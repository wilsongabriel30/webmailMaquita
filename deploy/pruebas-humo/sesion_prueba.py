#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sesión de PRUEBAS del correo (para los candados humo-*).

Los candados necesitan una sesión COMPLETA, no solo un JWT: el backend exige que
exista la sesión IMAP en Redis (`imap_pass:<cuenta>:<sid>`), que nace al iniciar sesión
de verdad. Antes los candados reutilizaban por casualidad una sesión viva y, al
caducar (1/09), todos fallaron con 401 sin que hubiera avería alguna.

Aquí se abre la sesión por el camino oficial del panel de administración
(`/api/auth/impersonate`, que autentica con el master user de Dovecot), y se
devuelve el token listo para las pruebas. La sesión dura 1 hora.

Uso: python3 sesion_prueba.py [cuenta]   → imprime el access_token
(en el propio servidor del correo: necesita el .env del backend; ver README.md)
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import os

APP_BACKEND = os.environ.get('HUMO_BACKEND', '/opt/maquita-webmail/backend')
sys.path.insert(0, APP_BACKEND)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import BASE, CUENTA  # noqa: E402


CACHE = '/var/lib/maquita-humo/sesiones.json'


def _leer_cache():
    try:
        with open(CACHE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_cache(datos):
    try:
        import os
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, 'w', encoding='utf-8') as f:
            json.dump(datos, f)
        os.chmod(CACHE, 0o600)
    except Exception:
        pass


def _guardada(cuenta):
    """Devuelve el token guardado si su sesión sigue viva (se comprueba de verdad)."""
    t = _leer_cache().get(cuenta)
    if not t:
        return ''
    try:
        r = urllib.request.Request(BASE + '/api/auth/me')
        r.add_header('Cookie', 'access_token=' + t)
        r.add_header('User-Agent', 'candado-humo')
        datos = json.loads(urllib.request.urlopen(r, timeout=15).read().decode() or '{}')
        return t if (datos.get('user') or {}).get('username') else ''
    except Exception:
        return ''


def _sesion_viva(token):
    """Comprueba que la sesion guardada TODAVIA sirve para leer el buzon.

    No basta con que el token no haya caducado: la sesion de correo son dos cosas, el token
    y la clave IMAP que vive en Redis con una hora de vida. Cuando esa clave caduca, el token
    sigue pareciendo bueno pero el IMAP falla, y los candados del correo salian en rojo
    culpando al correo cuando el problema era la sesion de pruebas. Se comprueba de verdad.
    """
    if not token:
        return False
    r = urllib.request.Request(BASE + '/api/mail/folders')
    r.add_header('Cookie', 'access_token=' + token)
    r.add_header('User-Agent', 'candado-humo')
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status == 200
    except Exception:
        return False


def _configuracion_backend():
    """Configuración del backend leída desde SU carpeta.

    `app.config` busca el `.env` con ruta relativa: si el candado se lanza desde otra carpeta
    (p. ej. /opt/maquita-webmail) no lo encuentra y la sesión de pruebas no se abre (falso rojo de
    T-40 al caducar la sesión guardada). Se lee desde APP_BACKEND y se deja la carpeta como estaba,
    porque otras pruebas importan este módulo.
    """
    anterior = os.getcwd()
    os.chdir(APP_BACKEND)
    try:
        from app.config import get_settings
        return get_settings()
    finally:
        os.chdir(anterior)


def abrir(cuenta=CUENTA):
    reutilizada = _guardada(cuenta)
    if reutilizada and _sesion_viva(reutilizada):
        return reutilizada
    import jwt as pyjwt
    s = _configuracion_backend()
    # Desde A-17 (04/09) el correo solo acepta un VALE de impersonación: para un buzón concreto,
    # de un solo uso (jti) y de 5 minutos. Se emite aquí igual que lo hace el panel.
    import uuid
    admin = pyjwt.encode({'username': 'candado-humo', 'role': 'superadmin', 'purpose': 'impersonate',
                          'target': cuenta, 'totp': True, 'jti': uuid.uuid4().hex,
                          'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                         s.admin_jwt_secret, algorithm='HS256')
    cuerpo = json.dumps({'username': cuenta, 'admin_token': admin}).encode()
    r = urllib.request.Request(BASE + '/api/auth/impersonate', data=cuerpo, method='POST')
    r.add_header('Content-Type', 'application/json')
    r.add_header('User-Agent', 'candado-humo')
    try:
        resp = urllib.request.urlopen(r, timeout=25)
        galletas = resp.headers.get_all('Set-Cookie') or []
        for c in galletas:
            if c.startswith('access_token='):
                t = c.split('=', 1)[1].split(';')[0]
                datos = _leer_cache(); datos[cuenta] = t; _guardar_cache(datos)
                return t
        datos = json.loads(resp.read().decode() or '{}')
        return datos.get('access_token', '')
    except urllib.error.HTTPError as e:
        print('no se pudo abrir la sesión de pruebas: %s %s' % (e.code, e.read()[:150].decode('utf-8', 'ignore')),
              file=sys.stderr)
        return ''


if __name__ == '__main__':
    t = abrir(sys.argv[1] if len(sys.argv) > 1 else CUENTA)
    if not t:
        sys.exit(2)
    print(t)
