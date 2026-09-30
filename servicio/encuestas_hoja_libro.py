# -*- coding: utf-8 -*-
"""
Formularios del Almacén — añadir respuestas a un libro que la persona ya trabaja
================================================================================
Hasta el 17/09/2026 la hoja vinculada se rehacía DESDE CERO con cada respuesta.
Todo lo que la persona hacía sobre el archivo se perdía en la siguiente
respuesta: pestañas nuevas, columnas calculadas con fórmulas (TOTAL = suma de
socios…), encabezados renombrados, columnas quitadas, filas ordenadas o
borradas. Pasó en «IBI 2025/prueba IFO (respuestas).xlsx».

Ahora se hace lo mismo que Google Sheets con un formulario:

- **El archivo existente no se rehace.** Solo se AÑADEN filas al final de la
  tabla, una por respuesta NUEVA (enviada después de la última ya escrita).
- **Cada columna se rellena por su encabezado.** Si la persona renombró una
  columna y el encabezado sigue conteniendo el título de la pregunta
  («A. Provincia» ↔ «Provincia») también se reconoce. Las columnas que no son
  de ninguna pregunta (p. ej. «TOTAL») copian la FÓRMULA de la fila de arriba,
  ajustada a la fila nueva; si no tienen fórmula se dejan vacías.
- **Preguntas nuevas del formulario** → columna nueva al final de la tabla.
  Una columna que la persona borró en el Excel NO vuelve, sea de una pregunta
  vigente o retirada; «Exportar» la recupera a propósito. Cada pregunta
  recuerda los nombres anteriores de su columna (`antes`), así un renombre que
  no llegó al archivo se reconoce y se vuelve a aplicar (29/09/2026).
- Pestañas, fórmulas, formatos y filas existentes no se tocan: el archivo se
  modifica a nivel de XML (`encuestas_hoja_xml`), no se reescribe con openpyxl,
  que dejaba las fórmulas como texto en OnlyOffice.

- **Pregunta renombrada en el formulario** → se renombra su encabezado (y las
  fórmulas que lo nombran), salvo que la persona ya le hubiera puesto otro
  nombre en el Excel: entonces manda el suyo.

Estado por formulario en `encuesta_hoja_estado`: hasta qué respuesta se
escribió (`hasta`) y, por pregunta, su título en el formulario y su encabezado
en la hoja (`preguntas` = {id: {form, hoja}}). Si un archivo existente no tiene
estado (anterior a este módulo) se deduce: están escritas las respuestas cuya
fecha aparece en la columna «Fecha» o, si no hay esa columna, tantas como filas
tenga la tabla. (La primera versión daba todas por escritas y perdió cuatro
respuestas de «Nuevo Formulario» el 17/09/2026.)

Autoría: Equipo de Tecnología Maquita — 2026-09-17
"""
import io
import json
import logging
import os
import re
import unicodedata

import encuestas_hoja_sincronizar as sincronizar
import encuestas_hoja_xml as xml_mod

log = logging.getLogger('almacen.encuestas.hoja_libro')

_tabla_lista = False

# Columnas fijas que pueden aparecer después de crear la hoja, y cómo se anotan
# en el estado (junto a las preguntas, con una clave que ningún id puede tener).
FIJAS_TARDIAS = ('PUNTUACION', 'CORREO')
PREFIJO_FIJA = '__fija__'


