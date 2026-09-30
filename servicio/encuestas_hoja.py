# -*- coding: utf-8 -*-
"""
Formularios del Almacén — la hoja de cálculo vinculada
======================================================
Hasta el 27/08/2026 exportar era un botón: se pulsaba, se generaba el `.xlsx` y
ahí se quedaba. Con cada respuesta nueva el archivo envejecía en silencio, y
quien lo abría podía estar mirando datos de hace una semana sin saberlo.

Ahora la hoja queda **vinculada** al formulario: la primera exportación anota
dónde está, y a partir de entonces se rehace sola en dos momentos:

    al llegar una respuesta   cambian las FILAS
    al editar el formulario   cambian las COLUMNAS (añadir o quitar preguntas)

El segundo hace falta igual que el primero: quien añade una pregunta espera
verla en la hoja, y sin esto la columna no aparecía hasta que alguien
respondiera.

Decisiones que conviene recordar:

- **Se rehace en segundo plano, no mientras alguien responde.** Quien rellena un
  formulario no tiene por qué esperar a que se escriba un Excel; y si la
  escritura fallara, su respuesta ya está guardada y no se pierde.
- **Nunca falla hacia fuera.** Todo va dentro de try/except: lo peor que puede
  pasar es que la hoja se quede como estaba y haya que pulsar «Exportar», que es
  lo que había antes.
- **Se avisa al editor de que el archivo cambió** (`invalidar_cache`): sin eso,
  quien lo abra sigue viendo la copia que el editor tiene guardada, que fue el
  fallo que costó encontrar esa misma mañana.
- **Se rehace la hoja entera, no se añade una fila.** Un `.xlsx` con formato de
  tabla no se amplía «por abajo» sin reescribir medio archivo, y rehacerlo cuesta
  milisegundos: no compensa la complejidad de mantener el formato al insertar.

Autoría: Equipo de Tecnología Maquita — 2026-08-27
"""
import io
import logging
import threading

import encuestas_bd as ebd

log = logging.getLogger('almacen.encuestas.hoja')

# Formularios que se están rehaciendo ahora mismo. Si llegan cinco respuestas
# seguidas no tiene sentido lanzar cinco escrituras del mismo archivo: la que ya
# está en marcha va a leer también las nuevas.
_en_marcha = set()
_candado = threading.Lock()

# Refrescos aplazados por formulario (ver `refrescar_al_editar`).
_relojes = {}
SEGUNDOS_ESPERA = 8


def ruta_de(fila_encuesta):
    """Ruta de la hoja vinculada, o '' si el formulario no tiene ninguna."""
    return ((fila_encuesta or {}).get('hoja_ruta') or '').strip()


def _olvidar_sin_trabajo(usuario, ruta_hoja):
    """La hoja deja de constar como «sin nada que escribir»."""
    try:
        import vivo_sin_trabajo as sin_trabajo
        sin_trabajo.olvidar(usuario, ruta_hoja)
    except Exception:
        pass


def vincular(encuesta_id, ruta_hoja):
    """Anota qué archivo es la hoja de este formulario (lo hace «Exportar»)."""
    try:
        ebd.bd.ejecutar('UPDATE encuestas SET hoja_ruta = %s WHERE id = %s',
                        (ruta_hoja, encuesta_id))
    except Exception as excepcion:
        log.warning('no se pudo vincular la hoja de %s: %s', encuesta_id, excepcion)


def refrescar_en_segundo_plano(fila_encuesta, definicion):
    """Rehace la hoja sin hacer esperar a quien acaba de responder."""
    # Los libros que reciben las respuestas de este formulario («Recibir
    # respuestas de un formulario…», 28/09/2026), tenga o no hoja propia.
    try:
        import formulario_destinos
        formulario_destinos.al_llegar_respuesta((definicion or {}).get('id') or fila_encuesta['id'])
    except Exception as excepcion:
        log.warning('destinos de %s: %s', fila_encuesta.get('id'), excepcion)
    ruta_hoja = ruta_de(fila_encuesta)
    if not ruta_hoja:
        return          # este formulario no tiene hoja: no hay nada que rehacer

    # Hay trabajo para esta hoja: si constaba como «sin nada que escribir», el
    # puente del editor tiene que volver a preguntarlo ya (22/09/2026).
    try:
        import vivo_sin_trabajo as sin_trabajo
        sin_trabajo.olvidar(fila_encuesta.get('propietario'), ruta_hoja)
    except Exception:
        pass

    encuesta_id = fila_encuesta['id']
    with _candado:
        if encuesta_id in _en_marcha:
            return
        _en_marcha.add(encuesta_id)

    hilo = threading.Thread(
        target=_rehacer, args=(dict(fila_encuesta), definicion, ruta_hoja),
        name='hoja-%s' % encuesta_id[:8], daemon=True)
    hilo.start()


