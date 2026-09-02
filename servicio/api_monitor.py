# -*- coding: utf-8 -*-
"""Monitoreo y mantenimiento del Drive Maquita (solo master).
=========================================================
Da a la administración una foto del estado del servicio (disco, base de datos,
Document Server, conversor CAD, índice, este worker) y un botón para RECARGAR el
servicio sin cortar a nadie (graceful HUP, zero-downtime) cuando va lento.

Autoría: Equipo de Tecnología Maquita — 2026-07-24
"""
import logging
import os
import shutil
import subprocess
import time
import urllib.request

from flask import Blueprint, jsonify, request

from api_archivos import error, usuario_actual
from almacen_bd import consultar, ejecutar, es_master, conexion

log = logging.getLogger('almacen.monitor')

bp_monitor = Blueprint('almacen_monitor', __name__)

RAIZ_ALMACEN = '/mnt/almacen'
URL_CAD = 'http://193.16.0.211:8790/health'


def _master():
    if not es_master(usuario_actual()):
        from flask import abort
        abort(403)


def _nombre_usuario(uid):
    try:
        f = consultar("SELECT COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, "
                      "u.username) AS n FROM usuarios u "
                      "LEFT JOIN trabajadores t ON u.trabajador_id = t.id "
                      "WHERE u.id = %s", (int(uid),), nomina=True)
        return f[0]['n'] if f else ('Usuario %s' % uid)
    except Exception:
        return 'Usuario %s' % uid


def _nombres_de(ids):
    ids = tuple({int(i) for i in ids}) or (0,)
    try:
        return {n['id']: n['nombre'] for n in consultar(
            "SELECT u.id, COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, "
            "u.username) AS nombre FROM usuarios u "
            "LEFT JOIN trabajadores t ON u.trabajador_id = t.id WHERE u.id IN %s",
            (ids,), nomina=True)}
    except Exception:
        return {}


_auditoria_lista = False