# ── estado en BD ─────────────────────────────────────────────────────────
def _asegurar_tabla():
    global _tabla_lista
    if _tabla_lista:
        return
    import almacen_bd as bd
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS encuesta_hoja_estado (
            encuesta_id TEXT PRIMARY KEY,
            hasta TIMESTAMPTZ,
            preguntas JSONB NOT NULL DEFAULT '[]'::jsonb,
            actualizado TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    # `provisional`: lo escribió el complemento DENTRO del editor y todavía no
    # consta en el archivo. Se revisa al cerrarse el libro (22/09/2026).
    bd.ejecutar('ALTER TABLE encuesta_hoja_estado '
                'ADD COLUMN IF NOT EXISTS provisional BOOLEAN NOT NULL DEFAULT FALSE')
    _tabla_lista = True


def leer_estado(encuesta_id):
    import almacen_bd as bd
    _asegurar_tabla()
    filas = bd.consultar('SELECT hasta, preguntas, provisional FROM encuesta_hoja_estado '
                         'WHERE encuesta_id = %s', (encuesta_id,))
    return filas[0] if filas else None


def guardar_estado(encuesta_id, hasta, preguntas, provisional=False):
    """`provisional`: la escritura solo consta dentro del editor abierto, no en
    el archivo. Se comprueba al cerrarse el libro (`encuestas_hoja_confirmacion`)."""
    import almacen_bd as bd
    _asegurar_tabla()
    bd.ejecutar("""
        INSERT INTO encuesta_hoja_estado (encuesta_id, hasta, preguntas, provisional, actualizado)
        VALUES (%s, %s, %s::jsonb, %s, NOW())
        ON CONFLICT (encuesta_id) DO UPDATE
        SET hasta = EXCLUDED.hasta, preguntas = EXCLUDED.preguntas,
            provisional = EXCLUDED.provisional, actualizado = NOW()
    """, (encuesta_id, hasta, json.dumps(preguntas, ensure_ascii=False), bool(provisional)))


# ── ayudantes ────────────────────────────────────────────────────────────
def _hoja_de_un_solo_formulario(fila_encuesta, ruta_hoja):
    """¿Esta hoja la alimenta solo este formulario?

    Si la comparten varios, sus filas se mezclan y ninguno puede decidir que
    una fila sobra. Ante la duda (o si la consulta falla) se dice que NO.
    """
    try:
        import almacen_bd as bd
        filas = bd.consultar(
            'SELECT id FROM encuestas WHERE hoja_ruta = %s', (ruta_hoja,))
        return len(filas) <= 1 and (not filas or filas[0]['id'] == fila_encuesta['id'])
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo comprobar si es compartida (%s)',
                    ruta_hoja, excepcion)
        return False


def _texto_suelto(valor):
    """Una respuesta en una línea cuando ya no queda la pregunta que la
    describe: sin su definición no se puede pedir al modelo que la lea."""
    if isinstance(valor, dict):
        return ' · '.join('%s: %s' % (k, v) for k, v in valor.items() if v not in (None, '', []))
    if isinstance(valor, list):
        return ', '.join(str(v) for v in valor)
    return str(valor)


def normalizar(texto):
    plano = unicodedata.normalize('NFKD', str(texto or ''))
    plano = ''.join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', plano).strip().upper()


def _contiene(texto, parte):
    return bool(parte) and re.search(
        r'(?<![A-Z0-9])' + re.escape(parte) + r'(?![A-Z0-9])', texto) is not None


def _columna_de_cabecera(encabezados, cabecera):
    """Índice (0..n) de la columna de la hoja para una cabecera del formulario.
    Primero igual; si no, la columna cuyo encabezado CONTIENE la cabecera
    (la más corta, para no confundir «Hombres -30 años» con su «(2)»)."""
    buscada = normalizar(cabecera)
    normales = [normalizar(e) for e in encabezados]
    if buscada in normales:
        return normales.index(buscada)
    candidatas = [(len(t), i) for i, t in enumerate(normales)
                  if t and _contiene(t, buscada)]
    return min(candidatas)[1] if candidatas else None


def construir_conservando(fila_encuesta, definicion, usuario, ruta_hoja):
    """El `.xlsx` con las respuestas nuevas añadidas, anotando ya el estado.

    Camino de siempre («Exportar»): quien llama escribe el archivo justo
    después. Para el camino en el que la escritura puede NO cuajar —el editor
    abierto pisa el archivo— está `preparar`, que devuelve el estado aparte
    para confirmarlo solo si el archivo quedó escrito (21/09/2026).
    """
    memoria, estado = preparar(fila_encuesta, definicion, usuario, ruta_hoja)
    if estado is not None:
        confirmar(definicion['id'], estado)
    return memoria


def confirmar(encuesta_id, estado):
    """Da por escritas las respuestas de `estado` (lo que devuelve `preparar`)."""
    guardar_estado(encuesta_id, estado['hasta'], estado['preguntas'])