def refrescar_al_editar(fila_encuesta, definicion):
    """Rehace la hoja tras editar el formulario, unos segundos después.

    Al añadir o quitar una pregunta cambian las COLUMNAS, así que la hoja se
    queda desfasada aunque no llegue ninguna respuesta nueva (27/08/2026).

    Va con retardo a propósito: el editor guarda solo, a 1,2 s de dejar de
    escribir, y sin esperar se reescribiría el Excel con cada palabra que se
    teclea. El reloj se reinicia en cada guardado, así que la hoja se rehace una
    vez, cuando la persona deja de editar.
    """
    ruta_hoja = ruta_de(fila_encuesta)
    if not ruta_hoja:
        return
    encuesta_id = fila_encuesta['id']
    with _candado:
        anterior = _relojes.pop(encuesta_id, None)
        if anterior:
            anterior.cancel()
        # La definición NO se guarda aquí: cuando el reloj salte se lee la del
        # archivo, que para entonces será la última. Guardar esta dejaría la
        # hoja con la versión de hace ocho segundos.
        reloj = threading.Timer(
            SEGUNDOS_ESPERA, _rehacer_leyendo, args=(dict(fila_encuesta),))
        reloj.daemon = True
        _relojes[encuesta_id] = reloj
        reloj.start()


def al_cambiar_respuestas(encuesta_id):
    """Se borraron o se recuperaron respuestas: la hoja tiene que reflejarlo
    sin esperar a que llegue una respuesta nueva (28/09/2026). Nunca lanza."""
    try:
        fila = ebd.obtener(encuesta_id)
        if fila:
            refrescar_al_editar(fila, None)
    except Exception as excepcion:
        log.warning('hoja de %s: no se pudo avisar del cambio (%s)', encuesta_id, excepcion)


def _rehacer_leyendo(fila_encuesta):
    """Relee la definición del `.forma` y rehace la hoja."""
    encuesta_id = fila_encuesta['id']
    with _candado:
        _relojes.pop(encuesta_id, None)
        if encuesta_id in _en_marcha:
            return          # ya hay una escritura en curso; leerá esto también
        _en_marcha.add(encuesta_id)
    try:
        from api_encuestas import leer_definicion
        definicion = leer_definicion(int(fila_encuesta['propietario']),
                                     fila_encuesta['ruta'])
        if definicion is None:
            return
    except Exception as excepcion:
        log.warning('no se pudo releer %s: %s', fila_encuesta.get('ruta'), excepcion)
        with _candado:
            _en_marcha.discard(encuesta_id)
        return
    ruta_hoja = ruta_de(fila_encuesta)
    if ruta_hoja:
        _rehacer(fila_encuesta, definicion, ruta_hoja)   # libera el turno al salir
    else:
        with _candado:
            _en_marcha.discard(encuesta_id)


# Si el Excel está abierto en el editor, se reintenta cada tanto hasta que se
# cierre (17/09/2026). Escribirlo por fuera con gente dentro partía la sala en
# dos y el guardado del editor borraba lo escrito.
SEGUNDOS_REINTENTO = 120
MAX_REINTENTOS = 360          # 12 horas; la siguiente respuesta lo relanza


def _sala_ocupada(propietario, ruta_hoja):
    try:
        import sala_editor
        from api_onlyoffice import _base_documento
        return sala_editor.usuarios_conectados(_base_documento(propietario, ruta_hoja))
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo consultar el editor (%s)', ruta_hoja, excepcion)
        return None


