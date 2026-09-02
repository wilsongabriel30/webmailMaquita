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


def vincular(encuesta_id, ruta_hoja):
    """Anota qué archivo es la hoja de este formulario (lo hace «Exportar»)."""
    try:
        ebd.bd.ejecutar('UPDATE encuestas SET hoja_ruta = %s WHERE id = %s',
                        (ruta_hoja, encuesta_id))
    except Exception as excepcion:
        log.warning('no se pudo vincular la hoja de %s: %s', encuesta_id, excepcion)


def refrescar_en_segundo_plano(fila_encuesta, definicion):
    """Rehace la hoja sin hacer esperar a quien acaba de responder."""
    ruta_hoja = ruta_de(fila_encuesta)
    if not ruta_hoja:
        return          # este formulario no tiene hoja: no hay nada que rehacer

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


def _rehacer(fila_encuesta, definicion, ruta_hoja):
    encuesta_id = fila_encuesta['id']
    try:
        contenido = construir(fila_encuesta, definicion)
        if contenido is None:
            return
        import nucleo_archivos as nucleo
        propietario = int(fila_encuesta['propietario'])
        carpeta = ruta_hoja.rsplit('/', 1)[0] or '/'
        nombre = ruta_hoja.rsplit('/', 1)[-1]
        nucleo.subir(propietario, carpeta, nombre, contenido)

        # El archivo se acaba de reemplazar por fuera del editor: si no se avisa,
        # quien lo abra ve la copia guardada del Document Server.
        try:
            from api_onlyoffice import invalidar_cache
            invalidar_cache(propietario, ruta_hoja)
        except Exception as excepcion:
            log.warning('hoja %s: no se pudo refrescar el editor (%s)',
                        ruta_hoja, excepcion)
        log.info('hoja actualizada: %s', ruta_hoja)
    except Exception as excepcion:
        # La respuesta ya está guardada; la hoja se queda como estaba y se puede
        # rehacer a mano con «Exportar».
        log.warning('no se pudo rehacer la hoja %s: %s', ruta_hoja, excepcion)
    finally:
        with _candado:
            _en_marcha.discard(encuesta_id)


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

    import encuestas_ajustes as ajustes_mod
    import encuestas_excel as excel
    import encuestas_modelo as modelo
    from api_encuestas import quien_respondio

    filas = ebd.listar_respuestas(definicion['id'])
    nombres = ebd.nombres_usuarios([f['usuario_id'] for f in filas])
    ajustes = ajustes_mod.limpiar(fila_encuesta.get('ajustes'))
    listado = modelo.preguntas(definicion)
    es_quiz = ajustes['cuestionario']

    cabeceras = excel.encabezados_unicos(
        ['Fecha', 'Quién', 'Correo'] + (['Puntuación'] if es_quiz else []) +
        [modelo.plano(p['titulo']) for p in listado])

    cuerpo = []
    for fila in reversed(filas):    # de la más antigua a la más reciente
        respuesta = fila['datos'] or {}
        celdas = [
            # Fecha de verdad, no texto: así la tabla se puede ordenar y filtrar
            # por cuándo se respondió, que es lo primero que se hace con esto.
            fila['enviada_en'].replace(tzinfo=None) if fila['enviada_en'] else '',
            quien_respondio(fila, nombres, ajustes),
            '' if ajustes.get('anonimo') else (fila.get('correo') or ''),
        ]
        if es_quiz:
            celdas.append(
                '' if fila.get('puntos') is None
                else '%s / %s' % (fila['puntos'], fila.get('puntos_max') or 0))
        for pregunta in listado:
            valor = respuesta.get(pregunta['id'])
            if isinstance(valor, list):
                valor = ', '.join(str(v) for v in valor)
            celdas.append('' if valor is None else str(valor))
        cuerpo.append(celdas)

    libro = Workbook()
    tema = (definicion.get('tema') or {}).get('color')
    try:
        excel.escribir(libro, cabeceras, cuerpo,
                       modelo.plano(definicion.get('titulo')), tema)
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
