# -*- coding: utf-8 -*-
"""Login de CUENTAS EXTERNAS del Drive (pasantes, aliados) — Fase 2.

Verifica contra `usuarios_externos`, emite el MISMO JWT `access_token` que el webmail
(firmado con WEBMAIL_SECRET_KEY, HS256, payload sub/exp/type=access) y marca la sesion
viva en Redis. NO toca el login del correo. Lleva al Drive directamente (los externos no
tienen buzon). Keycloak-ready: el callback OIDC podra reutilizar `emitir_sesion()`.
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
    """Setea la cookie access_token (JWT igual al del webmail) y marca sesion viva."""
    email = (email or '').strip().lower()
    exp = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=_TTL_MIN)
    token = jwt.encode({'sub': email, 'exp': exp, 'type': 'access'}, _SECRETO, algorithm='HS256')
    r = _r()
    if r is not None:
        try:
            r.set('imap_pass:%s' % email, 'externo', ex=_TTL_MIN * 60)
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