def _aplazar(fila_encuesta, ruta_hoja, intento):
    encuesta_id = fila_encuesta['id']
    if intento >= MAX_REINTENTOS:
        log.warning('hoja %s: sigue abierta tras %d reintentos, se deja', ruta_hoja, intento)
        return
    with _candado:
        if encuesta_id in _relojes:
            return      # ya hay un refresco programado; leerá lo último
        reloj = threading.Timer(SEGUNDOS_REINTENTO, _reintentar,
                                args=(dict(fila_encuesta), intento + 1))
        reloj.daemon = True
        _relojes[encuesta_id] = reloj
        reloj.start()


def _reintentar(fila_encuesta, intento):
    encuesta_id = fila_encuesta['id']
    with _candado:
        _relojes.pop(encuesta_id, None)
        if encuesta_id in _en_marcha:
            return
        _en_marcha.add(encuesta_id)
    try:
        from api_encuestas import leer_definicion
        definicion = leer_definicion(int(fila_encuesta['propietario']),
                                     fila_encuesta['ruta'])
    except Exception as excepcion:
        log.warning('no se pudo releer %s: %s', fila_encuesta.get('ruta'), excepcion)
        definicion = None
    ruta_hoja = ruta_de(fila_encuesta)
    if definicion is None or not ruta_hoja:
        with _candado:
            _en_marcha.discard(encuesta_id)
        return
    _rehacer(fila_encuesta, definicion, ruta_hoja, intento)


def al_cerrar_editor(usuario, ruta):
    """El editor acaba de soltar este archivo: si es la hoja de respuestas de
    algún formulario, se le añade lo que llegó mientras estaba abierto
    (17/09/2026). Los reintentos por reloj se pierden al recargar el servicio;
    este aviso no."""
    try:
        # Lo que el complemento dio por escrito dentro del editor solo vale si
        # de verdad quedó en el archivo (22/09/2026).
        try:
            import encuestas_hoja_confirmacion as confirmacion
            confirmacion.revisar(usuario, ruta)
        except Exception as excepcion:
            log.warning('al cerrar %s: no se pudo revisar lo escrito en vivo (%s)',
                        ruta, excepcion)
        try:
            import formulario_destinos
            formulario_destinos.al_cerrar(usuario, ruta)
        except Exception as excepcion:
            log.warning('al cerrar %s: destinos (%s)', ruta, excepcion)
        filas = ebd.bd.consultar(
            "SELECT * FROM encuestas WHERE hoja_ruta = %s "
            "AND (propietario = %s OR hoja_ruta LIKE '/unidades/%%')",
            (ruta, int(usuario)))
        vistos = set()
        for fila in filas:
            clave = (fila['propietario'], fila['ruta'])
            if clave not in vistos:
                vistos.add(clave)
                refrescar_al_editar(fila, None)
    except Exception as excepcion:
        log.warning('al cerrar %s: %s', ruta, excepcion)


