#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-49 parte 3 - Candado de la HORA ORIGINAL de escritura.

Simula lo que hara la cola del equipo: un mensaje escrito hace 18 minutos que sale ahora.
El receptor tiene que poder ver las dos horas, y el servidor tiene que rechazar las horas
que no son de fiar (del futuro, o demasiado viejas).
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import jwt

BASE = 'https://mail.maquita.org'
CONV = 52
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def galletas(correo):
    env = {}
    for l in open('/opt/maquita-webmail/chat-service/.env'):
        if '=' in l and not l.strip().startswith('#'):
            k, v = l.strip().split('=', 1)
            env[k] = v.strip('"\'')
    t = jwt.encode({'sub': correo, 'type': 'access', 'exp': int(time.time()) + 900},
                   env['CHAT_JWT_SECRET'], algorithm='HS256')
    r = urllib.request.Request(BASE + '/chat/')
    r.add_header('Cookie', 'access_token=' + t)
    with urllib.request.urlopen(r, timeout=20) as x:
        g = x.headers.get_all('Set-Cookie') or []
    return '; '.join(['access_token=' + t] +
                     [c.split(';')[0] for c in g if c.startswith('chat_session=')])


def pedir(ruta, gal, datos=None):
    r = urllib.request.Request(BASE + ruta, method='POST' if datos else 'GET',
                               data=json.dumps(datos).encode() if datos else None)
    r.add_header('Cookie', gal)
    if datos:
        r.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(r, timeout=25) as x:
            return x.status, json.loads(x.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def main():
    gal = galletas('gestiontecnologia@maquita.com.ec')
    ahora = datetime.now(timezone.utc)

    # 1) un mensaje que estuvo 18 minutos en la cola del equipo
    escrito = (ahora - timedelta(minutes=18)).isoformat()
    marca = 'Mensaje en cola %d' % int(time.time())
    c, d = pedir('/api/chat/conversations/%d/messages' % CONV, gal,
                 {'content': marca, 'message_type': 'text', 'escrito_en': escrito})
    msg = (d.get('message') or {})
    check('T-49 . se acepta un mensaje con su hora de escritura', c == 200 and d.get('exito'),
          'estado=%d' % c)
    check('T-49 . la respuesta devuelve la hora en que se escribió',
          bool(msg.get('escrito_en')), 'escrito_en=%s' % msg.get('escrito_en'))
    # comparar como FECHAS, no como texto: las dos vienen en husos distintos
    def _fecha(v):
        try:
            f = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
            return f if f.tzinfo else f.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    fe, fl = _fecha(msg.get('escrito_en')), _fecha(msg.get('created_at'))
    check('T-49 . la hora de escritura es ANTERIOR a la de llegada',
          bool(fe and fl and fe < fl),
          'diferencia=%s' % (str(fl - fe) if (fe and fl) else 'no comparable'))

    # 2) al leer la conversacion, el receptor ve las dos horas
    time.sleep(1)
    c, d = pedir('/api/chat/conversations/%d/messages?limit=10' % CONV, gal)
    lista = d.get('messages') or d.get('mensajes') or []
    guardado = next((m for m in lista if (m.get('content') or m.get('contenido')) == marca), None)
    check('T-49 . el mensaje se recupera con su hora de escritura',
          bool(guardado and guardado.get('escrito_en')),
          'escrito_en=%s' % (guardado or {}).get('escrito_en'))

    # 3) horas que NO son de fiar: se ignoran y manda la hora de llegada
    futuro = (ahora + timedelta(hours=3)).isoformat()
    c, d = pedir('/api/chat/conversations/%d/messages' % CONV, gal,
                 {'content': 'Reloj adelantado %d' % int(time.time()),
                  'message_type': 'text', 'escrito_en': futuro})
    check('T-49 . se ignora una hora del futuro (reloj desajustado)',
          c == 200 and not (d.get('message') or {}).get('escrito_en'),
          'escrito_en=%s' % (d.get('message') or {}).get('escrito_en'))

    viejo = (ahora - timedelta(days=20)).isoformat()
    c, d = pedir('/api/chat/conversations/%d/messages' % CONV, gal,
                 {'content': 'Demasiado viejo %d' % int(time.time()),
                  'message_type': 'text', 'escrito_en': viejo})
    check('T-49 . se ignora una hora de hace más de 7 días',
          c == 200 and not (d.get('message') or {}).get('escrito_en'),
          'escrito_en=%s' % (d.get('message') or {}).get('escrito_en'))

    # 4) sin hora de escritura, todo sigue igual que siempre
    c, d = pedir('/api/chat/conversations/%d/messages' % CONV, gal,
                 {'content': 'Sin cola %d' % int(time.time()), 'message_type': 'text'})
    check('T-49 . un mensaje normal (sin cola) sigue funcionando igual',
          c == 200 and d.get('exito') and not (d.get('message') or {}).get('escrito_en'),
          'estado=%d' % c)

    print('\nCandado T-49 (hora original de escritura): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
