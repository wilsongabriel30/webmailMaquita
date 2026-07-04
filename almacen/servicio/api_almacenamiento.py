# -*- coding: utf-8 -*-
"""
API de ALMACENAMIENTO del Almacén Maquita (solo master).
========================================================
Permite al master ver y ELEGIR dónde se guardan los archivos: la carpeta local,
un disco USB, una carpeta de red (NFS o SMB/Windows), un NAS, o una nube montada
(Google Drive / OneDrive vía rclone). El destino se cambia en caliente si ya está
conectado; para conectar uno nuevo se genera el comando de montaje guiado.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os
import shutil
import shlex
import logging

from flask import Blueprint, jsonify, request

import config_almacen
from api_archivos import error, usuario_actual
from almacen_bd import es_master, consultar

log = logging.getLogger('almacen.almacenamiento')

bp_almacenamiento = Blueprint('almacen_almacenamiento', __name__)

# Sistemas de archivos "de sistema" que NO son destinos de datos válidos
_FS_IGNORAR = {'proc', 'sysfs', 'devtmpfs', 'devpts', 'tmpfs', 'cgroup', 'cgroup2',
               'overlay', 'squashfs', 'mqueue', 'debugfs', 'tracefs', 'securityfs',
               'pstore', 'bpf', 'configfs', 'fusectl', 'autofs', 'binfmt_misc', 'ramfs'}


def _master():
    if not es_master(usuario_actual()):
        from flask import abort
        abort(403)


def _uso(ruta):
    """(total, usado, libre) en bytes de la partición que contiene 'ruta'. None si no existe."""
    try:
        u = shutil.disk_usage(ruta)
        return {'total': u.total, 'usado': u.used, 'libre': u.free,
                'porcentaje': round(u.used * 100 / u.total, 1) if u.total else 0}
    except Exception:
        return None


def _humano(n):
    n = float(n or 0)
    for unidad in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if n < 1024 or unidad == 'PB':
            return f'{n:.1f} {unidad}'
        n /= 1024


def _escribible(ruta):
    return os.path.isdir(ruta) and os.access(ruta, os.W_OK)


@bp_almacenamiento.route('/admin/almacenamiento', methods=['GET'])
def estado_almacenamiento():
    """GET — destino actual de los datos + uso + destinos YA conectados donde se podría cambiar."""
    _master()
    actual = config_almacen.raiz_datos()
    info = {'ruta_actual': actual, 'escribible': _escribible(actual)}
    u = _uso(actual)
    if u:
        info.update({'uso': u, 'uso_humano': {
            'total': _humano(u['total']), 'usado': _humano(u['usado']), 'libre': _humano(u['libre'])}})

    # Destinos candidatos ya montados (particiones reales + /mnt + /media)
    candidatos = []
    vistos = set()
    try:
        with open('/proc/mounts') as f:
            for linea in f:
                partes = linea.split()
                if len(partes) < 3:
                    continue
                dispositivo, punto, tipo = partes[0], partes[1], partes[2]
                if tipo in _FS_IGNORAR or punto in vistos:
                    continue
                if not (punto == '/' or punto.startswith('/mnt') or punto.startswith('/media')
                        or punto.startswith('/home') or 'nfs' in tipo or 'cifs' in tipo or 'fuse' in tipo):
                    continue
                vistos.add(punto)
                uu = _uso(punto)
                candidatos.append({
                    'ruta': punto, 'tipo': tipo, 'dispositivo': dispositivo,
                    'escribible': _escribible(punto),
                    'libre_humano': _humano(uu['libre']) if uu else '—',
                    'total_humano': _humano(uu['total']) if uu else '—',
                })
    except Exception as e:
        log.warning('No se pudieron leer los montajes: %s', e)

    return jsonify({'success': True, 'actual': info, 'candidatos': candidatos})


@bp_almacenamiento.route('/admin/almacenamiento/usar', methods=['POST'])
def usar_almacenamiento():
    """
    POST — {ruta} : cambia el destino de los datos a una carpeta YA existente y escribible
    (disco local, USB montado, NAS/red montada, nube montada). Efecto inmediato.
    Crea una subcarpeta 'almacen-datos' dentro para no mezclar con otros archivos del disco.
    """
    _master()
    datos = request.get_json() or {}
    ruta = (datos.get('ruta') or '').strip()
    if not ruta or not ruta.startswith('/') or '..' in ruta:
        return error('Ruta inválida', 400)
    if not os.path.isdir(ruta):
        return error('Esa carpeta no existe (¿está montado el disco?)', 400)

    destino = os.path.join(ruta, 'almacen-datos')
    try:
        os.makedirs(destino, exist_ok=True)
    except OSError as e:
        return error(f'No se pudo crear la carpeta de datos: {e}', 400)
    if not _escribible(destino):
        return error('No hay permiso de escritura en ese destino', 400)

    config_almacen.set_raiz_datos(destino)
    log.info('[AUDIT] master %s cambió el almacenamiento a %s', usuario_actual(), destino)
    return jsonify({'success': True, 'ruta_actual': destino,
                    'message': f'Los archivos nuevos se guardarán en: {destino}'})


@bp_almacenamiento.route('/admin/almacenamiento/comando', methods=['POST'])
def comando_conexion():
    """
    POST — {tipo, ...parametros} : genera el COMANDO para conectar un almacenamiento
    todavía no montado (USB, NFS, SMB/Windows, NAS, nube rclone). No lo ejecuta: lo
    entrega para que un administrador lo corra una vez con permisos. Luego el destino
    aparece en 'candidatos' y se elige con /usar.
    """
    _master()
    d = request.get_json() or {}
    tipo = (d.get('tipo') or '').strip()
    punto = '/mnt/almacen'
    q = shlex.quote

    if tipo == 'usb':
        cmd = (f"# 1) Conecta el USB.  2) Ver el dispositivo:  lsblk\n"
               f"sudo mkdir -p {punto}\n"
               f"sudo mount /dev/sdX1 {punto}    # reemplaza sdX1 por el que muestre lsblk\n"
               f"# Luego elige {punto} en 'discos ya conectados'.")
    elif tipo == 'nfs':
        servidor = q(d.get('servidor', 'SERVIDOR'))
        export = q(d.get('export', '/export/almacen'))
        cmd = (f"sudo mkdir -p {punto}\n"
               f"sudo mount -t nfs {servidor}:{export} {punto}\n"
               f"# Para que sobreviva reinicios, agrégalo a /etc/fstab.")
    elif tipo == 'smb':
        servidor = d.get('servidor', 'SERVIDOR')
        carpeta = d.get('carpeta', 'CARPETA')
        usuario = q(d.get('usuario', 'USUARIO'))
        cmd = (f"sudo mkdir -p {punto}\n"
               f"sudo mount -t cifs //{servidor}/{carpeta} {punto} "
               f"-o username={usuario},password=***,vers=3.0,uid=$(id -u sistemas),gid=$(id -g sistemas)\n"
               f"# (Windows / NAS con SMB). Reemplaza *** por la contraseña.")
    elif tipo == 'nas':
        cmd = ("# Un NAS se conecta por NFS o SMB. Usa la opción 'Red NFS' o 'Red SMB/Windows'\n"
               "# con la IP del NAS y la carpeta compartida.")
    elif tipo == 'nube':
        remoto = q(d.get('remoto', 'miremoto'))
        cmd = (f"# Nube (Google Drive, OneDrive, etc.) vía rclone:\n"
               f"rclone config      # una vez: crea el remoto '{remoto}' (elige Drive/OneDrive/...)\n"
               f"sudo mkdir -p {punto}\n"
               f"rclone mount {remoto}: {punto} --vfs-cache-mode full --allow-other --daemon\n"
               f"# Nota: la nube es más lenta que un disco local; ideal para respaldo o archivos fríos.")
    elif tipo == 'local':
        ruta = q(d.get('ruta', '/ruta/de/tu/disco'))
        cmd = (f"sudo mkdir -p {ruta}\n"
               f"sudo chown sistemas:sistemas {ruta}\n"
               f"# Luego pon {ruta} en 'discos ya conectados' o escríbela directamente.")
    else:
        return error('Tipo de almacenamiento no reconocido', 400)

    return jsonify({'success': True, 'tipo': tipo, 'punto_montaje': punto, 'comando': cmd})


# ── CUOTAS POR USUARIO (espacio de cada persona) ─────────────────────────
_GB = 1024 ** 3


@bp_almacenamiento.route('/admin/cuota-defecto', methods=['GET', 'POST'])
def cuota_defecto():
    """GET/POST — cuota por defecto de la organización (GB). Solo master."""
    _master()
    if request.method == 'POST':
        datos = request.get_json() or {}
        try:
            gb = float(datos.get('gb'))
        except (TypeError, ValueError):
            return error('GB inválido', 400)
        if gb <= 0:
            return error('La cuota debe ser mayor a 0', 400)
        from almacen_bd import ejecutar
        ejecutar("""
            INSERT INTO config_kv (clave, valor) VALUES ('cuota_defecto_bytes', %s)
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
        """, (str(int(gb * _GB)),))
        return jsonify({'success': True, 'gb': gb})
    return jsonify({'success': True, 'gb': round(config_almacen.cuota_defecto_bytes() / _GB, 1)})


@bp_almacenamiento.route('/admin/usuarios', methods=['GET'])
def buscar_usuarios_cuota():
    """GET /admin/usuarios?q= — busca personas para asignarles espacio (nombre, usuario, id)."""
    _master()
    consulta = (request.args.get('q') or '').strip()
    if len(consulta) < 2:
        return jsonify({'success': True, 'usuarios': []})
    filas = consultar("""
        SELECT u.id, u.username,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
          AND (LOWER(u.username) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.nombres, '')) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.apellidos, '')) LIKE LOWER(%s) || '%%')
        ORDER BY u.username LIMIT 15
    """, (consulta, consulta, consulta), nomina=True)
    return jsonify({'success': True, 'usuarios': [dict(f) for f in filas]})


@bp_almacenamiento.route('/admin/cuota/<int:objetivo_id>', methods=['GET'])
def ver_cuota_usuario(objetivo_id):
    """GET — espacio de un usuario: cuánto usa y su límite (o el default)."""
    _master()
    import nucleo_archivos as nucleo
    datos = nucleo.cuota(objetivo_id)
    fila = consultar('SELECT limite_bytes FROM cuotas WHERE usuario_id = %s', (objetivo_id,))
    datos['success'] = True
    datos['tiene_cuota_propia'] = bool(fila)
    datos['limite_gb'] = round(datos['total'] / _GB, 1)
    datos['usado_gb'] = round(datos['usado'] / _GB, 2)
    return jsonify(datos)


@bp_almacenamiento.route('/admin/cuota', methods=['POST'])
def set_cuota_usuario():
    """POST — {usuario_id, gb} : asigna espacio a un usuario. gb=0 → usar el default."""
    _master()
    from almacen_bd import ejecutar
    datos = request.get_json() or {}
    uid = datos.get('usuario_id')
    if not uid:
        return error('usuario_id requerido', 400)
    try:
        gb = float(datos.get('gb'))
    except (TypeError, ValueError):
        return error('GB inválido', 400)
    if gb <= 0:   # volver al default (borra la cuota propia)
        ejecutar('DELETE FROM cuotas WHERE usuario_id = %s', (int(uid),))
        return jsonify({'success': True, 'message': 'Usará la cuota por defecto'})
    ejecutar("""
        INSERT INTO cuotas (usuario_id, limite_bytes) VALUES (%s, %s)
        ON CONFLICT (usuario_id) DO UPDATE SET limite_bytes = EXCLUDED.limite_bytes
    """, (int(uid), int(gb * _GB)))
    log.info('[AUDIT] master %s asignó %s GB al usuario %s', usuario_actual(), gb, uid)
    return jsonify({'success': True, 'gb': gb})


@bp_almacenamiento.route('/preferencias', methods=['GET'])
def preferencias():
    """GET /preferencias — el explorador la consulta al abrir; el motor devuelve vacío (JSON)."""
    usuario_actual()
    return jsonify({'success': True, 'preferencias': {}})