def preparar(fila_encuesta, definicion, usuario, ruta_hoja):
    """(contenido, estado) SIN tocar el estado guardado.

    `contenido` es el `.xlsx` en memoria con las respuestas nuevas añadidas (o
    None si no hay nada que escribir o el libro no se puede leer, y entonces no
    se toca). `estado` es lo que habría que anotar cuando la escritura se
    confirme, o None si no hay nada que anotar.
    """
    import encuestas_hoja as hoja_mod
    encuesta_id = definicion['id']
    try:
        import nucleo_archivos as nucleo
        fisica = nucleo.ruta_fisica(int(usuario), ruta_hoja)
        existe = os.path.isfile(fisica)
        datos = hoja_mod.datos_de_hoja(fila_encuesta, definicion)
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo preparar (%s)', ruta_hoja, excepcion)
        return None, None

    cabeceras, listado = datos['cabeceras'], datos['listado']
    desplazamiento = len(cabeceras) - len(listado)
    titulos = {p['id']: cabeceras[desplazamiento + i] for i, p in enumerate(listado)}
    ultima = max([e for e in datos['enviadas'] if e] or [None], default=None)

    if not existe:
        memoria = hoja_mod.construir(fila_encuesta, definicion)
        if memoria is None:
            return None, None
        return memoria, {'hasta': ultima,
                         'preguntas': {i: {'form': t, 'hoja': t}
                                       for i, t in titulos.items()}}

    try:
        contenido = open(fisica, 'rb').read()
        encabezados, filas_hoja = xml_mod.leer_tabla(contenido)
    except xml_mod.SinTabla:
        log.warning('hoja %s: no tiene la tabla «Respuestas», no se toca', ruta_hoja)
        return None, None
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo leer el libro, no se toca (%s)', ruta_hoja, excepcion)
        return None, None

    # Una tabla dañada no se arregla añadiéndole filas (29/09/2026: el
    # complemento en vivo dejó 56 copias de los encabezados y una respuesta).
    try:
        import encuestas_hoja_reparar as reparar
        anotado = leer_estado(encuesta_id)
        conocidos = list(cabeceras)
        for anotada in ((anotado or {}).get('preguntas') or {}).values() \
                if isinstance((anotado or {}).get('preguntas'), dict) else []:
            if isinstance(anotada, dict):
                conocidos += [anotada.get('hoja'), anotada.get('form')] \
                    + list(anotada.get('antes') or [])
        clave, detalle = reparar.danada(contenido, conocidos)
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo examinar la tabla (%s)', ruta_hoja, excepcion)
        clave, detalle = '', ''
    if clave:
        if _hoja_de_un_solo_formulario(fila_encuesta, ruta_hoja) \
                and reparar.se_puede_rehacer(contenido):
            log.warning('hoja %s dañada (%s): se rehace desde las respuestas guardadas',
                        ruta_hoja, detalle)
            memoria = hoja_mod.construir(fila_encuesta, definicion)
            if memoria is None:
                return None, None
            return memoria, {'hasta': ultima,
                             'preguntas': {i: {'form': t, 'hoja': t}
                                           for i, t in titulos.items()}}
        if clave == 'encabezados':
            log.warning('hoja %s dañada (%s) y con trabajo propio de la persona: '
                        'no se toca; hay que repararla a mano', ruta_hoja, detalle)
            return None, None
        log.warning('hoja %s: %s; tiene trabajo propio, se sigue añadiendo al final',
                    ruta_hoja, detalle)

    try:
        estado = leer_estado(encuesta_id)
        if estado is None:
            hasta = _hasta_deducido(encabezados, filas_hoja, datos['enviadas'])
            preguntas = None
        else:
            hasta, preguntas = estado['hasta'], estado['preguntas']
        if not isinstance(preguntas, dict):
            preguntas = _preguntas_deducidas(preguntas, titulos, encabezados)

        plan = _planear(encabezados, cabeceras[:desplazamiento], listado, titulos, preguntas)

        # La hoja tiene que reflejar TODAS las respuestas, no solo las nuevas:
        # modificar una respuesta la duplicaba y borrarla dejaba su fila para
        # siempre (22/09/2026). Se comprueba lo escrito contra la base y, si no
        # cuadra, se reescriben las filas en su sitio.
        ancho = len(encabezados) + len(plan['columnas'])

        def _alinear(celdas):
            return [(celdas[plan['mapa'][i]] if celdas[plan['mapa'][i]] is not None else '')
                    if i in plan['mapa'] else None for i in range(ancho)]

        todas = [_alinear(celdas) for celdas in datos['cuerpo']]
        # La reconciliación reescribe y vacía filas, así que solo se permite
        # cuando está claro que TODAS las filas de la tabla son de este
        # formulario: con la hoja compartida por varios (pasa en «prueba IFO»,
        # con dos encuestas sobre el mismo libro) o sin ninguna respuesta
        # todavía, el motor no puede saber de quién es cada fila y se limita a
        # añadir, como antes (22/09/2026).
        #
        # Sin respuestas SÍ se vacía cuando consta que el motor ya escribió en
        # esta hoja (`hasta`): es que se borraron todas, y la hoja tiene que
        # quedar vacía como la pestaña Respuestas (28/09/2026).
        puede_reconciliar = (bool(todas) or hasta is not None) \
            and _hoja_de_un_solo_formulario(fila_encuesta, ruta_hoja)
        # Una pregunta que se quitó del formulario deja su columna en la hoja.
        # Su dato pertenece a una respuesta concreta: se vuelve a escribir con
        # ella, o al reordenar las filas quedaría junto a otra.
        vivas = {p['id'] for p in listado}
        columna_de = {normalizar(e): i for i, e in enumerate(encabezados)}
        retiradas = {}
        for id_pregunta, anotada in preguntas.items():
            if not isinstance(anotada, dict) or id_pregunta in vivas \
                    or id_pregunta.startswith(PREFIJO_FIJA):
                continue
            indice = columna_de.get(normalizar(anotada.get('hoja')))
            if indice is not None:
                retiradas[id_pregunta] = indice
        for fila_valores, respuesta in zip(todas, datos.get('respuestas') or []):
            for id_pregunta, indice in retiradas.items():
                valor = (respuesta or {}).get(id_pregunta)
                fila_valores[indice] = '' if valor is None else _texto_suelto(valor)
        desfase, iguales = sincronizar.revisar(filas_hoja, todas)
        if desfase and not puede_reconciliar:
            log.info('hoja %s: no se reconcilia (hoja compartida o sin respuestas); '
                     'solo se añaden filas', ruta_hoja)
            desfase = False
        nuevas = [c for c, e in zip(datos['cuerpo'], datos['enviadas'])
                  if e and (hasta is None or e > hasta)]
        if desfase:
            # Lo que ya no cuadra se reescribe entero; lo que falte al final se
            # añade después, por el camino de siempre.
            nuevas = datos['cuerpo'][len(filas_hoja):] if len(filas_hoja) < len(todas) else []
        if not (nuevas or desfase or plan['columnas'] or plan['renombres']):
            # Se conserva «provisional»: si lo último lo escribió el complemento
            # dentro de un editor abierto, aún no consta en el archivo. Borrar la
            # marca aquí (lo hacía «Exportar») daba la respuesta por escrita sin
            # estarlo, y no se reintentaba nunca (28/09/2026, respuesta 258).
            guardar_estado(encuesta_id, hasta, preguntas,
                           provisional=bool(estado and estado.get('provisional')))
            return None, None

        resultado = contenido
        columnas_nuevas, renombres = plan['columnas'], plan['renombres']
        if desfase and (columnas_nuevas or renombres):
            # Las columnas nuevas entran ANTES de reescribir las filas: si no,
            # la tabla todavía no las tiene y las respuestas ya escritas se
            # quedan sin su dato (la «Puntuación» de las anteriores, 28/09/2026).
            resultado = xml_mod.anadir_filas(resultado, [], columnas_nuevas, renombres)
            columnas_nuevas, renombres = [], []
        if desfase:
            # Gobierna las columnas de las preguntas vivas y también las de las
            # que se quitaron del formulario: su dato pertenece a una fila
            # concreta y, si no se mueve con ella, queda pegado a otra respuesta.
            retiradas = {normalizar(v.get('hoja')) for v in preguntas.values()
                         if isinstance(v, dict) and v.get('hoja')}
            columnas_datos = [i for i in range(ancho)
                              if i in plan['mapa']
                              or (i < len(encabezados)
                                  and normalizar(encabezados[i]) in retiradas)]
            hasta_donde = len(todas) if len(filas_hoja) >= len(todas) else len(filas_hoja)
            if todas:
                rehecho = sincronizar.escribir(resultado, todas[:hasta_donde], columnas_datos)
            else:
                # No queda ninguna respuesta: la hoja se vacía entera.
                import encuestas_hoja_vaciar
                rehecho = encuestas_hoja_vaciar.vaciar(resultado)
            if rehecho is not None:
                resultado = rehecho
            log.info('hoja %s: reconciliada desde la fila %d (%d respuestas, %d filas escritas)',
                     ruta_hoja, iguales + 1, len(todas), len(filas_hoja))

        filas = [_alinear(celdas) for celdas in nuevas]
        if filas or columnas_nuevas or renombres:
            resultado = xml_mod.anadir_filas(resultado, filas, columnas_nuevas, renombres)
        log.info('hoja %s: %d filas, %d columnas nuevas, %d renombradas', ruta_hoja,
                 len(filas), len(plan['columnas']), len(plan['renombres']))
        return io.BytesIO(resultado), {'hasta': ultima if (nuevas or desfase) else hasta,
                                       'preguntas': preguntas}
    except Exception as excepcion:
        log.warning('hoja %s: no se pudieron añadir las respuestas (%s); no se toca',
                    ruta_hoja, excepcion)
        return None, None


