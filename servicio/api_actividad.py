# -*- coding: utf-8 -*-
"""
API de ACTIVIDAD y COMENTARIOS del Almacén Maquita.
===================================================
Actividad reciente (quién hizo qué) y comentarios en archivos — dos funciones
de colaboración estilo Google Drive.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.actividad')

bp_actividad = Blueprint('almacen_actividad', __name__)

# Textos legibles para cada acción (para la UI)
_ACCION_TEXTO = {
    'subio': 'subió', 'elimino': 'envió a la papelera', 'renombro': 'renombró',
    'movio': 'movió', 'copio': 'copió', 'compartio': 'compartió',
    'restauro': 'restauró', 'comento': 'comentó', 'creo_carpeta': 'creó la carpeta',
    'acceso_directo': 'creó un acceso directo',
}


def _nombre_usuario(usuario_id):
    """Nombre legible del autor (de nómina). Cacheado en la propia consulta."""
    filas = consultar("""
        SELECT COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.id = %s
    """, (usuario_id,), nomina=True)
    return filas[0]['nombre'] if filas else f'Usuario {usuario_id}'


def _serializar(filas):
    nombres = {}
    out = []
    for f in filas:
        uid = f['usuario_id']
        if uid not in nombres:
            nombres[uid] = _nombre_usuario(uid)
        out.append({
            'id': f['id'], 'usuario': nombres[uid],
            'accion': f['accion'], 'accion_texto': _ACCION_TEXTO.get(f['accion'], f['accion']),
            'ruta': f['ruta'], 'detalle': f['detalle'],
            'creado_en': f['creado_en'].isoformat(),
        })
    return out


@bp_actividad.route('/actividad', methods=['GET'])
def mi_actividad():
    """GET /actividad — mis últimas acciones (Actividad reciente)."""
    usuario = usuario_actual()
    filas = consultar("""
        SELECT id, usuario_id, accion, ruta, detalle, creado_en
        FROM actividad WHERE usuario_id = %s ORDER BY creado_en DESC LIMIT 60
    """, (usuario,))
    return jsonify({'success': True, 'actividad': _serializar(filas), 'total': len(filas)})


@bp_actividad.route('/actividad/<int:actividad_id>/deshacer', methods=['POST'])
def deshacer_actividad(actividad_id):
    """
    POST /actividad/<id>/deshacer — deshace una acción de la actividad.
    Hoy soporta DESHACER BORRADOS: busca el elemento en la papelera (o en la retención
    si el usuario ya la vació) por su ruta original y lo restaura a su sitio.
    """
    import os
    import nucleo_archivos as nucleo
    from seguridad_rutas import ruta_fisica, RutaInvalida
    usuario = usuario_actual()
    fila = consultar("SELECT accion, ruta, detalle FROM actividad WHERE id = %s AND usuario_id = %s",
                     (actividad_id, usuario))
    if not fila:
        return error('Acción no encontrada', 404)
    accion, ruta, detalle = fila[0]['accion'], fila[0]['ruta'], fila[0]['detalle']

    # ── Deshacer MOVER o RENOMBRAR: devolver el elemento a su ruta original ──
    if accion in ('movio', 'renombro'):
        origen_actual = ruta       # dónde quedó (destino/nuevo nombre)
        ruta_original = detalle    # dónde estaba antes (se guardó en la actividad)
        if not ruta_original:
            return error('No hay ruta original para deshacer', 400)
        try:
            if not os.path.exists(ruta_fisica(usuario, origen_actual)):
                return error('El elemento ya no está ahí (se volvió a cambiar). No se puede deshacer.', 409)
            if os.path.exists(ruta_fisica(usuario, ruta_original)):
                return error('Ya existe algo en la ruta original. No se puede deshacer sin sobrescribir.', 409)
            nucleo.mover(usuario, origen_actual, ruta_original)
        except RutaInvalida as e:
            return error(str(e), 400)
        except FileNotFoundError:
            return error('El elemento ya no está disponible', 404)
        registrar_actividad(usuario, 'movio', ruta_original, origen_actual)
        verbo = 'renombrado' if accion == 'renombro' else 'movido'
        return jsonify({'success': True, 'ruta_restaurada': ruta_original,
                        'message': f'Deshecho: el elemento volvió a su sitio ({verbo})'})

    if accion != 'elimino':
        return error('Esta acción no se puede deshacer', 400)

    # 1) ¿sigue en la papelera? (lo más reciente con esa ruta original)
    pap = consultar("""
        SELECT nombre_fisico FROM papelera
        WHERE usuario_id = %s AND ruta_original = %s ORDER BY eliminado_en DESC LIMIT 1
    """, (usuario, ruta))
    try:
        if pap:
            restaurada = nucleo.restaurar_de_papelera(usuario, pap[0]['nombre_fisico'])
        else:
            # 2) ¿está en la retención? (papelera ya vaciada)
            ret = consultar("""
                SELECT nombre_fisico FROM retencion
                WHERE usuario_id = %s AND ruta_original = %s
                ORDER BY eliminado_definitivo_en DESC LIMIT 1
            """, (usuario, ruta))
            if not ret:
                return error('Ya no se puede recuperar (no está en papelera ni retención)', 404)
            restaurada = nucleo.restaurar_de_retencion(usuario, ret[0]['nombre_fisico'])
    except FileNotFoundError:
        return error('El elemento ya no está disponible', 404)

    registrar_actividad(usuario, 'restauro', restaurada, 'deshacer borrado')
    return jsonify({'success': True, 'ruta_restaurada': restaurada,
                    'message': 'Borrado deshecho: el elemento volvió a su sitio'})


@bp_actividad.route('/archivos/actividad', methods=['GET'])
def actividad_archivo():
    """GET /archivos/actividad?ruta= — actividad de un archivo/carpeta puntual."""
    usuario_actual()
    ruta = request.args.get('ruta', '')
    filas = consultar("""
        SELECT id, usuario_id, accion, ruta, detalle, creado_en
        FROM actividad WHERE ruta = %s ORDER BY creado_en DESC LIMIT 60
    """, (ruta,))
    return jsonify({'success': True, 'actividad': _serializar(filas), 'total': len(filas)})


# ── Comentarios ──────────────────────────────────────────────────────────
@bp_actividad.route('/archivos/comentarios', methods=['GET'])
def listar_comentarios():
    """GET /archivos/comentarios?ruta= — comentarios de un archivo/carpeta."""
    usuario = usuario_actual()
    ruta = request.args.get('ruta', '')
    # Quien no puede ver el archivo, no ve sus comentarios.
    from permisos_accion import puede_leer
    if not puede_leer(usuario, ruta):
        return jsonify({'success': True, 'comentarios': [], 'total': 0})
    filas = consultar("""
        SELECT id, usuario_id, texto, creado_en
        FROM comentarios WHERE ruta = %s ORDER BY creado_en
    """, (ruta,))
    nombres = {}
    coment = []
    for f in filas:
        uid = f['usuario_id']
        if uid not in nombres:
            nombres[uid] = _nombre_usuario(uid)
        coment.append({'id': f['id'], 'usuario': nombres[uid], 'usuario_id': uid,
                       'texto': f['texto'], 'creado_en': f['creado_en'].isoformat()})
    return jsonify({'success': True, 'comentarios': coment, 'total': len(coment)})


@bp_actividad.route('/archivos/comentarios', methods=['POST'])
def crear_comentario():
    """POST /archivos/comentarios — {ruta, texto}."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as e:
        return error(str(e), 400)
    texto = (datos.get('texto') or '').strip()
    if not texto:
        return error('El comentario está vacío', 400)
    if ruta == '/':
        return error('Ruta inválida', 400)
    # Comentar en algo que no se puede ni ver dejaba rastro en la actividad
    # de una unidad ajena.
    from permisos_accion import puede_escribir, MOTIVO_LECTOR
    if not puede_escribir(usuario, ruta):
        return error(MOTIVO_LECTOR, 403)
    fila = ejecutar("""
        INSERT INTO comentarios (usuario_id, ruta, texto) VALUES (%s, %s, %s)
        RETURNING id, creado_en
    """, (usuario, ruta, texto[:2000]))
    registrar_actividad(usuario, 'comento', ruta, texto[:80])
    return jsonify({'success': True, 'id': fila['id'],
                    'creado_en': fila['creado_en'].isoformat()}), 201


@bp_actividad.route('/archivos/comentarios/<int:comentario_id>', methods=['DELETE'])
def eliminar_comentario(comentario_id):
    """DELETE /archivos/comentarios/<id> — borra un comentario propio."""
    usuario = usuario_actual()
    fila = ejecutar("""
        DELETE FROM comentarios WHERE id = %s AND usuario_id = %s RETURNING id
    """, (comentario_id, usuario))
    if not fila:
        return error('Comentario no encontrado o no es tuyo', 404)
    return jsonify({'success': True})
