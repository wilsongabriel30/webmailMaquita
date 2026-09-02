# -*- coding: utf-8 -*-
"""
API de UNIDADES COMPARTIDAS del Almacén Maquita.
================================================
Drives de equipo, propiedad de la ORGANIZACIÓN (no de una persona), con miembros
y roles — el equivalente a las "Unidades compartidas" de Google Drive / SharePoint
(que Drive cobra desde Business Standard). Aquí, gratis.

Roles: manager (gestiona miembros y todo), editor (sube/edita/borra), viewer (solo ve).

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import json
import logging
import os
import shutil
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar, es_master
from api_archivos import error, usuario_actual
from config_almacen import raiz_datos
from registro import registrar_actividad
from seguridad_rutas import unidad_de_ruta
import nucleo_archivos as nucleo

log = logging.getLogger('almacen.unidades')

bp_unidades = Blueprint('almacen_unidades', __name__)

ROLES = ('manager', 'editor', 'viewer')

# Papelera de unidades: al eliminar una unidad, sus archivos y un manifiesto
# (nombre, miembros, permisos) quedan archivados aquí. Son recuperables durante
# DIAS_RETENCION; un timer (almacen-purga-unidades) borra lo que pase de ese
# plazo. Así un borrado por error se puede deshacer, pero no se acumula para
# siempre. Regla de oro: mientras esté en la papelera, no se pierde nada.
DIAS_RETENCION = 90


def _dir_eliminadas():
    return os.path.join(raiz_datos(), '_unidades', '_eliminadas')


# La regla vive en `roles_unidad`, que no importa Flask: la necesitan tanto
# FARO como el servicio WebDAV, que corre aparte. Aquí se reexporta para que
# todo lo que ya la llamaba siga igual.
from roles_unidad import rol_en_unidad          # noqa: F401,E402


def permiso_unidad(usuario_id, ruta, escritura=False):
    """¿Puede el usuario leer (o escribir) esta ruta si es de una unidad compartida?
    Devuelve True/False. Para rutas personales devuelve True (no aplica)."""
    unidad_id, sub = unidad_de_ruta(ruta)
    if unidad_id is None:
        return True   # ruta personal: la seguridad personal ya aplica
    # El rol puede venir AMPLIADO por una concesión sobre esta carpeta o sobre
    # una superior (modelo ampliativo, como las Unidades compartidas de Google).
    # Ante cualquier fallo se cae al rol de unidad de siempre: nunca se abre
    # más de lo que ya estaba abierto.
    try:
        from permisos_unidad_carpeta import rol_efectivo
        rol = rol_efectivo(usuario_id, unidad_id, sub)
    except Exception as excepcion:
        log.warning('rol_efectivo falló (se usa el rol de unidad): %s', excepcion)
        rol = rol_en_unidad(usuario_id, unidad_id)
    if rol is None:
        return False
    if escritura and rol == 'viewer':
        return False
    return True


@bp_unidades.route('/unidades', methods=['GET'])
def listar_unidades():
    """GET /unidades — unidades compartidas donde soy miembro (con mi rol)."""
    usuario = usuario_actual()
    filas = consultar("""
        SELECT u.id, u.nombre, u.creado_en, m.rol,
               (SELECT COUNT(*) FROM unidad_miembros mm WHERE mm.unidad_id = u.id) AS miembros
        FROM unidades_compartidas u
        JOIN unidad_miembros m ON m.unidad_id = u.id
        WHERE m.usuario_id = %s
        ORDER BY u.nombre
    """, (usuario,))
    return jsonify({'success': True, 'unidades': [{
        'id': f['id'], 'nombre': f['nombre'], 'mi_rol': f['rol'],
        'miembros': f['miembros'], 'ruta': f'/unidades/{f["id"]}',
        'creado_en': f['creado_en'].isoformat(),
    } for f in filas]})


@bp_unidades.route('/unidades', methods=['POST'])
def crear_unidad():
    """POST /unidades — {nombre} : crea una unidad compartida (solo master). El creador
    queda como manager."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un master puede crear unidades compartidas', 403)
    datos = request.get_json() or {}
    nombre = (datos.get('nombre') or '').strip()[:150]
    if not nombre:
        return error('Nombre requerido', 400)
    fila = ejecutar("INSERT INTO unidades_compartidas (nombre, creado_por) VALUES (%s, %s) RETURNING id",
                    (nombre, usuario))
    ejecutar("INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) VALUES (%s, %s, 'manager')",
             (fila['id'], usuario))
    registrar_actividad(usuario, 'creo_carpeta', f'/unidades/{fila["id"]}', f'Unidad: {nombre}')
    return jsonify({'success': True, 'id': fila['id'], 'nombre': nombre,
                    'ruta': f'/unidades/{fila["id"]}'}), 201


