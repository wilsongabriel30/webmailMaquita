#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-47 · Candado del contrato de notificaciones: el evento `notificacion` llega a
TODAS las conexiones del usuario (navegador y app a la vez), no solo a una.
Uso: humo-notificaciones"""
import json
import sys
import time
import urllib.request

import jwt
import socketio as sio_cli

# Nada atado a una instalación concreta: todo por entorno o por argumentos.
#   HUMO_BASE         dirección donde se publica el chat (por omisión, CHAT_URL_PUBLICA)
#   HUMO_DESTINO      correo que RECIBE el aviso (dos conexiones: navegador y aplicación)
#   HUMO_REMITENTE    correo que escribe
#   HUMO_CONVERSACION conversación entre ambos (también como primer argumento)
#   HUMO_ENV          fichero de configuración del chat (por omisión, el de al lado)
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))
ENV = os.getenv('HUMO_ENV', os.path.join(_AQUI, '.env'))


def _config(clave, defecto=''):
    try:
        for l in open(ENV):
            if l.strip().startswith('#') or '=' not in l:
                continue
            k, v = l.strip().split('=', 1)
            if k == clave:
                return v.strip('"\'')
    except OSError:
        pass
    return defecto


BASE = (os.getenv('HUMO_BASE') or _config('CHAT_URL_PUBLICA')).rstrip('/')
fallas = []
recibidos = {'navegador': [], 'app': []}
confirmacion = {}   # nombre -> (segundos hasta `connected`, usuario_id)


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def token(correo):
    env = {'CHAT_JWT_SECRET': _config('CHAT_JWT_SECRET')}
    # `sid` y `av` NO son adorno: desde F-03 la sesion del chat los exige, porque son los que
    # permiten revocarla desde el correo. El vale real del webmail los lleva; sin ellos el
    # socket se rechaza con «sesion central no valida» y esta prueba daba rojo sin haber nada
    # roto. Aqui se usa un `sid` propio de la prueba, que el correo nunca ha revocado.
    return jwt.encode({'sub': correo, 'type': 'access',
                       'sid': 'humo-t47-%d' % int(time.time()),
                       'av': 0,
                       'exp': int(time.time()) + 900},
                      env['CHAT_JWT_SECRET'], algorithm='HS256')


def cookies(tok, ua):
    r = urllib.request.Request(BASE + '/chat/')
    r.add_header('Cookie', 'access_token=' + tok); r.add_header('User-Agent', ua)
    r.add_header('Accept', 'text/html')
    with urllib.request.urlopen(r, timeout=20) as resp:
        galletas = resp.headers.get_all('Set-Cookie') or []
    partes = ['access_token=' + tok]
    for c in galletas:
        if c.startswith('chat_session='):
            partes.append(c.split(';')[0])
    return '; '.join(partes)


def cliente(nombre, tok, ua):
    c = sio_cli.Client(reconnection=False)
    arranque = time.time()

    @c.on('notificacion')
    def _n(d):
        recibidos[nombre].append(d)

    # `connected` es la UNICA senal de que la conexion fue aceptada y quedo en la sala
    # user_<id>: desde la v0.4.51 la app se apoya en el para decidir si su canal esta vivo,
    # asi que si se quitara o se retrasara, la flota entera recargaria el chat en bucle.
    @c.on('connected')
    def _c(d):
        confirmacion[nombre] = (time.time() - arranque, (d or {}).get('usuario_id'))
    c.connect(BASE, headers={'Cookie': cookies(tok, ua), 'User-Agent': ua},
              transports=['websocket'], wait_timeout=15)
    return c


def main(conversacion=None):
    conversacion = conversacion or os.getenv('HUMO_CONVERSACION')
    correo_destino = os.getenv('HUMO_DESTINO', '')
    correo_remitente = os.getenv('HUMO_REMITENTE', '')
    if not (BASE and conversacion and correo_destino and correo_remitente):
        print('Faltan datos. Uso:\n'
              '  HUMO_BASE=https://chat.ejemplo.org HUMO_DESTINO=quien.recibe@ejemplo.org \\\n'
              '  HUMO_REMITENTE=quien.escribe@ejemplo.org HUMO_CONVERSACION=12 humo-notificaciones\n'
              '(HUMO_BASE se toma de CHAT_URL_PUBLICA si no se indica; la conversación también\n'
              ' puede ir como primer argumento). Las dos cuentas deben compartir esa conversación.')
        return 2
    conversacion = int(conversacion)
    destino, remitente = token(correo_destino), token(correo_remitente)
    c1 = cliente('navegador', destino, 'Mozilla/5.0 Chrome/151')
    c2 = cliente('app', destino, 'Mozilla/5.0 Chrome/151 MaquitaTeams/0.4.49')
    time.sleep(3)
    check('T-47 . las dos conexiones del usuario están conectadas', c1.connected and c2.connected,
          'navegador=%s app=%s' % (c1.connected, c2.connected))
    check('T-47 . el servidor confirma la conexión con `connected`',
          'navegador' in confirmacion and 'app' in confirmacion,
          'confirmadas: %s' % sorted(confirmacion))
    for quien, (tardanza, uid) in sorted(confirmacion.items()):
        check('T-47 . la confirmación del %s trae el usuario y llega a tiempo' % quien,
              bool(uid) and tardanza < 12, 'usuario=%s en %.1f s' % (uid, tardanza))

    datos = json.dumps({'content': 'Prueba de notificaciones %d' % int(time.time()),
                        'message_type': 'text'}).encode()
    r = urllib.request.Request(BASE + '/api/chat/conversations/%d/messages' % conversacion,
                               data=datos, method='POST')
    r.add_header('Content-Type', 'application/json'); r.add_header('Cookie', 'access_token=' + remitente)
    with urllib.request.urlopen(r, timeout=20) as resp:
        envio = resp.status
    time.sleep(6)
    check('T-47 . el mensaje se envía', envio in (200, 201), 'estado=%s' % envio)
    check('T-47 . la notificación llega al NAVEGADOR', len(recibidos['navegador']) > 0,
          '%d eventos' % len(recibidos['navegador']))
    check('T-47 . la notificación llega también a la APP (contrato: todas las conexiones)',
          len(recibidos['app']) > 0, '%d eventos' % len(recibidos['app']))
    if recibidos['app']:
        d = recibidos['app'][0]
        check('T-47 . la notificación trae lo necesario para abrir la conversación',
              bool(d.get('url')) and d.get('conversacion_id'),
              'url=%s conv=%s' % ((d.get('url') or '')[-28:], d.get('conversacion_id')))
    c1.disconnect(); c2.disconnect()
    print('\nCandado T-47 (notificaciones a todas las conexiones): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