# ── qué hay ya escrito (archivo sin estado) ──────────────────────────────
def _hasta_deducido(encabezados, filas_hoja, enviadas):
    """Fecha de la última respuesta que YA está en la hoja, o None."""
    from datetime import datetime, timedelta
    enviadas = sorted(e for e in enviadas if e)
    if not filas_hoja or not enviadas:
        return None
    normales = [normalizar(e) for e in encabezados]
    if 'FECHA' in normales:
        columna, en_hoja = normales.index('FECHA'), set()
        for fila in filas_hoja:
            try:
                momento = datetime(1899, 12, 30) + timedelta(days=float(fila[columna]))
                en_hoja.add((momento + timedelta(milliseconds=500)).replace(microsecond=0))
            except (TypeError, ValueError):
                continue
        presentes = [e for e in enviadas
                     if e.replace(tzinfo=None, microsecond=0) in en_hoja]
        if presentes:
            return max(presentes)
    return enviadas[min(len(filas_hoja), len(enviadas)) - 1]


def _preguntas_deducidas(conocidas, titulos, encabezados):
    """Estado por pregunta cuando no lo había (o era la lista antigua de ids)."""
    salida = {}
    for id_, titulo in titulos.items():
        i = _columna_de_cabecera(encabezados, titulo)
        if i is not None:
            salida[id_] = {'form': titulo, 'hoja': encabezados[i]}
        elif conocidas is not None and id_ in conocidas:
            # La quitó la persona: se anota como tal para no volver a crearla.
            salida[id_] = {'form': titulo, 'hoja': None, 'borrada': True}
    return salida