@bp_unidades.route('/unidades/<int:unidad_id>/miembros', methods=['GET'])
def listar_miembros(unidad_id):
    """GET — miembros de la unidad (cualquier miembro puede ver la lista)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) is None:
        return error('No eres miembro de esta unidad', 403)
    # Dos consultas: la membresía vive en la BD del almacén y los nombres en el
    # directorio (otra BD) — no se pueden JOINear entre bases en PostgreSQL.
    membresia = consultar("""
        SELECT usuario_id, rol FROM unidad_miembros WHERE unidad_id = %s
    """, (unidad_id,))
    if not membresia:
        return jsonify({'success': True, 'miembros': []})
    ids = tuple({int(m['usuario_id']) for m in membresia})
    personas = consultar("""
        SELECT u.id, u.username,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.id IN %s
    """, (ids,), nomina=True)
    por_id = {p['id']: p for p in personas}
    miembros = [{
        'usuario_id': m['usuario_id'], 'rol': m['rol'],
        'nombre': (por_id.get(m['usuario_id']) or {}).get('nombre') or f"Usuario {m['usuario_id']}",
        'username': (por_id.get(m['usuario_id']) or {}).get('username') or '',
    } for m in membresia]
    miembros.sort(key=lambda x: (x['rol'], x['nombre'].lower()))
    return jsonify({'success': True, 'miembros': miembros})


@bp_unidades.route('/unidades/<int:unidad_id>/buscar-personas', methods=['GET'])
def buscar_personas_unidad(unidad_id):
    """GET ?q= — busca personas para agregar a la unidad. Lo puede usar el
    MANAGER de la unidad aunque NO sea master de FARO: es el buscador de la
    gestion DELEGADA, para no obligar a pasar por el panel de administracion
    (que expone herramientas tecnicas peligrosas)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un administrador de esta unidad puede gestionar sus miembros', 403)
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'success': True, 'usuarios': []})
    filas = consultar("""
        SELECT u.id, u.username,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
          AND (unaccent(LOWER(u.username)) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.nombres, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.apellidos, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(u.full_name, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR LOWER(COALESCE(u.email, '')) LIKE '%%' || LOWER(%s) || '%%')
        ORDER BY
          (unaccent(LOWER(COALESCE(t.apellidos, u.username))) LIKE unaccent(LOWER(%s)) || '%%') DESC,
          u.username
        LIMIT 25
    """, (q, q, q, q, q, q), nomina=True)
    return jsonify({'success': True, 'usuarios': [
        {'id': f['id'], 'username': f['username'], 'nombre': f['nombre']}
        for f in filas]})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros', methods=['POST'])
def agregar_miembro(unidad_id):
    """POST — {usuario_id, rol} : agrega/actualiza un miembro (solo manager/master)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    datos = request.get_json() or {}
    nuevo = datos.get('usuario_id')
    # Por defecto SOLO LECTURA (12/08/2026): la edición se concede por carpeta.
    rol = (datos.get('rol') or 'viewer').strip()
    if not nuevo or rol not in ROLES:
        return error('usuario_id y rol válido requeridos', 400)
    # Un ADMINISTRADOR de unidad no degrada a otro administrador: eso es de
    # los superadministradores (master) — regla de Wilson, 12/08/2026.
    from almacen_bd import es_master
    actual = consultar(
        'SELECT rol FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s',
        (unidad_id, int(nuevo)))
    if (actual and actual[0]['rol'] == 'manager' and rol != 'manager'
            and not es_master(usuario)):
        return error('Solo un superadministrador puede cambiar el rol de un '
                     'administrador de la unidad', 403)
    ejecutar("""
        INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) VALUES (%s, %s, %s)
        ON CONFLICT (unidad_id, usuario_id) DO UPDATE SET rol = EXCLUDED.rol
    """, (unidad_id, int(nuevo), rol))
    return jsonify({'success': True, 'message': 'Miembro agregado'})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros/<int:miembro_id>', methods=['DELETE'])
def quitar_miembro(unidad_id, miembro_id):
    """DELETE — quita un miembro (solo manager/master). A un ADMINISTRADOR
    solo lo quita un superadministrador (master) — 12/08/2026."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    from almacen_bd import es_master
    fila = consultar(
        'SELECT rol FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s',
        (unidad_id, miembro_id))
    if fila and fila[0]['rol'] == 'manager' and not es_master(usuario):
        return error('Solo un superadministrador puede quitar a un '
                     'administrador de la unidad', 403)
    ejecutar("DELETE FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s",
             (unidad_id, miembro_id))
    return jsonify({'success': True, 'message': 'Miembro removido'})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros/todos', methods=['POST'])
