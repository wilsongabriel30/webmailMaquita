# -*- coding: utf-8 -*-
"""
Recibir respuestas de un formulario en un Excel propio (Drive Maquita)
=====================================================================
Un formulario escribe sus respuestas en SU hoja de respuestas. Pero la gente
trabaja en libros propios: una hoja por provincia rediseñada a su manera, con
sus totales y su formato (Martín, «Prueba IFO/CHIMBORAZO.xlsx», 28/09/2026). Lo
que hace falta es que ese libro RECIBA las respuestas nuevas del formulario,
sin rehacerlo ni depender de fórmulas hacia otro archivo.

Una conexión (tabla `formulario_destinos`) dice: «las respuestas de este
formulario —todas, o solo las que cumplan un filtro, p. ej. Provincia =
Chimborazo— entran como filas en esta hoja de este libro». Entonces:

  · cada respuesta es UNA FILA nueva al final del bloque de datos;
  · cada dato va a la columna cuyo encabezado es la pregunta (da igual el orden);
  · las columnas de la persona (sus TOTAL) copian la fórmula de la fila de
    arriba; nada más del libro se toca;
  · una respuesta no se escribe dos veces: se anota su id y, además, si la fecha
    de envío ya está en la columna «Fecha», se da por escrita (así, al conectar
    un libro que ya tenía algunas copiadas a mano, solo entran las que faltan).

Cuándo se escribe: al llegar una respuesta (si el libro está cerrado) y al
cerrarse el libro en el editor. Con el libro ABIERTO las escribe el complemento
«respuestas en vivo» dentro de la sesión (`encuestas_vivo` delega aquí); eso
queda como provisional y se comprueba contra el archivo al cerrarse.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import io
import json
import logging
import threading

import almacen_bd as bd
import formulario_destinos_xml as lugar_mod
from encuestas_hoja_libro import _columna_de_cabecera, normalizar

log = logging.getLogger('almacen.formulario_destinos')

_esquema_listo = False
_en_marcha = set()
_candado = threading.Lock()

PREFIJO_VIVO = 'destino:'


def asegurar_esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS formulario_destinos (
            id               SERIAL PRIMARY KEY,
            encuesta_id      TEXT NOT NULL,
            destino_usuario  INTEGER NOT NULL,
            destino_ruta     TEXT NOT NULL,
            destino_hoja     TEXT NOT NULL,
            filtro_pregunta  TEXT,           -- id de la pregunta (o NULL: todas)
            filtro_valor     TEXT,
            desde            TIMESTAMPTZ,    -- NULL = también las anteriores que falten
            escritas         JSONB NOT NULL DEFAULT '[]'::jsonb,
            provisionales    JSONB NOT NULL DEFAULT '[]'::jsonb,
            creado_por       INTEGER,
            creado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en   TIMESTAMPTZ,
            ultimo_error     TEXT,
            activo           BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS ix_formulario_destinos_encuesta
            ON formulario_destinos(encuesta_id) WHERE activo;
        CREATE INDEX IF NOT EXISTS ix_formulario_destinos_ruta
            ON formulario_destinos(destino_ruta) WHERE activo;
    """)
    _esquema_listo = True


# ── consultas ────────────────────────────────────────────────────────────
def obtener(destino_id):
    asegurar_esquema()
    filas = bd.consultar('SELECT * FROM formulario_destinos WHERE id = %s AND activo',
                         (int(destino_id),))
    return dict(filas[0]) if filas else None


def de_la_ruta(usuario, ruta):
    """Conexiones activas que escriben en este libro."""
    asegurar_esquema()
    return [dict(f) for f in bd.consultar(
        "SELECT * FROM formulario_destinos WHERE activo AND destino_ruta = %s "
        "AND (destino_usuario = %s OR destino_ruta LIKE '/unidades/%%') ORDER BY id",
        (ruta, int(usuario)))]


def del_formulario(encuesta_id):
    asegurar_esquema()
    return [dict(f) for f in bd.consultar(
        'SELECT * FROM formulario_destinos WHERE activo AND encuesta_id = %s ORDER BY id',
        (encuesta_id,))]