def _asegurar_auditoria():
    global _auditoria_lista
    if _auditoria_lista:
        return
    with conexion() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_auditoria (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER,
                    usuario_nombre TEXT,
                    accion TEXT NOT NULL,
                    detalle TEXT,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
    _auditoria_lista = True


def _auditar(uid, accion, detalle=''):
    """Deja rastro de una acción administrativa. Best-effort (nunca rompe)."""
    try:
        _asegurar_auditoria()
        ejecutar('INSERT INTO admin_auditoria (usuario_id, usuario_nombre, accion, '
                 'detalle) VALUES (%s, %s, %s, %s)',
                 (uid, _nombre_usuario(uid), accion, detalle))
    except Exception as excepcion:
        log.warning('auditoria %s: %s', accion, excepcion)


def _humano(n):
    n = float(n or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if n < 1024 or u == 'PB':
            return '%.1f %s' % (n, u)
        n /= 1024


def _ping_http(url, timeout=4):
    """(ok, ms) de un GET simple."""
    t = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(1)
            return (r.status == 200), round((time.monotonic() - t) * 1000)
    except Exception:
        return False, round((time.monotonic() - t) * 1000)


ARCHIVO_ESTADO_RESPALDO = '/home/sistemas/.almacen/respaldo-estado.json'

# Un respaldo diario que lleva mas de esto sin correr es un problema, no un retraso.
HORAS_ALERTA_RESPALDO = 26


@bp_monitor.route('/admin/respaldo', methods=['GET'])
def estado_respaldo():
    """GET /admin/respaldo — estado del respaldo diario. Solo master.

    La web NO entra al servidor de respaldos: es el propio script del nodo
    pve-backup el que EMPUJA este archivo al terminar, usando la misma llave
    que ya usa para el rsync. Aqui solo se lee un archivo local.

    Motivo de existir (incidente del 2026-07-28): el volcado de la base de datos
    estuvo produciendo archivos VACIOS durante dias mientras el log decia OK.
    La unica forma de haberlo visto era leer el log a mano. Esto lo pone a la
    vista de cualquier master.
    """
    import json
    import os
    from datetime import datetime, timezone

    negado = _master()
    if negado:
        return negado

    if not os.path.isfile(ARCHIVO_ESTADO_RESPALDO):
        return jsonify({
            'success': True,
            'hay_datos': False,
            'sano': False,
            'avisos': ['El respaldo nunca ha publicado su estado. '
                       'Puede que no se haya ejecutado desde que se activó el aviso, '
                       'o que no consiga escribir en este servidor.'],
        })

    try:
        with open(ARCHIVO_ESTADO_RESPALDO, encoding='utf-8') as fichero:
            estado = json.load(fichero)
    except Exception as excepcion:
        return jsonify({'success': True, 'hay_datos': False, 'sano': False,
                        'avisos': ['No se pudo leer el estado del respaldo: %s' % excepcion]})

    avisos = []

    # ¿Cuando corrio por ultima vez?
    horas = None
    try:
        generado = datetime.fromisoformat(estado.get('generado_en'))
        if generado.tzinfo is None:
            generado = generado.replace(tzinfo=timezone.utc)
        horas = (datetime.now(timezone.utc) - generado).total_seconds() / 3600.0
        if horas > HORAS_ALERTA_RESPALDO:
            avisos.append('El último respaldo fue hace %.0f horas. '
                          'Debería correr todos los días.' % horas)
    except Exception:
        avisos.append('No se pudo interpretar la fecha del último respaldo.')

    # La comprobacion que fallaba en silencio.
    bd = estado.get('base_datos') or {}
    if not bd.get('valido'):
        avisos.append('EL RESPALDO DE LA BASE DE DATOS NO ES VÁLIDO. '
                      'Los archivos estarían a salvo, pero se perderían los compartidos, '
                      'las versiones, la papelera y los permisos.')

    if not (estado.get('snapshot') or {}).get('tamano_bytes'):
        avisos.append('El snapshot de archivos figura vacío.')

    destino = estado.get('destino') or {}
    if (destino.get('usado_porcentaje') or 0) >= 90:
        avisos.append('El disco de respaldo está al %s%%.' % destino['usado_porcentaje'])

    return jsonify({
        'success': True,
        'hay_datos': True,
        'sano': not avisos,
        'avisos': avisos,
        'horas_desde_ultimo': round(horas, 1) if horas is not None else None,
        'estado': estado,
        'legible': {
            'snapshot': _humano((estado.get('snapshot') or {}).get('tamano_bytes') or 0),
            'base_datos': _humano(bd.get('tamano_bytes') or 0),
            'libre': _humano(destino.get('libre_bytes') or 0),
        },
    })


@bp_monitor.route('/admin/estado', methods=['GET'])
def estado_servicio():
    """GET /admin/estado — foto del estado del Drive (solo master)."""
    _master()
    comps = []

    # 1) Disco donde viven los archivos
    try:
        u = shutil.disk_usage(RAIZ_ALMACEN)
        pct = round(u.used * 100 / u.total, 1) if u.total else 0
        comps.append({'nombre': 'Almacenamiento (disco)',
                      'ok': pct < 92, 'icono': 'storage',
                      'detalle': '%s usado de %s (%s%%)' % (_humano(u.used), _humano(u.total), pct),
                      'alerta': 'Disco casi lleno' if pct >= 92 else ''})
    except Exception as e:
        comps.append({'nombre': 'Almacenamiento (disco)', 'ok': False,
                      'icono': 'storage', 'detalle': 'No se pudo leer: %s' % e})

    # 2) Base de datos
    t = time.monotonic()
    try:
        consultar('SELECT 1 AS x')
        ms = round((time.monotonic() - t) * 1000)
        comps.append({'nombre': 'Base de datos', 'ok': ms < 500, 'icono': 'database',
                      'detalle': 'responde en %s ms' % ms})
    except Exception as e:
        comps.append({'nombre': 'Base de datos', 'ok': False, 'icono': 'database',
                      'detalle': 'sin respuesta: %s' % str(e)[:60]})

    # 3) Document Server (OnlyOffice)
    try:
        from api_onlyoffice import url_interna_ds, url_publica_ds
        destino = (url_interna_ds() or url_publica_ds() or '').rstrip('/')
        if destino:
            ok, ms = _ping_http(destino + '/healthcheck')
            comps.append({'nombre': 'Editor OnlyOffice', 'ok': ok, 'icono': 'edit_document',
                          'detalle': ('responde en %s ms' % ms) if ok else 'no responde'})
    except Exception:
        pass

    # 4) Conversor CAD (visor de planos)
    ok, ms = _ping_http(URL_CAD)
    comps.append({'nombre': 'Visor de planos (CAD)', 'ok': ok, 'icono': 'architecture',
                  'detalle': ('responde en %s ms' % ms) if ok else 'contenedor no responde'})

    # 5) Índice de archivos
    try:
        fila = consultar('SELECT COUNT(*) AS c, MAX(modificado_en) AS m FROM indice_nombres')
        comps.append({'nombre': 'Índice de archivos', 'ok': True, 'icono': 'search',
                      'detalle': '{:,} elementos indexados'.format(int(fila[0]['c'])).replace(',', '.')})
    except Exception as e:
        comps.append({'nombre': 'Índice de archivos', 'ok': False, 'icono': 'search',
                      'detalle': str(e)[:60]})

    # 6) Este worker (prueba de latencia real)
    t = time.monotonic()
    try:
        import nucleo_archivos as nucleo
        nucleo.cuota(usuario_actual())
        ms = round((time.monotonic() - t) * 1000)
        comps.append({'nombre': 'Respuesta del Drive', 'ok': ms < 1500, 'icono': 'speed',
                      'detalle': 'operación típica en %s ms (worker %s)' % (ms, os.getpid()),
                      'alerta': 'El Drive va lento; considera Recargar' if ms >= 1500 else ''})
    except Exception as e:
        comps.append({'nombre': 'Respuesta del Drive', 'ok': False, 'icono': 'speed',
                      'detalle': str(e)[:60]})

    sano = all(c['ok'] for c in componentes_criticos(comps))
    return jsonify({'success': True, 'sano': sano, 'componentes': comps,
                    'generado': time.strftime('%Y-%m-%d %H:%M:%S')})


def componentes_criticos(comps):
    """Solo lo que hace 'no sano' el sistema (el DS y el CAD son opcionales)."""
    criticos = ('Almacenamiento (disco)', 'Base de datos', 'Respuesta del Drive',
                'Índice de archivos')
    return [c for c in comps if c['nombre'] in criticos]


@bp_monitor.route('/admin/recargar', methods=['POST'])
def recargar_servicio():
    """POST /admin/recargar — recarga el Drive SIN downtime (graceful HUP).
    Solo master. Se ejecuta en segundo plano para responder antes del reciclado."""
    uid = usuario_actual()
    if not es_master(uid):
        return error('Solo un administrador puede recargar el servicio', 403)
    reload_bin = '/usr/local/bin/faro-reload'
    if not os.path.exists(reload_bin):
        return error('No se encontró la herramienta de recarga en el servidor', 500)
    try:
        # Detached: la respuesta HTTP sale ANTES de que se reciclen los workers.
        subprocess.Popen([reload_bin, 'maquita'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        log.warning('[AUDIT] master %s recargó el servicio Drive (faro-reload maquita)', uid)
        _auditar(uid, 'Recargar servicio', 'faro-reload maquita (por lentitud)')
        return jsonify({'success': True,
                        'mensaje': 'Recargando el Drive sin cortar a nadie. '
                                   'En unos segundos verás la mejora.'})
    except Exception as e:
        log.error('recargar_servicio: %s', e)
        return error('No se pudo iniciar la recarga: %s' % e, 500)


# ---------------------------------------------------------------------------
# Herramientas de administración (todas solo master)
# ---------------------------------------------------------------------------
@bp_monitor.route('/admin/top-consumidores', methods=['GET'])
def top_consumidores():
    """GET /admin/top-consumidores — quién ocupa más espacio (del índice)."""
    _master()
    filas = consultar(
        'SELECT usuario_id, COALESCE(SUM(tamano), 0) AS bytes, COUNT(*) AS archivos '
        'FROM indice_nombres WHERE NOT es_carpeta GROUP BY usuario_id '
        'ORDER BY bytes DESC NULLS LAST LIMIT 25')
    nombres = _nombres_de([f['usuario_id'] for f in filas])
    top = [{'usuario_id': int(f['usuario_id']),
            'nombre': nombres.get(int(f['usuario_id']), 'Usuario %s' % f['usuario_id']),
            'bytes': int(f['bytes'] or 0), 'humano': _humano(f['bytes']),
            'archivos': int(f['archivos'])} for f in filas]
    return jsonify({'success': True, 'top': top})


@bp_monitor.route('/admin/enlaces', methods=['GET'])
def listar_enlaces():
    """GET /admin/enlaces — enlaces públicos activos de toda la organización."""
    _master()
    filas = consultar(
        'SELECT id, propietario_id, ruta, token, expira_en, permite_descarga, '
        'clave_hash, email, requiere_otp, creado_en FROM compartidos '
        'WHERE token IS NOT NULL ORDER BY creado_en DESC LIMIT 300')
    nombres = _nombres_de([f['propietario_id'] for f in filas])
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc)
    enlaces = []
    for f in filas:
        vencido = bool(f['expira_en'] and f['expira_en'] < ahora)
        enlaces.append({
            'id': f['id'], 'ruta': f['ruta'],
            'nombre': f['ruta'].rsplit('/', 1)[-1],
            'de': nombres.get(int(f['propietario_id']), 'Usuario %s' % f['propietario_id']),
            'para': f['email'] or '(enlace abierto)',
            'requiere_clave': bool(f['clave_hash']),
            'requiere_otp': bool(f.get('requiere_otp')),
            'permite_descarga': bool(f['permite_descarga']),
            'expira_en': f['expira_en'].isoformat() if f['expira_en'] else None,
            'vencido': vencido,
        })
    return jsonify({'success': True, 'enlaces': enlaces, 'total': len(enlaces)})


@bp_monitor.route('/admin/enlaces/revocar', methods=['POST'])
def revocar_enlace():
    """POST /admin/enlaces/revocar {id} — anula un enlace público."""
    uid = usuario_actual()
    if not es_master(uid):
        return error('Solo un administrador puede revocar enlaces', 403)
    d = request.get_json(silent=True) or {}
    eid = d.get('id')
    if not eid:
        return error('Falta el id del enlace', 400)
    fila = consultar('SELECT ruta FROM compartidos WHERE id = %s AND token IS NOT NULL',
                     (eid,))
    if not fila:
        return error('Ese enlace ya no existe', 404)
    ejecutar('DELETE FROM compartidos WHERE id = %s', (eid,))
    _auditar(uid, 'Revocar enlace', fila[0]['ruta'])
    return jsonify({'success': True, 'mensaje': 'Enlace revocado'})


@bp_monitor.route('/admin/purgar-retencion', methods=['POST'])
def purgar_retencion_admin():
    """POST /admin/purgar-retencion — elimina definitivamente lo que ya venció su
    retención de 90 días (libera espacio). Solo master, auditado."""
    uid = usuario_actual()
    if not es_master(uid):
        return error('Solo un administrador puede purgar la retención', 403)
    try:
        import nucleo_archivos as nucleo
        n = nucleo.purgar_retencion()
    except Exception as excepcion:
        log.error('purgar_retencion: %s', excepcion)
        return error('No se pudo purgar: %s' % excepcion, 500)
    _auditar(uid, 'Purgar retención', '%s elementos vencidos eliminados' % n)
    return jsonify({'success': True, 'purgados': n,
                    'mensaje': ('Se eliminaron %s elementos vencidos' % n) if n
                               else 'No había nada vencido por purgar'})


@bp_monitor.route('/admin/auditoria', methods=['GET'])
def ver_auditoria():
    """GET /admin/auditoria — historial de acciones administrativas."""
    _master()
    try:
        _asegurar_auditoria()
        filas = consultar('SELECT usuario_nombre, accion, detalle, creado_en '
                          'FROM admin_auditoria ORDER BY id DESC LIMIT 60')
    except Exception as excepcion:
        return error('No se pudo leer el historial: %s' % excepcion, 500)
    eventos = [{'usuario': f['usuario_nombre'], 'accion': f['accion'],
                'detalle': f['detalle'] or '',
                'cuando': f['creado_en'].isoformat() if f['creado_en'] else ''}
               for f in filas]
    return jsonify({'success': True, 'eventos': eventos})