def agregar_todos(unidad_id):
    """POST — da acceso de SOLO LECTURA a todo el personal activo de una vez.

    Es la opción «como el Workspace»: documentación oficial que todos ven pero
    pocos editan. Se agregan como 'viewer' y con ON CONFLICT DO NOTHING, para
    NO pisar a quien ya sea editor o manager: dar acceso masivo no debe degradar
    permisos concedidos a mano.
    """
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    filas = consultar("SELECT id FROM usuarios WHERE active = TRUE", nomina=True)
    ids = [f['id'] for f in filas]
    for uid in ids:
        ejecutar("""
            INSERT INTO unidad_miembros (unidad_id, usuario_id, rol)
            VALUES (%s, %s, 'viewer')
            ON CONFLICT (unidad_id, usuario_id) DO NOTHING
        """, (unidad_id, int(uid)))
    return jsonify({'success': True,
                    'message': 'Acceso de solo lectura para todo el personal (%d)'
                               % len(ids), 'total': len(ids)})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros/solo-lectores', methods=['DELETE'])
def quitar_lectores(unidad_id):
    """DELETE — quita a TODOS los que solo tienen lectura ('viewer').

    El reverso del botón anterior. NO toca a editores ni managers: revierte el
    acceso masivo sin tocar los permisos concedidos a mano.
    """
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    ejecutar("DELETE FROM unidad_miembros WHERE unidad_id = %s AND rol = 'viewer'",
             (unidad_id,))
    return jsonify({'success': True, 'message': 'Acceso general retirado'})


def _mis_concesiones(usuario_id, unidad_id):
    """Concesiones por carpeta del propio usuario en una unidad. Nunca lanza."""
    try:
        filas = consultar(
            'SELECT ruta, rol FROM unidad_permisos_carpeta '
            'WHERE unidad_id = %s AND usuario_id = %s',
            (int(unidad_id), int(usuario_id)))
        return [{'ruta': f['ruta'], 'rol': f['rol']} for f in filas]
    except Exception:
        return []


@bp_unidades.route('/mi-permiso', methods=['GET'])
def mi_permiso():
    """GET /mi-permiso?ruta=/unidades/5/Contabilidad — rol efectivo del usuario.

    Lo usa el explorador para mostrar en pantalla con qué permiso estás viendo
    una carpeta de una unidad, que es información que antes no se veía en
    ninguna parte. Cualquier usuario puede consultar EL SUYO.
    """
    usuario = usuario_actual()
    ruta = request.args.get('ruta') or '/'
    unidad_id, sub = unidad_de_ruta(ruta)
    if unidad_id is None:
        return jsonify({'success': True, 'es_unidad': False})
    de_unidad = rol_en_unidad(usuario, unidad_id)
    try:
        from permisos_unidad_carpeta import rol_efectivo, rol_en_carpeta
        efectivo = rol_efectivo(usuario, unidad_id, sub)
        de_carpeta = rol_en_carpeta(usuario, unidad_id, sub)
    except Exception:
        efectivo, de_carpeta = de_unidad, None
    return jsonify({
        'success': True,
        'es_unidad': True,
        'unidad_id': unidad_id,
        'rol_unidad': de_unidad,
        'rol_carpeta': de_carpeta,
        'rol_efectivo': efectivo,
        # True cuando el permiso viene AMPLIADO por una concesión de carpeta.
        'ampliado': bool(de_carpeta) and de_carpeta != de_unidad,
        # TODAS las concesiones del usuario en esta unidad. Se envían de una vez
        # para que el explorador pueda marcar cada subcarpeta sin hacer una
        # consulta por fila: son pocas y el cálculo del rol efectivo es trivial.
        'concesiones': _mis_concesiones(usuario, unidad_id),
        # El veredicto de MOVER lo da el servidor, no la pantalla: asi la regla
        # vive en un solo sitio (permisos_mover.py) y el explorador no tiene que
        # reimplementarla ni quedarse desfasado cuando cambie.
        'puede_mover': _puede_mover_aqui(usuario, ruta),
    })