def restaurar_columnas(encuesta_id):
    """«Exportar» devuelve a la hoja las columnas que la persona borró de
    preguntas que siguen en el formulario (y «Puntuación»/«Correo»). Es la
    forma de recuperarlas a propósito: por sí solas no vuelven (29/09/2026)."""
    estado = leer_estado(encuesta_id)
    if not estado or not isinstance(estado.get('preguntas'), dict):
        return
    preguntas = {k: v for k, v in estado['preguntas'].items()
                 if not (isinstance(v, dict) and v.get('borrada'))}
    if len(preguntas) != len(estado['preguntas']):
        guardar_estado(encuesta_id, estado['hasta'], preguntas,
                       provisional=bool(estado.get('provisional')))


def estado_tras_editor(previas, titulos, encabezados):
    """Estado por pregunta según los encabezados que quedaron en el libro
    abierto, SIN olvidar lo anterior: la columna que la persona borró en el
    editor queda «borrada» (antes se olvidaba y el motor la volvía a crear) y
    se conservan los nombres anteriores de cada columna (29/09/2026)."""
    if not isinstance(previas, dict):
        return _preguntas_deducidas(previas, titulos, encabezados)
    salida = dict(previas)
    normales = [normalizar(e) for e in encabezados]
    for id_, titulo in titulos.items():
        anotada = previas.get(id_) or {}
        antes = [a for a in (anotada.get('antes') or []) if a]
        i = None
        for nombre in [anotada.get('hoja'), titulo] + antes:
            if i is None and nombre and normalizar(nombre) in normales:
                i = normales.index(normalizar(nombre))
        if i is None:
            i = _columna_de_cabecera(encabezados, titulo)
        if i is not None:
            salida[id_] = {'form': titulo, 'hoja': encabezados[i], 'antes': antes}
        elif anotada:
            salida[id_] = {'form': titulo, 'hoja': None, 'borrada': True, 'antes': antes}
    return salida


