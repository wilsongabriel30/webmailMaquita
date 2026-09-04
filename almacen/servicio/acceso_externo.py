# -*- coding: utf-8 -*-
"""Login de CUENTAS EXTERNAS del Drive (pasantes, aliados) — Fase 2.

Verifica contra `usuarios_externos` y emite un JWT en la MISMA cookie `access_token`
que el webmail (firmado con WEBMAIL_SECRET_KEY, HS256) pero con ÁMBITO PROPIO:
`aud = drive-externo`, `ambito = externo`. El backend del correo, el chat y el
propio Almacén distinguen esa sesión de la de un buzón:
  - el correo y el chat la RECHAZAN (PyJWT no acepta un `aud` que no se pidió, y el
    backend además lo comprueba de forma explícita);
  - el Almacén la resuelve SOLO contra `usuarios_externos`, nunca contra nómina.
La sesión viva se marca en Redis como `sesion_externa:<correo>` (NO `imap_pass:`, que
es la marca de sesión del correo). Antes se usaba la misma marca y el mismo JWT, y una
cuenta externa creada con el correo de un buzón interno se convertía en ese buzón.
Keycloak-ready: el callback OIDC podra reutilizar `emitir_sesion()`.
"""
import datetime as _dt
import hashlib
import hmac
import logging
import os
import secrets

import jwt
from flask import Blueprint, request, make_response, redirect, render_template_string

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.acceso_externo')

_SECRETO = os.getenv('WEBMAIL_SECRET_KEY', '')
_REDIS_URL = os.getenv('ALMACEN_REDIS_URL', '')
_COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN', '').strip()      # vacio = cookie host-only
_TTL_MIN = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '480'))   # 8 h por defecto
_MAX_INTENTOS = 8            # por IP+correo antes de frenar
_VENTANA_SEG = 900          # 15 min
AUDIENCIA_EXTERNA = 'drive-externo'   # `aud` del JWT de cuentas externas
CLAVE_SESION_EXTERNA = 'sesion_externa:%s'   # marca de sesión viva en Redis

bp_acceso_externo = Blueprint('acceso_externo', __name__)
_redis = None


def _r():
    global _redis
    if not _REDIS_URL:
        return None
    if _redis is None:
        import redis
        _redis = redis.Redis.from_url(_REDIS_URL, socket_timeout=2)
    return _redis


# ------------------------ contrasena (pbkdf2, sin dependencias) --------------
def hash_password_externo(pw: str) -> str:
    salt = secrets.token_hex(16)
    it = 200000
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), it)
    return 'pbkdf2_sha256$%d$%s$%s' % (it, salt, dk.hex())


def verificar_password_externo(pw: str, stored: str) -> bool:
    try:
        algo, it, salt, h = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), h)
    except Exception:
        return False


def fijar_password_externo(email: str, pw: str) -> bool:
    """Fija la contrasena y marca la cuenta como activada. Devuelve True si existia."""
    email = (email or '').strip().lower()
    filas = consultar('SELECT id FROM usuarios_externos WHERE LOWER(email)=%s AND active=TRUE', (email,))
    if not filas:
        return False
    ejecutar('UPDATE usuarios_externos SET password_hash=%s, activado=TRUE WHERE id=%s',
             (hash_password_externo(pw), filas[0]['id']))
    return True


def verificar_externo(email: str, pw: str) -> bool:
    email = (email or '').strip().lower()
    filas = consultar('SELECT password_hash FROM usuarios_externos '
                      'WHERE LOWER(email)=%s AND active=TRUE AND activado=TRUE', (email,))
    if not filas or not filas[0]['password_hash']:
        return False
    return verificar_password_externo(pw, filas[0]['password_hash'])


def emitir_sesion(resp, email: str):
    """Setea la cookie access_token (JWT con ámbito de cuenta externa) y marca sesion viva."""
    email = (email or '').strip().lower()
    exp = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=_TTL_MIN)
    token = jwt.encode({'sub': email, 'exp': exp, 'type': 'access',
                        'aud': AUDIENCIA_EXTERNA, 'ambito': 'externo'},
                       _SECRETO, algorithm='HS256')
    r = _r()
    if r is not None:
        try:
            r.set(CLAVE_SESION_EXTERNA % email, '1', ex=_TTL_MIN * 60)
        except Exception as e:
            log.warning('No se pudo marcar sesion en Redis: %s', e)
    ck = dict(httponly=True, secure=True, samesite='Strict', max_age=_TTL_MIN * 60, path='/')
    if _COOKIE_DOMAIN:
        ck['domain'] = _COOKIE_DOMAIN
    resp.set_cookie('access_token', token, **ck)
    return resp