def _puede_mover_aqui(usuario_id, ruta):
    try:
        from permisos_mover import puede_mover
        return bool(puede_mover(usuario_id, ruta))
    except Exception:
        return False


@bp_unidades.route('/unidades/<int:unidad_id>/permisos-carpeta', methods=['GET'])
def listar_permisos_carpeta(unidad_id):
    """GET [?ruta=/Contabilidad] — concesiones por carpeta (solo manager/master).

    Modelo AMPLIATIVO: una concesión solo SUBE el nivel que ya se tiene en la
    unidad, nunca lo baja. Para quitar acceso se revoca la concesión o se saca
    a la persona de la unidad.
    """
    from permisos_unidad_carpeta import listar
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede ver los permisos por carpeta', 403)
    filas = listar(unidad_id, request.args.get('ruta') or None)
    ids = sorted({f['usuario_id'] for f in filas})
    nombres = {}
    if ids:
        # 12/08/2026: `usuarios` no tiene columna nombre_completo (500 al
        # existir la primera concesión). Mismo COALESCE que usa todo el motor.
        for u in consultar("""
            SELECT u.id,
                   COALESCE(t.nombres || ' ' || t.apellidos,
                            u.full_name, u.username) AS nombre
            FROM usuarios u
            LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id IN %s
        """, (tuple(ids),), nomina=True):
            nombres[u['id']] = u['nombre']
    for f in filas:
        f['usuario_nombre'] = nombres.get(f['usuario_id'], 'Usuario %s' % f['usuario_id'])
        f['creado_en'] = f['creado_en'].isoformat() if f.get('creado_en') else None
    return jsonify({'success': True, 'permisos': filas})


@bp_unidades.route('/unidades/<int:unidad_id>/permisos-carpeta', methods=['POST'])
def conceder_permiso_carpeta(unidad_id):
    """POST — {ruta, usuario_id, rol} : concede un rol sobre una carpeta."""
    from permisos_unidad_carpeta import conceder
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede conceder permisos por carpeta', 403)
    datos = request.get_json() or {}
    ruta = (datos.get('ruta') or '').strip()
    destino = datos.get('usuario_id')
    rol = (datos.get('rol') or '').strip()
    if not ruta or ruta == '/':
        return error('Indica una carpeta dentro de la unidad', 400)
    if not destino:
        return error('Falta la persona', 400)
    if rol not in ROLES:
        return error('Rol inválido', 400)
    try:
        r = conceder(unidad_id, ruta, int(destino), rol, creado_por=usuario)
    except ValueError as excepcion:
        return error(str(excepcion), 400)
    registrar_actividad(usuario, 'permiso_carpeta',
                        '/unidades/%s%s' % (unidad_id, r['ruta']),
                        'a %s como %s' % (destino, rol))
    log.info('Permiso de carpeta unidad=%s ruta=%s usuario=%s rol=%s por %s',
             unidad_id, r['ruta'], destino, rol, usuario)
    return jsonify({'success': True, 'permiso': r}), 201


@bp_unidades.route('/unidades/<int:unidad_id>/permisos-carpeta', methods=['DELETE'])
def revocar_permiso_carpeta(unidad_id):
    """DELETE — {ruta, usuario_id} : quita la concesión. La persona vuelve a su
    rol de unidad, o se queda sin acceso si no era miembro."""
    from permisos_unidad_carpeta import revocar
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede revocar permisos por carpeta', 403)
    datos = request.get_json() or {}
    ruta = (datos.get('ruta') or '').strip()
    destino = datos.get('usuario_id')
    if not ruta or not destino:
        return error('Faltan la carpeta o la persona', 400)
    revocar(unidad_id, ruta, int(destino))
    registrar_actividad(usuario, 'permiso_carpeta_revocado',
                        '/unidades/%s/%s' % (unidad_id, ruta.strip('/')), str(destino))
    return jsonify({'success': True})