def crear(usuario, encuesta_id, ruta, hoja, filtro_pregunta, filtro_valor, solo_nuevas):
    asegurar_esquema()
    fila = bd.ejecutar(
        """INSERT INTO formulario_destinos (encuesta_id, destino_usuario, destino_ruta,
               destino_hoja, filtro_pregunta, filtro_valor, desde, creado_por)
           VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() END, %s) RETURNING *""",
        (encuesta_id, int(usuario), ruta, hoja, filtro_pregunta or None,
         filtro_valor if filtro_pregunta else None, bool(solo_nuevas), int(usuario)))
    _olvidar_sin_trabajo(usuario, ruta)
    return dict(fila)


def desactivar(destino_id):
    bd.ejecutar('UPDATE formulario_destinos SET activo = FALSE WHERE id = %s',
                (int(destino_id),))


def _anotar(d, escritas=None, provisionales=None, error=None):
    bd.ejecutar(
        'UPDATE formulario_destinos SET escritas = COALESCE(%s::jsonb, escritas), '
        'provisionales = COALESCE(%s::jsonb, provisionales), ultimo_error = %s, '
        'actualizado_en = NOW() WHERE id = %s',
        (json.dumps(sorted(escritas)) if escritas is not None else None,
         json.dumps(sorted(provisionales)) if provisionales is not None else None,
         (error or '')[:500] or None, d['id']))


def _olvidar_sin_trabajo(usuario, ruta):
    try:
        import vivo_sin_trabajo as sin_trabajo
        sin_trabajo.olvidar(usuario, ruta)
    except Exception:
        pass


# ── el formulario y sus respuestas ───────────────────────────────────────
def formulario(encuesta_id):
    """(fila de `encuestas`, definición) o (None, None)."""
    filas = bd.consultar('SELECT * FROM encuestas WHERE id = %s', (encuesta_id,))
    if not filas:
        return None, None
    from api_encuestas import leer_definicion
    fila = dict(filas[0])
    return fila, leer_definicion(int(fila['propietario']), fila['ruta'])


def _es_numero(pregunta):
    return (pregunta.get('tipo') in ('escala', 'calificacion') or
            (pregunta.get('validacion') or {}).get('clase') == 'numero')


def _numero(texto):
    try:
        limpio = str(texto).strip().replace(',', '.')
        return int(limpio) if limpio.lstrip('-').isdigit() else float(limpio)
    except (TypeError, ValueError):
        return texto


def cumple(filtro_pregunta, filtro_valor, listado, respuesta):
    """¿La respuesta pasa el filtro? En casillas basta con una de las marcadas."""
    if not filtro_pregunta:
        return True
    import encuestas_modelo as modelo
    pregunta = next((p for p in listado if p['id'] == filtro_pregunta), None)
    if pregunta is None:
        return False
    texto = modelo.texto_de(pregunta, (respuesta or {}).get(filtro_pregunta))
    buscado = normalizar(filtro_valor)
    return normalizar(texto) == buscado or buscado in {
        normalizar(t) for t in str(texto).split(',')}


def respuestas(fila, definicion, d):
    """Las respuestas que le tocan a esta conexión (filtro y «desde»), en orden:
    {cabeceras, listado, lista: [(id, celdas, enviada)]}."""
    import encuestas_hoja as hoja_mod
    datos = hoja_mod.datos_de_hoja(fila, definicion)
    cabeceras, listado = datos['cabeceras'], datos['listado']
    desplazamiento = len(cabeceras) - len(listado)
    numericas = {desplazamiento + i for i, p in enumerate(listado) if _es_numero(p)}
    lista = []
    for id_, celdas, enviada, respuesta in zip(datos['ids'], datos['cuerpo'],
                                               datos['enviadas'], datos['respuestas']):
        if d.get('desde') and enviada and enviada < d['desde']:
            continue
        if not cumple(d.get('filtro_pregunta'), d.get('filtro_valor'), listado, respuesta):
            continue
        celdas = [_numero(v) if i in numericas and v not in (None, '') else v
                  for i, v in enumerate(celdas)]
        lista.append((id_, celdas, enviada))
    return {'cabeceras': cabeceras, 'listado': listado, 'lista': lista}