def _frenado(clave: str) -> bool:
    r = _r()
    if r is None:
        return False
    try:
        return int(r.get('extlogin:%s' % clave) or 0) >= _MAX_INTENTOS
    except Exception:
        return False


def _contar_fallo(clave: str):
    r = _r()
    if r is None:
        return
    try:
        n = r.incr('extlogin:%s' % clave)
        if n == 1:
            r.expire('extlogin:%s' % clave, _VENTANA_SEG)
    except Exception:
        pass


_FORM = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acceso al Drive</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}
 .box{background:#fff;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.1);padding:34px;width:340px}
 h1{font-size:19px;text-align:center;margin:0 0 4px} .sub{text-align:center;color:#888;font-size:13px;margin-bottom:20px}
 label{font-size:13px;color:#444} input{width:100%;box-sizing:border-box;padding:11px;margin:6px 0 14px;border:1px solid #c8c6c4;border-radius:5px;font-size:15px}
 button{width:100%;background:#5b5fc7;color:#fff;border:0;padding:12px;border-radius:5px;font-size:15px;font-weight:600;cursor:pointer}
 .err{background:#fde7e9;color:#d13438;border-radius:6px;padding:10px;font-size:13px;margin-bottom:12px}
</style></head><body>
<form class="box" method="post" action="/acceso-externo">
  <h1>Acceso al Drive</h1>
  <div class="sub">Cuentas externas (colaboradores/aliados)</div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <label>Correo</label><input type="email" name="email" required autofocus>
  <label>Contrase&ntilde;a</label><input type="password" name="password" required>
  <button type="submit">Ingresar</button>
</form></body></html>"""


@bp_acceso_externo.route('/acceso-externo', methods=['GET'])
def form():
    return render_template_string(_FORM, error='')


@bp_acceso_externo.route('/acceso-externo', methods=['POST'])
def login():
    email = (request.form.get('email') or '').strip().lower()
    pw = request.form.get('password') or ''
    ip = request.headers.get('X-Real-IP') or (request.remote_addr or '')
    clave = '%s|%s' % (ip, email)
    if _frenado(clave):
        return render_template_string(_FORM, error='Demasiados intentos. Espera unos minutos.'), 429
    if email and pw and verificar_externo(email, pw):
        resp = make_response(redirect('/archivos-almacen'))
        return emitir_sesion(resp, email)
    _contar_fallo(clave)
    return render_template_string(_FORM, error='Credenciales incorrectas'), 401


# ======================= FASE 3: invitacion + fijar contrasena ===============
import re as _re
import smtplib as _smtplib
import datetime as _dt2
from email.message import EmailMessage as _EmailMessage

try:
    from config_almacen import URL_PUBLICA as _URL_PUBLICA
except Exception:
    _URL_PUBLICA = os.getenv('ALMACEN_URL_PUBLICA', 'http://localhost')

_INVIT_FROM = os.getenv('INVITACION_FROM', '')
_COMUNES = {'password', 'contrasena', 'contrasena1', '123456', '12345678', 'qwerty',
            'admin', 'maquita', '000000', 'iloveyou', 'bienvenido'}


def validar_fortaleza(pw: str, email: str = '') -> str:
    """Misma politica que el webmail. Devuelve un mensaje de error o '' si es valida."""
    if len(pw) < 10:
        return 'La contrase\u00f1a debe tener al menos 10 caracteres.'
    if len(pw) > 256:
        return 'La contrase\u00f1a no debe exceder 256 caracteres.'
    if not _re.search(r'[A-Z]', pw):
        return 'Debe incluir al menos una letra may\u00fascula.'
    if not _re.search(r'[a-z]', pw):
        return 'Debe incluir al menos una letra min\u00fascula.'
    if not _re.search(r'[0-9]', pw):
        return 'Debe incluir al menos un n\u00famero.'
    if not _re.search(r'[!@#$%^&*(),.?:{}|<>_+\-]', pw):
        return 'Debe incluir al menos un car\u00e1cter especial (!@#$%&*.).'
    base = pw.lower().rstrip('0123456789!@#$%^&*()_+-=.,')
    if pw.lower() in _COMUNES or base in _COMUNES:
        return 'Esa contrase\u00f1a es demasiado com\u00fan. Elige una m\u00e1s segura.'
    if email:
        u = email.split('@')[0].lower()
        if len(u) > 3 and u in pw.lower():
            return 'La contrase\u00f1a no debe contener tu usuario.'
    if _re.search(r'(.)\1{3,}', pw):
        return 'No debe tener 4 o m\u00e1s caracteres repetidos seguidos.'
    for i in range(len(pw) - 3):
        seq = pw[i:i + 4]
        if seq in '0123456789' or seq in 'abcdefghijklmnopqrstuvwxyz' or seq in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            return 'No debe contener secuencias obvias (1234, abcd).'
    return ''


def _from_addr() -> str:
    if _INVIT_FROM:
        return _INVIT_FROM
    host = _URL_PUBLICA.split('://')[-1].split('/')[0].split(':')[0]
    return 'no-reply@' + (host or 'localhost')


def _enviar_invitacion(email: str, nombre: str, link: str):
    msg = _EmailMessage()
    msg['Subject'] = 'Acceso al Drive \u2014 activa tu cuenta'
    msg['From'] = _from_addr()
    msg['To'] = email
    msg.set_content(
        'Hola %s:\n\nSe te ha dado acceso al Drive. Activa tu cuenta y define tu '
        'contrase\u00f1a en el siguiente enlace (v\u00e1lido 72 horas):\n\n%s\n\n'
        'Si no esperabas este correo, ign\u00f3ralo.\n' % (nombre or '', link))
    with _smtplib.SMTP('127.0.0.1', 25, timeout=15) as smtp:
        smtp.send_message(msg)


_DOMINIOS_INTERNOS = {d.strip().lower() for d in os.getenv(
    'ALMACEN_DOMINIOS_INTERNOS', 'maquita.org,maquita.com.ec,fundacionmaquita.org').split(',')
    if d.strip()}
_MAILDB_DSN = os.getenv('MAILDB_DSN', '').strip()


def es_correo_interno(email: str) -> bool:
    """True si el correo NO puede ser una cuenta externa: dominio institucional, buzon
    existente en el servidor de correo (MAILDB_DSN) o persona del directorio de nomina.
    Falla CERRADO: si una comprobacion configurada no responde, se considera interno."""
    email = (email or '').strip().lower()
    dominio = email.rsplit('@', 1)[-1]
    if dominio in _DOMINIOS_INTERNOS:
        return True
    if _MAILDB_DSN:
        try:
            import psycopg2
            with psycopg2.connect(_MAILDB_DSN, connect_timeout=5) as con:
                with con.cursor() as cur:
                    cur.execute('SELECT 1 FROM mailbox WHERE LOWER(username) = %s LIMIT 1', (email,))
                    if cur.fetchone():
                        return True
        except Exception as e:
            log.warning('No se pudo comprobar el buzon %s en el servidor de correo: %s', email, e)
            return True
    if os.getenv('ALMACEN_MODO_DIRECTORIO', 'local').strip().lower() == 'nomina':
        try:
            filas = consultar('SELECT 1 FROM usuarios WHERE LOWER(email) = %s LIMIT 1',
                              (email,), nomina=True)
            if filas:
                return True
        except Exception as e:
            log.warning('No se pudo comprobar %s en el directorio de nomina: %s', email, e)
            return True
    return False


def crear_e_invitar(email: str, nombre: str = '', creado_por: str = ''):
    """Crea la cuenta externa (si no existe) y le envia una invitacion. Devuelve (link, error)."""
    email = (email or '').strip().lower()
    if '@' not in email:
        return None, 'Correo inv\u00e1lido.'
    if es_correo_interno(email):
        return None, ('Ese correo pertenece a un buz\u00f3n o persona interna: entra con su '
                      'cuenta del correo, no como cuenta externa.')
    filas = consultar('SELECT id FROM usuarios_externos WHERE LOWER(email)=%s', (email,))
    if not filas:
        ejecutar('INSERT INTO usuarios_externos (email, full_name, active, activado, creado_por) '
                 'VALUES (%s,%s,TRUE,FALSE,%s)', (email, nombre or None, creado_por or None))
    token = secrets.token_urlsafe(32)
    expira = _dt2.datetime.now(_dt2.timezone.utc) + _dt2.timedelta(hours=72)
    ejecutar("UPDATE usuarios_externos SET invitacion_token=%s, invitacion_expira=%s, "
             "full_name=COALESCE(NULLIF(%s,''), full_name), "
             "creado_por=COALESCE(NULLIF(%s,''), creado_por) WHERE LOWER(email)=%s",
             (token, expira, nombre, creado_por, email))
    link = _URL_PUBLICA.rstrip('/') + '/acceso-externo/activar/' + token
    try:
        _enviar_invitacion(email, nombre, link)
    except Exception as e:
        log.warning('No se pudo enviar la invitacion a %s: %s', email, e)
    return link, None


def _cuenta_por_token(token: str):
    filas = consultar('SELECT id, email, full_name FROM usuarios_externos '
                      'WHERE invitacion_token=%s AND invitacion_expira > NOW() AND active=TRUE',
                      (token,))
    return filas[0] if filas else None


_FORM_ACTIVAR = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Activar cuenta</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}
 .box{background:#fff;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.1);padding:34px;width:360px}
 h1{font-size:19px;text-align:center;margin:0 0 4px} .sub{text-align:center;color:#888;font-size:13px;margin-bottom:18px}
 label{font-size:13px;color:#444} input{width:100%;box-sizing:border-box;padding:11px;margin:6px 0 12px;border:1px solid #c8c6c4;border-radius:5px;font-size:15px}
 button{width:100%;background:#5b5fc7;color:#fff;border:0;padding:12px;border-radius:5px;font-size:15px;font-weight:600;cursor:pointer}
 .err{background:#fde7e9;color:#d13438;border-radius:6px;padding:10px;font-size:13px;margin-bottom:12px}
 .reglas{font-size:12px;color:#888;margin:0 0 12px;line-height:1.5}
</style></head><body>
<form class="box" method="post">
  <h1>Activa tu cuenta del Drive</h1>
  <div class="sub">{{ email }}</div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  {% if token %}
  <div class="reglas">M\u00ednimo 10 caracteres, con may\u00fascula, min\u00fascula, n\u00famero y car\u00e1cter especial.</div>
  <label>Nueva contrase&ntilde;a</label><input type="password" name="password" required autofocus>
  <label>Repite la contrase&ntilde;a</label><input type="password" name="password2" required>
  <button type="submit">Activar y entrar</button>
  {% else %}
  <p style="text-align:center"><a href="/acceso-externo">Ir al inicio de sesi\u00f3n</a></p>
  {% endif %}
</form></body></html>"""


@bp_acceso_externo.route('/acceso-externo/activar/<token>', methods=['GET'])
def activar_form(token):
    c = _cuenta_por_token(token)
    if not c:
        return render_template_string(_FORM_ACTIVAR, token='', email='',
                                      error='Enlace inv\u00e1lido o expirado.'), 400
    return render_template_string(_FORM_ACTIVAR, token=token, email=c['email'], error='')


@bp_acceso_externo.route('/acceso-externo/activar/<token>', methods=['POST'])
def activar_post(token):
    c = _cuenta_por_token(token)
    if not c:
        return render_template_string(_FORM_ACTIVAR, token='', email='',
                                      error='Enlace inv\u00e1lido o expirado.'), 400
    pw = request.form.get('password') or ''
    pw2 = request.form.get('password2') or ''
    if pw != pw2:
        return render_template_string(_FORM_ACTIVAR, token=token, email=c['email'],
                                      error='Las contrase\u00f1as no coinciden.'), 400
    err = validar_fortaleza(pw, c['email'])
    if err:
        return render_template_string(_FORM_ACTIVAR, token=token, email=c['email'], error=err), 400
    ejecutar('UPDATE usuarios_externos SET password_hash=%s, activado=TRUE, '
             'invitacion_token=NULL, invitacion_expira=NULL WHERE id=%s',
             (hash_password_externo(pw), c['id']))
    resp = make_response(redirect('/archivos-almacen'))
    return emitir_sesion(resp, c['email'])   # auto-login tras activar


@bp_acceso_externo.route('/api/almacen/externos/invitar', methods=['POST'])
def invitar_endpoint():
    """Solo para admin (master): crea/invita una cuenta externa. Devuelve el enlace."""
    from auth_webmail import usuario_webmail
    _uid, rol = usuario_webmail()
    if rol not in ('master', 'master_admin'):
        return {'error': 'no autorizado'}, 403
    data = request.get_json(silent=True) or request.form
    link, err = crear_e_invitar((data.get('email') or '').strip(),
                                (data.get('nombre') or '').strip(), creado_por='admin')
    if err:
        return {'error': err}, 400
    return {'ok': True, 'link': link}


# ======================= FASE 4: panel de administracion =====================
from flask import jsonify as _jsonify


def _master_o_403():
    """Devuelve (uid, rol) si es master; si no, None (el caller responde 403)."""
    from auth_webmail import usuario_webmail
    uid, rol = usuario_webmail()
    return (uid, rol) if rol in ('master', 'master_admin') else None


@bp_acceso_externo.route('/api/almacen/externos', methods=['GET'])
def externos_listar():
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    filas = consultar(
        'SELECT id, email, full_name, active, activado, cuota_mb, proveedor, '
        "creado_por, to_char(creado_en,'YYYY-MM-DD') AS creado FROM usuarios_externos "
        'ORDER BY creado_en DESC')
    return _jsonify({'cuentas': [dict(f) for f in filas]})


@bp_acceso_externo.route('/api/almacen/externos/<int:eid>/activar', methods=['POST'])
def externos_activar(eid):
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    ejecutar('UPDATE usuarios_externos SET active=TRUE WHERE id=%s', (eid,))
    return _jsonify({'ok': True})


@bp_acceso_externo.route('/api/almacen/externos/<int:eid>/desactivar', methods=['POST'])
def externos_desactivar(eid):
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    ejecutar('UPDATE usuarios_externos SET active=FALSE WHERE id=%s', (eid,))
    # corta la sesion viva del externo (si Redis esta configurado)
    r = _r()
    if r is not None:
        fila = consultar('SELECT email FROM usuarios_externos WHERE id=%s', (eid,))
        if fila:
            try:
                r.delete(CLAVE_SESION_EXTERNA % fila[0]['email'].lower())
            except Exception:
                pass
    return _jsonify({'ok': True})


@bp_acceso_externo.route('/api/almacen/externos/<int:eid>/reinvitar', methods=['POST'])
def externos_reinvitar(eid):
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    fila = consultar('SELECT email, full_name FROM usuarios_externos WHERE id=%s', (eid,))
    if not fila:
        return _jsonify({'error': 'no existe'}), 404
    link, err = crear_e_invitar(fila[0]['email'], fila[0]['full_name'] or '', creado_por='admin')
    if err:
        return _jsonify({'error': err}), 400
    return _jsonify({'ok': True, 'link': link})


@bp_acceso_externo.route('/api/almacen/externos/<int:eid>/cuota', methods=['POST'])
def externos_cuota(eid):
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    data = request.get_json(silent=True) or request.form
    try:
        cuota = int(data.get('cuota_mb'))
    except (TypeError, ValueError):
        return _jsonify({'error': 'cuota_mb invalida'}), 400
    ejecutar('UPDATE usuarios_externos SET cuota_mb=%s WHERE id=%s', (cuota if cuota > 0 else None, eid))
    # Enforcement REAL: la cuota vive en la tabla `cuotas` por usuario_id (offset de externos),
    # el mismo mecanismo que los empleados. cuota=0 -> vuelve al default de la organizacion.
    from auth_webmail import _OFFSET_EXTERNOS
    uid = _OFFSET_EXTERNOS + eid
    if cuota > 0:
        ejecutar('INSERT INTO cuotas (usuario_id, limite_bytes) VALUES (%s,%s) '
                 'ON CONFLICT (usuario_id) DO UPDATE SET limite_bytes=EXCLUDED.limite_bytes',
                 (uid, cuota * 1024 * 1024))
    else:
        ejecutar('DELETE FROM cuotas WHERE usuario_id=%s', (uid,))
    return _jsonify({'ok': True})


@bp_acceso_externo.route('/api/almacen/externos/<int:eid>', methods=['DELETE'])
def externos_eliminar(eid):
    if not _master_o_403():
        return _jsonify({'error': 'no autorizado'}), 403
    fila = consultar('SELECT email FROM usuarios_externos WHERE id=%s', (eid,))
    from auth_webmail import _OFFSET_EXTERNOS
    uid = _OFFSET_EXTERNOS + eid
    ejecutar('DELETE FROM usuarios_externos WHERE id=%s', (eid,))
    ejecutar('DELETE FROM cuotas WHERE usuario_id=%s', (uid,))
    ejecutar('DELETE FROM cuotas_uso WHERE usuario_id=%s', (uid,))
    r = _r()
    if r is not None and fila:
        try:
            r.delete(CLAVE_SESION_EXTERNA % fila[0]['email'].lower())
        except Exception:
            pass
    # Los ARCHIVOS del externo NO se borran en automatico (para evitar perdida de datos):
    # quedan con su owner id y un master puede recuperarlos o limpiarlos. Revocar el acceso
    # (borrar la cuenta + cortar la sesion) basta para el cierre de la pasantia/alianza.
    return _jsonify({'ok': True})


_PANEL = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Cuentas externas del Drive</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;background:#faf9f8;margin:0;padding:24px;color:#323130}
 h1{font-size:20px} .crear{background:#fff;border:1px solid #e1dfdd;border-radius:8px;padding:16px;margin:14px 0;max-width:720px}
 input{padding:8px;border:1px solid #c8c6c4;border-radius:5px;font-size:14px;margin:0 6px 6px 0}
 button{background:#5b5fc7;color:#fff;border:0;border-radius:5px;padding:8px 12px;font-size:13px;cursor:pointer}
 button.sec{background:#edebe9;color:#323130} button.dng{background:#d13438}
 table{border-collapse:collapse;width:100%;max-width:1000px;background:#fff;font-size:13px}
 th,td{border:1px solid #edebe9;padding:8px 10px;text-align:left} th{background:#f3f2f1}
 .pill{font-size:11px;padding:2px 7px;border-radius:10px} .on{background:#dff6dd;color:#0b6a0b} .off{background:#fde7e9;color:#d13438}
 .msg{margin:8px 0;font-size:13px}
</style></head><body>
<h1>Cuentas externas del Drive</h1>
<p style="font-size:13px;color:#605e5c">Colaboradores/aliados con acceso al Drive sin buz&oacute;n de correo. Solo administradores.</p>
<div class="crear">
  <input id="email" type="email" placeholder="correo@externo.com" size="26">
  <input id="nombre" type="text" placeholder="Nombre (opcional)" size="20">
  <button onclick="invitar()">Crear e invitar</button>
  <div id="msg" class="msg"></div>
</div>
<table id="tabla"><thead><tr><th>Correo</th><th>Nombre</th><th>Estado</th><th>Cuota</th><th>Creada</th><th>Acciones</th></tr></thead><tbody></tbody></table>
<script>
const API='/api/almacen/externos';
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function cargar(){
  const r=await fetch(API); if(!r.ok){document.getElementById('msg').textContent='No autorizado.';return;}
  const d=await r.json(); const tb=document.querySelector('#tabla tbody'); tb.innerHTML='';
  (d.cuentas||[]).forEach(c=>{
    const estado = c.active ? (c.activado?'<span class="pill on">activa</span>':'<span class="pill off">sin activar</span>') : '<span class="pill off">inactiva</span>';
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${esc(c.email)}</td><td>${esc(c.full_name)}</td><td>${estado}</td>`+
      `<td>${c.cuota_mb?c.cuota_mb+' MB':'—'}</td><td>${esc(c.creado)}</td>`+
      `<td>`+
      (c.active?`<button class="sec" onclick="acc(${c.id},'desactivar')">Desactivar</button>`:`<button class="sec" onclick="acc(${c.id},'activar')">Activar</button>`)+
      ` <button class="sec" onclick="acc(${c.id},'reinvitar')">Reinvitar</button>`+
      ` <button class="sec" onclick="cuota(${c.id})">Cuota</button>`+
      ` <button class="dng" onclick="elim(${c.id},'${esc(c.email)}')">Eliminar</button>`+
      `</td>`;
    tb.appendChild(tr);
  });
}
async function invitar(){
  const email=document.getElementById('email').value, nombre=document.getElementById('nombre').value;
  const r=await fetch(API+'/invitar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,nombre})});
  const d=await r.json(); document.getElementById('msg').textContent = r.ok ? ('Invitada. Enlace: '+d.link) : ('Error: '+(d.error||''));
  if(r.ok){document.getElementById('email').value='';document.getElementById('nombre').value='';cargar();}
}
async function acc(id,a){await fetch(`${API}/${id}/${a}`,{method:'POST'});cargar();}
async function cuota(id){const v=prompt('Cuota en MB (0 = sin limite):');if(v===null)return;await fetch(`${API}/${id}/cuota`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cuota_mb:parseInt(v||'0',10)})});cargar();}
async function elim(id,em){if(!confirm('Eliminar la cuenta '+em+'? No borra sus archivos (eso es aparte).'))return;await fetch(`${API}/${id}`,{method:'DELETE'});cargar();}
cargar();
</script></body></html>"""


@bp_acceso_externo.route('/api/almacen/externos/panel', methods=['GET'])
def externos_panel():
    if not _master_o_403():
        return 'No autorizado', 403
    return _PANEL