@bp_unidades.route('/unidades/<int:unidad_id>/papelera', methods=['GET'])
def papelera_unidad(unidad_id):
    """Papelera de la unidad: lo que se borro de ella. La ve cualquier MIEMBRO
    (para saber que se borro); restaurar si es manager."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) is None:
        return error('No eres miembro de esta unidad', 403)
    carpetas, archivos = nucleo.listar_papelera_unidad(unidad_id)
    # Nombre de quien borro cada elemento (importante para saber a quien preguntar).
    _items = carpetas + archivos
    _ids = tuple({int(i['usuario_id']) for i in _items if i.get('usuario_id')})
    _nombres = {}
    if _ids:
        try:
            for _f in consultar(
                "SELECT u.id, COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, "
                "u.username) AS nombre FROM usuarios u "
                "LEFT JOIN trabajadores t ON u.trabajador_id = t.id WHERE u.id IN %s",
                (_ids,), nomina=True):
                _nombres[int(_f['id'])] = _f['nombre']
        except Exception:
            pass
    for _i in _items:
        _i['borrado_por'] = _nombres.get(int(_i['usuario_id']), 'Alguien') if _i.get('usuario_id') else ''
    return jsonify({'success': True, 'carpetas': carpetas, 'archivos': archivos,
                    'total': len(carpetas) + len(archivos),
                    'puede_restaurar': rol_en_unidad(usuario, unidad_id) == 'manager'})


@bp_unidades.route('/unidades/<int:unidad_id>/papelera/ver', methods=['GET'])
def ver_papelera_unidad(unidad_id):
    """Sirve un archivo de la papelera de la unidad para leerlo ANTES de restaurar.
    Lo puede ver cualquier miembro. Tipos activos (HTML/SVG/JS) se descargan."""
    import os
    from flask import send_file
    from config_almacen import raiz_datos
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) is None:
        return error('No eres miembro de esta unidad', 403)
    nombre_fisico = (request.args.get('nombre_fisico') or '').strip()
    if (not nombre_fisico) or ('/' in nombre_fisico) or ('\\' in nombre_fisico) or ('..' in nombre_fisico):
        return error('Elemento invalido', 400)
    filas = consultar(
        "SELECT nombre, es_carpeta FROM papelera WHERE unidad_id = %s AND nombre_fisico = %s",
        (unidad_id, nombre_fisico))
    if not filas:
        return error('No esta en la papelera', 404)
    if filas[0]['es_carpeta']:
        return error('No se puede previsualizar una carpeta', 400)
    fisica = os.path.join(raiz_datos(), '_unidades', str(unidad_id), 'papelera', nombre_fisico)
    if not os.path.isfile(fisica):
        return error('El archivo ya no existe', 404)
    ext = os.path.splitext(filas[0]['nombre'])[1].lstrip('.').lower()
    activos = {'html', 'htm', 'xhtml', 'svg', 'svgz', 'xml', 'js', 'mjs'}
    resp = send_file(fisica, as_attachment=(ext in activos), download_name=filas[0]['nombre'])
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    if ext in activos:
        resp.headers['Content-Type'] = 'application/octet-stream'
    return resp


@bp_unidades.route('/unidades/<int:unidad_id>/papelera/restaurar', methods=['POST'])
def restaurar_papelera_unidad(unidad_id):
    """Restaura un elemento de la papelera de la unidad. Solo un administrador."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un administrador de la unidad puede restaurar', 403)
    datos = request.get_json() or {}
    nombre_fisico = (datos.get('nombre_fisico') or '').strip()
    if not nombre_fisico:
        return error('Falta el elemento a restaurar', 400)
    try:
        ruta = nucleo.restaurar_papelera_unidad(unidad_id, nombre_fisico)
    except FileNotFoundError as e:
        return error(str(e), 404)
    return jsonify({'success': True, 'ruta': ruta, 'message': 'Restaurado'})