def mapa_columnas(encabezados, cabeceras, n_fijas):
    """{índice de columna de la hoja: índice en la fila del formulario}."""
    mapa, normales = {}, [normalizar(e) for e in encabezados]
    for j, cabecera in enumerate(cabeceras):
        if j < n_fijas:     # «Fecha», «Quién»…: solo si el encabezado es exactamente ese
            i = normales.index(normalizar(cabecera)) if normalizar(cabecera) in normales else None
        else:
            i = _columna_de_cabecera(encabezados, cabecera)
        if i is not None and i not in mapa:
            mapa[i] = j
    return mapa


def _instante(enviada):
    return enviada.replace(tzinfo=None, microsecond=0) if enviada else None


def _fechas_en_disco(d, cabeceras):
    """Fechas que ya están en la columna «Fecha» del libro guardado (None si no
    tiene esa columna o no se puede leer)."""
    import nucleo_archivos as nucleo
    try:
        contenido = open(nucleo.ruta_fisica(int(d['destino_usuario']), d['destino_ruta']),
                         'rb').read()
        return lugar_mod.fechas_presentes(
            lugar_mod.localizar(contenido, d['destino_hoja'], cabeceras))
    except Exception as excepcion:
        log.info('destino %s: no se pudo leer el libro (%s)', d['id'], excepcion)
        return None


def pendientes(d, datos, fechas, extra_hechas=()):
    """Las respuestas de `datos` que aún no están en el libro."""
    hechas = set(d.get('escritas') or []) | set(extra_hechas)
    return [(i, c, e) for i, c, e in datos['lista']
            if i not in hechas and not (fechas and _instante(e) in fechas)]


# ── escribir con el libro cerrado ────────────────────────────────────────
def escribir(d):
    """Añade al libro las respuestas que faltan. Devuelve (n escritas, aviso)."""
    import encuestas_hoja as hoja_mod
    import encuestas_hoja_xml as xml_mod
    import nucleo_archivos as nucleo
    usuario, ruta = int(d['destino_usuario']), d['destino_ruta']
    dentro = hoja_mod._sala_ocupada(usuario, ruta)
    if dentro is None or dentro:
        return 0, 'abierto'
    fila, definicion = formulario(d['encuesta_id'])
    if definicion is None:
        _anotar(d, error='El formulario ya no existe')
        return 0, 'El formulario ya no existe'
    datos = respuestas(fila, definicion, d)
    contenido = open(nucleo.ruta_fisica(usuario, ruta), 'rb').read()
    lugar = lugar_mod.localizar(contenido, d['destino_hoja'], datos['cabeceras'])
    fechas = lugar_mod.fechas_presentes(lugar)
    ya = {i for i, _, e in datos['lista'] if fechas and _instante(e) in fechas}
    escritas = set(d.get('escritas') or []) | ya
    # Lo que el complemento escribió con el libro abierto: si hay columna
    # «Fecha», ella dice qué quedó guardado de verdad; si no, se confía.
    if d.get('provisionales') and fechas is None:
        escritas |= set(d['provisionales'])
    d['escritas'] = sorted(escritas)
    faltan = pendientes(d, datos, fechas)
    if not faltan:
        _anotar(d, escritas=escritas, provisionales=[])
        return 0, ''

    n_fijas = len(datos['cabeceras']) - len(datos['listado'])
    mapa = mapa_columnas(lugar['encabezados'], datos['cabeceras'], n_fijas)
    ancho = lugar['c2'] - lugar['c1'] + 1
    filas = [[(c[mapa[i]] if c[mapa[i]] is not None else '') if i in mapa else None
              for i in range(ancho)] for _, c, _ in faltan]
    lugar['columnas_clave'] = [lugar['c1'] + i for i in mapa]
    nuevo = xml_mod.anadir_filas(contenido, filas, destino=lugar)

    carpeta, _, nombre = ruta.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre, io.BytesIO(nuevo))
    import encuestas_hoja_recalculo as recalculo
    calculado = recalculo.recalcular(usuario, ruta)
    if calculado:
        nucleo.subir(usuario, carpeta or '/', nombre, io.BytesIO(calculado))
    try:
        from api_onlyoffice import invalidar_cache
        invalidar_cache(usuario, ruta)
    except Exception as excepcion:
        log.warning('destino %s: no se pudo refrescar el editor (%s)', d['id'], excepcion)
    if hoja_mod._sala_ocupada(usuario, ruta):
        # Alguien entró mientras se escribía: su guardado puede pisarlo. No se
        # anota; al cerrar se mira la columna «Fecha» y se repone lo que falte.
        return len(faltan), 'abierto'
    _anotar(d, escritas=escritas | {i for i, _, _ in faltan}, provisionales=[])
    log.info('destino %s (%s): %d respuestas añadidas', d['id'], ruta, len(faltan))
    return len(faltan), ''