# ── qué hay que cambiar en las columnas ──────────────────────────────────
def _planear(encabezados, fijas, listado, titulos, preguntas):
    """Decide columnas nuevas, renombres y a qué columna va cada dato.
    Actualiza `preguntas` (el estado) en el sitio."""
    normales = [normalizar(e) for e in encabezados]
    mapa, columnas, renombres = {}, [], []

    def libre(titulo):
        usados = set(normales) | {normalizar(t) for t in columnas} \
            | {normalizar(n) for _, n in renombres}
        candidato, n = titulo, 1
        while normalizar(candidato) in usados:
            n += 1
            candidato = '%s (%d)' % (titulo, n)
        return candidato

    def nueva(id_, titulo, j):
        nombre = libre(titulo)
        columnas.append(nombre)
        preguntas[id_] = {'form': titulo, 'hoja': nombre}
        mapa[len(encabezados) + len(columnas) - 1] = j

    # «Fecha», «Quién»…: solo si el encabezado es exactamente ese (una pregunta
    # «Fecha de elaboración» no debe recibir la fecha de envío).
    for j, cabecera in enumerate(fijas):
        clave = PREFIJO_FIJA + normalizar(cabecera)
        tardia = normalizar(cabecera) in FIJAS_TARDIAS
        if normalizar(cabecera) in normales:
            mapa.setdefault(normales.index(normalizar(cabecera)), j)
            if tardia:
                preguntas[clave] = {'form': cabecera, 'hoja': cabecera}
            continue
        # «Puntuación» y «Correo» dependen de un ajuste que se puede activar
        # DESPUÉS de crear la hoja (28/09/2026: se activó el cuestionario y la
        # hoja se quedó sin columna de nota). Si nunca tuvo columna, se crea al
        # final; si la tuvo y la persona la quitó, no vuelve.
        if not tardia:
            continue
        if preguntas.get(clave) is None:
            nombre = libre(cabecera)
            columnas.append(nombre)
            preguntas[clave] = {'form': cabecera, 'hoja': nombre}
            mapa[len(encabezados) + len(columnas) - 1] = j
        else:
            preguntas[clave] = {'form': cabecera, 'hoja': None, 'borrada': True}

    for n, pregunta in enumerate(listado):
        id_, titulo, j = pregunta['id'], titulos[pregunta['id']], len(fijas) + n
        anotada = preguntas.get(id_)
        if anotada is None:
            # Pregunta nueva: columna propia, sin buscar parecidas (podría
            # quedarse con una columna de la persona que contenga el título).
            nueva(id_, titulo, j)
            continue
        # Nombres que tuvo la columna: si un renombre no llegó al archivo (el
        # editor guardó encima), la columna sigue con el nombre viejo y se la
        # reconoce por él (29/09/2026, «prueba_2026»).
        antes = [a for a in (anotada.get('antes') or []) if a]
        columna = None
        for nombre in [anotada.get('hoja')] + antes:
            if columna is None and nombre and normalizar(nombre) in normales:
                columna = normales.index(normalizar(nombre))
        for intento in (titulo, anotada.get('form')):
            if columna is None and intento:
                columna = _columna_de_cabecera(encabezados, intento)
        if columna is None or columna in mapa:
            # La persona borró la columna en el Excel: no vuelve (se recupera a
            # propósito con «Exportar», ver `restaurar_columnas`).
            if anotada.get('hoja'):
                log.info('columna «%s» ya no está en la hoja: no se vuelve a crear',
                         anotada['hoja'])
            preguntas[id_] = {'form': titulo, 'hoja': None, 'borrada': True,
                              'antes': antes}
            continue
        hoja = encabezados[columna]
        viejo = normales[columna]
        renombrada = normalizar(anotada.get('form')) != normalizar(titulo) \
            and viejo == normalizar(anotada.get('form'))
        # Renombre que se perdió: la columna conserva un nombre que le puso el
        # motor (no la persona), distinto del título actual.
        perdido = viejo != normalizar(titulo) \
            and viejo in {normalizar(a) for a in antes}
        if renombrada or perdido:
            hoja = libre(titulo)
            renombres.append((encabezados[columna], hoja))
            antes = (antes + [encabezados[columna]])[-6:]
        preguntas[id_] = {'form': titulo, 'hoja': hoja, 'antes': antes}
        mapa[columna] = j
    return {'mapa': mapa, 'columnas': columnas, 'renombres': renombres}