def _rehacer(fila_encuesta, definicion, ruta_hoja, intento=0):
    encuesta_id = fila_encuesta['id']
    try:
        dentro = _sala_ocupada(int(fila_encuesta['propietario']), ruta_hoja)
        if dentro is None or dentro:      # sin respuesta del editor: no arriesgar
            log.info('hoja %s abierta en el editor (%s): se rehace al cerrarse',
                     ruta_hoja, dentro)
            _aplazar(fila_encuesta, ruta_hoja, intento)
            return
        import nucleo_archivos as nucleo
        import encuestas_hoja_libro as libro_mod
        propietario = int(fila_encuesta['propietario'])
        # Rehacer desde cero borraba pestañas, fórmulas y columnas que la
        # persona añade al libro (17/09/2026): ahora solo se AÑADEN las filas
        # de las respuestas nuevas, como hace Google Sheets.
        contenido, estado = libro_mod.preparar(
            fila_encuesta, definicion, propietario, ruta_hoja)
        if contenido is None:
            return
        carpeta = ruta_hoja.rsplit('/', 1)[0] or '/'
        nombre = ruta_hoja.rsplit('/', 1)[-1]
        nucleo.subir(propietario, carpeta, nombre, contenido)
        # Las filas añadidas llevan fórmulas sin resultado: OnlyOffice las
        # calcula y guarda (si no, se veían como texto «=SUM(…», 17/09/2026).
        import encuestas_hoja_recalculo as recalculo
        calculado = recalculo.recalcular(propietario, ruta_hoja)
        if calculado:
            nucleo.subir(propietario, carpeta, nombre, io.BytesIO(calculado))

        # Si alguien entró en el editor MIENTRAS se escribía, su guardado va a
        # pisar estas filas (pasó el 21/09/2026: el editor guardó 17 s después y
        # la respuesta se perdió). En ese caso no se da por escrita: se reintenta
        # al cerrarse la sala. Solo se anota el estado cuando nadie está dentro.
        if _sala_ocupada(propietario, ruta_hoja):
            log.info('hoja %s: alguien entró al editor mientras se escribía; '
                     'se reintenta al cerrarse', ruta_hoja)
            _aplazar(fila_encuesta, ruta_hoja, intento)
        elif estado is not None:
            libro_mod.confirmar(encuesta_id, estado)

        # El archivo se acaba de reemplazar por fuera del editor: si no se avisa,
        # quien lo abra ve la copia guardada del Document Server.
        try:
            from api_onlyoffice import invalidar_cache
            invalidar_cache(propietario, ruta_hoja)
        except Exception as excepcion:
            log.warning('hoja %s: no se pudo refrescar el editor (%s)',
                        ruta_hoja, excepcion)

        # Y a los vínculos: si alguien alimenta una hoja de su libro desde este
        # archivo de respuestas, hay que rehacerla ahora, no en la próxima
        # edición. Es lo que hace que la hoja del libro se llene sola.
        try:
            from api_vinculos import refrescar_por_origen
            refrescar_por_origen(propietario, ruta_hoja)
        except Exception as excepcion:
            log.warning('hoja %s: no se pudieron refrescar los vínculos (%s)',
                        ruta_hoja, excepcion)
        log.info('hoja actualizada: %s', ruta_hoja)
    except Exception as excepcion:
        # La respuesta ya está guardada; la hoja se queda como estaba y se puede
        # rehacer a mano con «Exportar».
        log.warning('no se pudo rehacer la hoja %s: %s', ruta_hoja, excepcion)
    finally:
        with _candado:
            _en_marcha.discard(encuesta_id)


def cabeceras(fila_encuesta, definicion):
    """Solo la fila de cabeceras de la hoja, para quien la pinta en vivo
    (el complemento del editor crea la hoja del libro con ellas, 10/09/2026)."""
    import encuestas_ajustes as ajustes_mod
    import encuestas_modelo as modelo
    import encuestas_colaboradores as colaboradores
    ajustes = ajustes_mod.limpiar(fila_encuesta.get('ajustes'))
    return cabeceras_de(ajustes, colaboradores.desplegar(modelo.preguntas(definicion)))


def recoge_correo(ajustes):
    """¿El formulario recoge el correo de quien responde? Si no, la hoja no
    lleva la columna «Correo» (11/09/2026: antes salía siempre, vacía)."""
    import encuestas_ajustes as ajustes_mod
    return (ajustes or {}).get('recopilar_correo', ajustes_mod.CORREO_NO) != ajustes_mod.CORREO_NO


def cabeceras_de(ajustes, listado):
    """Fecha, Quién, (Correo), (Puntuación) y una columna por pregunta."""
    import encuestas_excel as excel
    import encuestas_modelo as modelo
    # Encuesta ANÓNIMA: ni «Quién» ni «Correo». Se prometió no saber quién
    # responde y la hoja no debe insinuar lo contrario (11/09/2026).
    return excel.encabezados_unicos(
        ['Fecha'] +
        ([] if ajustes.get('anonimo') else ['Quién']) +
        (['Correo'] if recoge_correo(ajustes) and not ajustes.get('anonimo') else []) +
        (['Puntuación'] if ajustes.get('cuestionario') else []) +
        [modelo.plano(p['titulo']) for p in listado])