def escribir_en_segundo_plano(d):
    with _candado:
        if d['id'] in _en_marcha:
            return
        _en_marcha.add(d['id'])

    def trabajo():
        try:
            escribir(d)
        except Exception as excepcion:
            log.warning('destino %s: %s', d['id'], excepcion)
            try:
                _anotar(d, error=str(excepcion))
            except Exception:
                pass
        finally:
            with _candado:
                _en_marcha.discard(d['id'])
    threading.Thread(target=trabajo, name='destino-%s' % d['id'], daemon=True).start()


# ── enganches ────────────────────────────────────────────────────────────
def al_llegar_respuesta(encuesta_id):
    """Nunca lanza."""
    try:
        for d in del_formulario(encuesta_id):
            _olvidar_sin_trabajo(d['destino_usuario'], d['destino_ruta'])
            escribir_en_segundo_plano(d)
    except Exception as excepcion:
        log.warning('destinos de %s: %s', encuesta_id, excepcion)


def al_cerrar(usuario, ruta):
    """Se cerró el libro: se escribe lo que falte (y se resuelve lo provisional
    contra la columna «Fecha», en `escribir`). Nunca lanza."""
    try:
        for d in de_la_ruta(usuario, ruta):
            escribir_en_segundo_plano(d)
    except Exception as excepcion:
        log.warning('destinos al cerrar %s: %s', ruta, excepcion)


# ── con el libro abierto (lo pide `encuestas_vivo`) ──────────────────────
def vivo_hojas(usuario, ruta):
    salida = []
    for d in de_la_ruta(usuario, ruta):
        try:
            fila, definicion = formulario(d['encuesta_id'])
            if definicion is None:
                continue
            datos = respuestas(fila, definicion, d)
            faltan = pendientes(d, datos, _fechas_en_disco(d, datos['cabeceras']),
                                d.get('provisionales') or [])
            if faltan:
                salida.append({'encuesta_id': PREFIJO_VIVO + str(d['id']),
                               'titulo': fila.get('titulo') or '',
                               'hoja': d['destino_hoja'], 'pendientes': len(faltan)})
        except Exception as excepcion:
            log.warning('vivo destino %s: %s', d['id'], excepcion)
    return salida


def _del_libro(usuario, ruta, clave):
    try:
        destino_id = int(str(clave)[len(PREFIJO_VIVO):])
    except ValueError:
        return None
    return next((d for d in de_la_ruta(usuario, ruta) if d['id'] == destino_id), None)


def vivo_filas(usuario, ruta, clave, encabezados):
    """Filas colocadas en las columnas que el editor tiene ahora."""
    import encuestas_vivo as vivo
    d = _del_libro(usuario, ruta, clave)
    if not d:
        return None
    fila, definicion = formulario(d['encuesta_id'])
    if definicion is None:
        return None
    datos = respuestas(fila, definicion, d)
    faltan = pendientes(d, datos, _fechas_en_disco(d, datos['cabeceras']),
                        d.get('provisionales') or [])
    n_fijas = len(datos['cabeceras']) - len(datos['listado'])
    mapa = mapa_columnas(encabezados, datos['cabeceras'], n_fijas)
    if not faltan or not mapa:
        return {'filas': [], 'columnas': [], 'renombres': [], 'hasta': ''}
    filas = [[vivo._celda(c[mapa[i]]) if i in mapa else None
              for i in range(len(encabezados))] for _, c, _ in faltan]
    return {'filas': filas, 'columnas': [], 'renombres': [],
            'hasta': 'ids:' + ','.join(str(i) for i, _, _ in faltan)}


def vivo_confirmar(usuario, ruta, clave, hasta):
    d = _del_libro(usuario, ruta, clave)
    if not d or not str(hasta).startswith('ids:'):
        return False
    ids = {int(x) for x in str(hasta)[4:].split(',') if x.strip().isdigit()}
    _anotar(d, provisionales=set(d.get('provisionales') or []) | ids)
    log.info('destino %s: %d filas escritas en el editor abierto', d['id'], len(ids))
    return True
