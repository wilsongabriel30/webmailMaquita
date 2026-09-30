# -*- coding: utf-8 -*-
"""
Papelera de RESPUESTAS de formularios (Drive Maquita).

Por qué existe: «Eliminar todas las respuestas» hacía un DELETE sin copia. El
21/09/2026 se vaciaron así las respuestas de «prueba IFO» y solo se pudieron
recuperar porque seguían en el Excel. Ahora, antes de borrar, cada respuesta
se guarda entera aquí (la fila tal cual, en JSONB) y se puede devolver.

Cada borrado es un «lote»: todas las respuestas que se fueron de una vez. Un
lote se restaura completo, con sus ids originales, así que la hoja de cálculo
y los enlaces de edición siguen cuadrando.

Rutas (montadas sobre bp_encuestas, mismo prefijo /api/almacen):
  GET  /encuestas/respuestas/papelera?ruta=X.forma   → {lotes: [...]}
  POST /encuestas/respuestas/restaurar?ruta=X.forma  {lote} → {restauradas}

Los lotes se guardan DIAS_RETENCION días y luego se purgan solos.

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import logging
import uuid

from flask import jsonify, request

import almacen_bd as bd

log = logging.getLogger('almacen.encuestas.papelera')

DIAS_RETENCION = 90

_esquema_listo = False


def asegurar_esquema():
    """Crea la tabla de la papelera si no existe. Idempotente.

    Sin clave foránea a `encuestas` a propósito: si se borra el formulario,
    la copia de sus respuestas debe sobrevivir.
    """
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS encuesta_respuestas_borradas (
            id           SERIAL PRIMARY KEY,
            lote         TEXT NOT NULL,
            encuesta_id  TEXT NOT NULL,
            respuesta_id INTEGER NOT NULL,
            fila         JSONB NOT NULL,
            borrada_por  INTEGER,
            borrada_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_resp_borradas_encuesta
            ON encuesta_respuestas_borradas(encuesta_id, borrada_en DESC);
    """)
    _esquema_listo = True


def _avisar_hoja(encuesta_id, cuantas):
    """La hoja de respuestas refleja el borrado o la recuperación."""
    if not cuantas:
        return
    try:
        import encuestas_hoja
        encuestas_hoja.al_cambiar_respuestas(encuesta_id)
    except Exception as excepcion:
        log.warning('papelera de %s: no se pudo avisar a la hoja (%s)',
                    encuesta_id, excepcion)


def mover_a_papelera(encuesta_id, usuario_id, respuesta_id=None):
    """Borra respuestas guardando antes su copia. Devuelve (lote, cuántas).

    Copia y borrado van en UNA sola sentencia (CTE): o se hacen las dos o
    ninguna, así nunca queda una respuesta borrada sin copia.
    """
    asegurar_esquema()
    lote = uuid.uuid4().hex[:16]
    filtro = 'encuesta_id = %s'
    parametros = [encuesta_id]
    if respuesta_id is not None:
        filtro += ' AND id = %s'
        parametros.append(int(respuesta_id))
    filas = bd.consultar(f"""
        WITH borradas AS (
            DELETE FROM encuesta_respuestas WHERE {filtro} RETURNING *
        )
        INSERT INTO encuesta_respuestas_borradas
            (lote, encuesta_id, respuesta_id, fila, borrada_por)
        SELECT %s, b.encuesta_id, b.id, to_jsonb(b), %s FROM borradas b
        RETURNING respuesta_id
    """, (*parametros, lote, usuario_id))
    _purgar_viejos()
    _avisar_hoja(encuesta_id, len(filas))
    return lote, len(filas)


def _purgar_viejos():
    try:
        bd.ejecutar(
            'DELETE FROM encuesta_respuestas_borradas '
            "WHERE borrada_en < NOW() - (%s || ' days')::interval",
            (str(DIAS_RETENCION),))
    except Exception as exc:   # purgar es limpieza: nunca debe tumbar el borrado
        log.warning('No se pudo purgar la papelera de respuestas: %s', exc)


def lotes(encuesta_id):
    """Lotes borrados de ese formulario, del más reciente al más antiguo."""
    asegurar_esquema()
    return bd.consultar("""
        SELECT lote, COUNT(*)::int AS cuantas, MIN(borrada_en) AS borrada_en,
               MIN(borrada_por) AS borrada_por
        FROM encuesta_respuestas_borradas
        WHERE encuesta_id = %s
        GROUP BY lote
        ORDER BY MIN(borrada_en) DESC
    """, (encuesta_id,))


def restaurar(encuesta_id, lote):
    """Devuelve un lote completo a las respuestas. Devuelve cuántas volvieron.

    Se reinsertan con su id original (ON CONFLICT: si alguna ya estuviera, no
    se duplica) y el lote sale de la papelera en la misma transacción.
    """
    asegurar_esquema()
    filas = bd.consultar("""
        WITH lote AS (
            DELETE FROM encuesta_respuestas_borradas
            WHERE encuesta_id = %s AND lote = %s
            RETURNING fila
        )
        INSERT INTO encuesta_respuestas
        SELECT (jsonb_populate_record(NULL::encuesta_respuestas, l.fila)).*
        FROM lote l
        ON CONFLICT (id) DO NOTHING
        RETURNING id
    """, (encuesta_id, lote))
    _avisar_hoja(encuesta_id, len(filas))
    return len(filas)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
def registrar_rutas(bp, abrir, sincronizar, limpiar, error, nombres_usuarios):
    """Monta las rutas sobre el blueprint de formularios.

    Recibe las utilidades de api_encuestas en vez de importarlas, para no
    crear una importación circular.
    """

    @bp.route('/encuestas/respuestas/papelera', methods=['GET'])
    def papelera_respuestas():
        datos, fallo = abrir(escritura=True)
        if fallo:
            return fallo
        usuario, ruta, definicion = datos
        definicion = limpiar(definicion)
        sincronizar(usuario, ruta, definicion)
        lista = lotes(definicion['id'])
        nombres = nombres_usuarios([l['borrada_por'] for l in lista])
        return jsonify({'success': True, 'dias': DIAS_RETENCION, 'lotes': [{
            'lote': l['lote'],
            'cuantas': l['cuantas'],
            'borrada_en': l['borrada_en'].isoformat(),
            'borrada_por': nombres.get(l['borrada_por'], ''),
        } for l in lista]})

    @bp.route('/encuestas/respuestas/restaurar', methods=['POST'])
    def restaurar_respuestas():
        datos, fallo = abrir(escritura=True)
        if fallo:
            return fallo
        usuario, ruta, definicion = datos
        definicion = limpiar(definicion)
        sincronizar(usuario, ruta, definicion)
        lote = str((request.get_json(silent=True) or {}).get('lote') or '')
        if not lote:
            return error('Falta indicar qué borrado recuperar', 400)
        cuantas = restaurar(definicion['id'], lote)
        if not cuantas:
            return error('Ese borrado ya no está en la papelera', 404)
        log.info('Formulario %s: %s respuestas restauradas (lote %s) por %s',
                 ruta, cuantas, lote, usuario)
        return jsonify({'success': True, 'restauradas': cuantas})