def construir(fila_encuesta, definicion):
    """El `.xlsx` completo en memoria, o None si no se puede generar.

    Vive aquí y no en el endpoint porque lo usan DOS caminos: el botón
    «Exportar» y el refresco automático, y si cada uno armara el archivo por su
    cuenta acabarían dando resultados distintos.
    """
    try:
        from openpyxl import Workbook
    except ImportError:
        log.warning('sin openpyxl: no se puede generar la hoja')
        return None

    import encuestas_excel as excel
    datos = datos_de_hoja(fila_encuesta, definicion)
    cabeceras, cuerpo = datos['cabeceras'], datos['cuerpo']

    libro = Workbook()
    tema = datos['tema']
    try:
        excel.escribir(libro, cabeceras, cuerpo, datos['titulo'], tema)
    except Exception as excepcion:
        # El formato no puede costar el archivo: si algo falla, se escribe la
        # rejilla de siempre y la hoja sale igual.
        log.warning('hoja sin formato (%s)', excepcion)
        libro = Workbook()
        hoja = libro.active
        hoja.title = 'Respuestas'
        hoja.append(cabeceras)
        for celdas in cuerpo:
            hoja.append(celdas)

    memoria = io.BytesIO()
    libro.save(memoria)
    memoria.seek(0)
    return memoria


def datos_de_hoja(fila_encuesta, definicion):
    """Cabeceras y filas de la hoja de respuestas, sin escribir ningún archivo.

    Separado de `construir` el 17/09/2026: `encuestas_hoja_libro` añade estas
    filas a un libro que ya existe en vez de rehacerlo.
    """
    import encuestas_ajustes as ajustes_mod
    import encuestas_modelo as modelo
    from api_encuestas import quien_respondio

    filas = ebd.listar_respuestas(definicion['id'])
    nombres = ebd.nombres_usuarios([f['usuario_id'] for f in filas])
    import encuestas_colaboradores as colaboradores
    ajustes = ajustes_mod.limpiar(fila_encuesta.get('ajustes'))
    # La pregunta «Colaborador» ocupa varias columnas: la del nombre y una por
    # cada dato de nómina (28/09/2026). De aquí en adelante `listado` son las
    # COLUMNAS de la hoja, y cada respuesta se reparte igual.
    originales = modelo.preguntas(definicion)
    listado = colaboradores.desplegar(originales)
    es_quiz = ajustes['cuestionario']

    cabeceras = cabeceras_de(ajustes, listado)

    cuerpo, enviadas, respuestas, ids = [], [], [], []
    for fila in reversed(filas):    # de la más antigua a la más reciente
        respuesta = colaboradores.desplegar_respuesta(originales, fila['datos'] or {})
        enviadas.append(fila['enviada_en'])
        ids.append(fila['id'])
        # Lo respondido tal cual, por si hace falta una pregunta que ya no está
        # en el formulario pero cuya columna sigue en la hoja (22/09/2026).
        respuestas.append(respuesta)
        celdas = [
            # Fecha de verdad, no texto: así la tabla se puede ordenar y filtrar
            # por cuándo se respondió, que es lo primero que se hace con esto.
            fila['enviada_en'].replace(tzinfo=None, microsecond=0) if fila['enviada_en'] else '',
        ]
        if not ajustes.get('anonimo'):
            celdas.append(quien_respondio(fila, nombres, ajustes, definicion))
            if recoge_correo(ajustes):
                celdas.append(fila.get('correo') or '')
        if es_quiz:
            celdas.append(
                '' if fila.get('puntos') is None
                else '%s / %s' % (fila['puntos'], fila.get('puntos_max') or 0))
        for pregunta in listado:
            # Cómo se lee cada respuesta lo decide el modelo, que es quien
            # sabe qué forma tiene cada tipo (una cuadrícula es un mapa, no un
            # texto). Antes se resolvía aquí y solo contemplaba listas.
            celdas.append(modelo.texto_de(pregunta,
                                          respuesta.get(pregunta['id'])))
        cuerpo.append(celdas)
    return {'cabeceras': cabeceras, 'cuerpo': cuerpo, 'listado': listado,
            'enviadas': enviadas, 'respuestas': respuestas, 'ids': ids,
            'titulo': modelo.plano(definicion.get('titulo')),
            'tema': (definicion.get('tema') or {}).get('color')}