@bp_unidades.route('/unidades/<int:unidad_id>', methods=['PATCH'])
def renombrar_unidad(unidad_id):
    """PATCH — {nombre} : cambia el NOMBRE de la unidad. Lo puede hacer un
    administrador de la unidad (manager; master lo es de todas).

    Solo cambia la etiqueta: la unidad se referencia por id (/unidades/<id>) y
    los archivos viven en su carpeta fisica por id, asi que renombrar NO mueve
    nada ni rompe los enlaces compartidos ni el disco montado."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un administrador de la unidad puede renombrarla', 403)
    datos = request.get_json() or {}
    nombre = (datos.get('nombre') or '').strip()[:150]
    if not nombre:
        return error('Escribe un nombre', 400)
    ejecutar("UPDATE unidades_compartidas SET nombre = %s WHERE id = %s",
             (nombre, unidad_id))
    return jsonify({'success': True, 'nombre': nombre})


@bp_unidades.route('/unidades/<int:unidad_id>', methods=['DELETE'])
def eliminar_unidad(unidad_id):
    """DELETE — envía una unidad a la papelera (90 días). SOLO master.

    No se pierde nada: los archivos y un MANIFIESTO (nombre, miembros, permisos)
    se archivan en `_unidades/_eliminadas/<id>-<fecha>`. La unidad desaparece al
    instante de la web y del disco montado (se borran sus filas), pero se puede
    RESTAURAR tal cual durante DIAS_RETENCION días desde la papelera de unidades.
    Un timer purga definitivamente lo que pase de ese plazo. Si no se puede
    archivar, se ABORTA sin borrar nada."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un administrador general (master) puede eliminar '
                     'unidades', 403)
    fila = consultar("SELECT id, nombre, creado_por, creado_en "
                     "FROM unidades_compartidas WHERE id = %s", (unidad_id,))
    if not fila:
        return error('La unidad no existe', 404)
    u = fila[0]
    miembros = consultar("SELECT usuario_id, rol FROM unidad_miembros "
                         "WHERE unidad_id = %s", (unidad_id,))
    permisos = consultar("SELECT ruta, usuario_id, rol, creado_por, creado_en "
                         "FROM unidad_permisos_carpeta WHERE unidad_id = %s",
                         (unidad_id,))
    # ── ENLACES PÚBLICOS DE LA UNIDAD (05/08/2026) ──────────────────────────
    # Al borrar la unidad 6 quedó vivo su enlace público: seguía respondiendo y
    # mostraba una carpeta VACÍA a quien lo abriera —peor que un error, porque
    # quien lo tenía pensaba que se había borrado la documentación—. Ahora se
    # revocan junto con la unidad y se guardan en el manifiesto, para que al
    # RESTAURAR vuelvan tal cual (mismo token: quien tenga el enlace sigue
    # entrando, sin tener que repartirlo otra vez).
    enlaces = consultar(
        "SELECT propietario_id, ruta, tipo, destinatario, token, permisos, "
        "       expira_en, clave_hash, permite_descarga, email, puede_editar, "
        "       requiere_otp, modo, accesos, creado_en "
        "  FROM compartidos WHERE ruta = %s OR ruta LIKE %s",
        ('/unidades/%s' % unidad_id, '/unidades/%s/%%' % unidad_id))
    ahora = datetime.now(timezone.utc)

    def _iso(v):
        return v.isoformat() if v else None
    manifiesto = {
        'id': u['id'], 'nombre': u['nombre'],
        'creado_por': u['creado_por'], 'creado_en': _iso(u['creado_en']),
        'eliminada_en': ahora.isoformat(), 'eliminada_por': usuario,
        'miembros': [{'usuario_id': m['usuario_id'], 'rol': m['rol']}
                     for m in miembros],
        'permisos': [{'ruta': p['ruta'], 'usuario_id': p['usuario_id'],
                      'rol': p['rol'], 'creado_por': p['creado_por'],
                      'creado_en': _iso(p['creado_en'])} for p in permisos],
        'enlaces': [{k: (_iso(e[k]) if k in ('expira_en', 'creado_en') else e[k])
                     for k in e.keys()} for e in enlaces],
    }

    # 1) Archivar carpeta física (mover, nunca borrar) y guardar el manifiesto.
    #    Si falla, no se toca la base de datos: mejor dejar todo como estaba.
    try:
        base_el = _dir_eliminadas()
        os.makedirs(base_el, exist_ok=True)
        carpeta = '%s-%s' % (unidad_id, ahora.strftime('%Y%m%d-%H%M%S'))
        destino = os.path.join(base_el, carpeta)
        origen = os.path.join(raiz_datos(), '_unidades', str(unidad_id))
        if os.path.isdir(origen):
            # os.rename es ATÓMICO (mismo disco): mueve todo de golpe o falla
            # sin mover nada. Se usa a propósito en vez de shutil.move, que
            # copia y borra por partes y podría dejar la unidad a medias si el
            # borrado del origen fallara (p. ej. por permisos).
            os.rename(origen, destino)
        else:
            os.makedirs(destino, exist_ok=True)
        with open(os.path.join(destino, '_unidad.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(manifiesto, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        log.error('No se pudo archivar la unidad %s: %s', unidad_id, exc)
        return error('No se pudo eliminar la unidad ahora mismo (no se pudo '
                     'archivar su carpeta). No se borró nada. Intentá de nuevo; '
                     'si sigue, avisá a Tecnología.', 503)

    # 2) Quitar el registro. Los miembros caen por CASCADE; los permisos se
    #    borran explícitamente (por si no tuvieran FK con cascade).
    ejecutar("DELETE FROM unidad_permisos_carpeta WHERE unidad_id = %s", (unidad_id,))
    # Los enlaces públicos se cortan CON la unidad: si no, siguen respondiendo
    # y muestran una carpeta vacía a quien los tenga. Quedan en el manifiesto.
    ejecutar("DELETE FROM compartidos WHERE ruta = %s OR ruta LIKE %s",
             ('/unidades/%s' % unidad_id, '/unidades/%s/%%' % unidad_id))
    ejecutar("DELETE FROM unidades_compartidas WHERE id = %s", (unidad_id,))
    log.warning('Unidad %s ("%s") a papelera (%s días) por master %s. '
                'Enlaces revocados: %s. Carpeta: %s',
                unidad_id, u['nombre'], DIAS_RETENCION, usuario,
                len(enlaces), carpeta)
    return jsonify({'success': True,
                    'enlaces_revocados': len(enlaces),
                    'message': 'Unidad «%s» eliminada%s. Se puede recuperar '
                               'durante %s días desde la papelera de unidades.'
                               % (u['nombre'],
                                  (' y %d enlace%s público%s revocado%s'
                                   % (len(enlaces), '' if len(enlaces) == 1 else 's',
                                      '' if len(enlaces) == 1 else 's',
                                      '' if len(enlaces) == 1 else 's'))
                                  if enlaces else '',
                                  DIAS_RETENCION)})


@bp_unidades.route('/unidades/papelera', methods=['GET'])
def papelera_unidades_eliminadas():
    """GET — unidades eliminadas y recuperables (solo master). Lee los
    manifiestos de `_unidades/_eliminadas/` y calcula los días que quedan."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un administrador general (master) puede ver la '
                     'papelera de unidades', 403)
    ahora = datetime.now(timezone.utc)
    items = []
    base_el = _dir_eliminadas()
    if os.path.isdir(base_el):
        for carpeta in sorted(os.listdir(base_el), reverse=True):
            manif = os.path.join(base_el, carpeta, '_unidad.json')
            if not os.path.isfile(manif):
                continue
            try:
                with open(manif, encoding='utf-8') as fh:
                    m = json.load(fh)
                elim = datetime.fromisoformat(m['eliminada_en'])
                quedan = DIAS_RETENCION - (ahora - elim).days
                items.append({
                    'carpeta': carpeta, 'id': m.get('id'),
                    'nombre': m.get('nombre'),
                    'miembros': len(m.get('miembros', [])),
                    'eliminada_en': m.get('eliminada_en'),
                    'dias_restantes': max(0, quedan),
                })
            except Exception as exc:
                log.warning('Manifiesto ilegible en %s: %s', carpeta, exc)
    return jsonify({'success': True, 'unidades': items,
                    'retencion_dias': DIAS_RETENCION})


@bp_unidades.route('/unidades/papelera/restaurar', methods=['POST'])
def restaurar_unidad_eliminada():
    """POST — {carpeta} : restaura una unidad eliminada con su MISMO id, miembros
    y permisos, y devuelve sus archivos a su sitio. Solo master."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un administrador general (master) puede restaurar '
                     'unidades', 403)
    carpeta = os.path.basename(((request.get_json() or {}).get('carpeta') or '').strip())
    if not carpeta:
        return error('Falta indicar qué unidad restaurar', 400)
    dir_arch = os.path.join(_dir_eliminadas(), carpeta)
    manif = os.path.join(dir_arch, '_unidad.json')
    if not os.path.isfile(manif):
        return error('No se encontró esa unidad en la papelera', 404)
    with open(manif, encoding='utf-8') as fh:
        m = json.load(fh)
    uid = m['id']
    if consultar("SELECT 1 FROM unidades_compartidas WHERE id = %s", (uid,)):
        return error('Ya existe una unidad activa con ese identificador; no se '
                     'puede restaurar automáticamente. Avisá a Tecnología.', 409)

    # 1) Recrear registro (mismo id), miembros y permisos.
    ejecutar("INSERT INTO unidades_compartidas (id, nombre, creado_por, creado_en) "
             "VALUES (%s, %s, %s, %s)",
             (uid, m['nombre'], m.get('creado_por') or usuario, m.get('creado_en')))
    for mm in m.get('miembros', []):
        ejecutar("INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) "
                 "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                 (uid, mm['usuario_id'], mm['rol']))
    for p in m.get('permisos', []):
        ejecutar("INSERT INTO unidad_permisos_carpeta "
                 "(unidad_id, ruta, usuario_id, rol, creado_por, creado_en) "
                 "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                 (uid, p['ruta'], p['usuario_id'], p['rol'],
                  p.get('creado_por') or usuario, p.get('creado_en')))

    # 1b) Devolver los enlaces públicos que tenía, con su MISMO token: quien
    #     conserve el enlace vuelve a entrar sin que haya que repartirlo otra
    #     vez. Si alguno choca (token ya usado), se omite en vez de romper la
    #     restauración entera.
    enlaces_ok = 0
    for e in m.get('enlaces', []):
        try:
            ejecutar(
                "INSERT INTO compartidos (propietario_id, ruta, tipo, destinatario, "
                "  token, permisos, expira_en, clave_hash, permite_descarga, email, "
                "  puede_editar, requiere_otp, modo, accesos, creado_en) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (token) DO NOTHING",
                (e.get('propietario_id'), e.get('ruta'), e.get('tipo'),
                 e.get('destinatario'), e.get('token'), e.get('permisos'),
                 e.get('expira_en'), e.get('clave_hash'),
                 e.get('permite_descarga', True), e.get('email'),
                 e.get('puede_editar', False), e.get('requiere_otp', False),
                 e.get('modo') or 'descargar', e.get('accesos') or 0,
                 e.get('creado_en')))
            enlaces_ok += 1
        except Exception as exc:
            log.warning('Restauración de unidad %s: enlace %s no se pudo '
                        'recrear: %s', uid, (e.get('token') or '')[:10], exc)

    # 2) Devolver los archivos a su sitio (y quitar el manifiesto del destino).
    destino = os.path.join(raiz_datos(), '_unidades', str(uid))
    try:
        os.remove(manif)   # el manifiesto no debe viajar de vuelta
        if not os.path.exists(destino):
            os.rename(dir_arch, destino)   # atómico (mismo disco)
        else:
            # El destino ya existe (raro): mover el contenido dentro.
            for nombre_hijo in os.listdir(dir_arch):
                shutil.move(os.path.join(dir_arch, nombre_hijo),
                            os.path.join(destino, nombre_hijo))
            os.rmdir(dir_arch)
    except Exception as exc:
        log.error('Restauración de unidad %s: filas OK pero fallo al mover '
                  'archivos: %s', uid, exc)
        return jsonify({'success': True, 'nombre': m['nombre'],
                        'message': 'Unidad «%s» restaurada. Revisá los archivos '
                                   'con Tecnología por si acaso.' % m['nombre']})
    log.warning('Unidad %s ("%s") restaurada de la papelera por master %s',
                uid, m['nombre'], usuario)
    return jsonify({'success': True, 'nombre': m['nombre'],
                    'enlaces_restaurados': enlaces_ok,
                    'message': ('Unidad «%s» restaurada%s.'
                                % (m['nombre'],
                                   ' con %d enlace%s público%s'
                                   % (enlaces_ok, '' if enlaces_ok == 1 else 's',
                                      '' if enlaces_ok == 1 else 's')
                                   if enlaces_ok else ''))})
