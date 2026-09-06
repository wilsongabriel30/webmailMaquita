#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-48 - Candado de los estados de presencia, medido de punta a punta.

Nada de importar modulos ni tocar Redis a mano: se abre un socket de verdad, se consulta por
HTTP igual que hace el cliente Windows, y se comprueba que el puntito dice la verdad.
"""
import json
import sys
import time
import urllib.error
import urllib.request

import jwt
import socketio as sio_cli

BASE = 'https://mail.maquita.org'
UA_APP = 'Mozilla/5.0 Chrome/151 MaquitaTeams/0.4.55'
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def token(correo):
    env = {}
    for l in open('/opt/maquita-webmail/chat-service/.env'):
        if '=' in l and not l.strip().startswith('#'):
            k, v = l.strip().split('=', 1)
            env[k] = v.strip('"\'')
    return jwt.encode({'sub': correo, 'type': 'access', 'exp': int(time.time()) + 900},
                      env['CHAT_JWT_SECRET'], algorithm='HS256')


def cookies(tok, ua=UA_APP):
    r = urllib.request.Request(BASE + '/chat/')
    r.add_header('Cookie', 'access_token=' + tok)
    r.add_header('User-Agent', ua)
    with urllib.request.urlopen(r, timeout=20) as resp:
        galletas = resp.headers.get_all('Set-Cookie') or []
    partes = ['access_token=' + tok]
    for c in galletas:
        if c.startswith('chat_session='):
            partes.append(c.split(';')[0])
    return '; '.join(partes)


def pedir(ruta, galletas, datos=None):
    r = urllib.request.Request(BASE + ruta, method='POST' if datos else 'GET',
                               data=json.dumps(datos).encode() if datos else None)
    r.add_header('Cookie', galletas)
    if datos:
        r.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def main():
    tok_a = token('test@maquita.org')
    tok_b = token('gestiontecnologia@maquita.com.ec')
    ga, gb = cookies(tok_a), cookies(tok_b)

    # quien es cada uno
    _, d = pedir('/api/chat/estado', ga)
    uid_a = d.get('usuario_id')
    _, d = pedir('/api/chat/estado', gb)
    uid_b = d.get('usuario_id')

    # 1) la lista definitiva, 1:1 con Teams
    for estado in ('disponible', 'ocupado', 'no_molestar', 'vuelvo_enseguida',
                   'ausente', 'desconectado'):
        c, d = pedir('/api/chat/estado', ga, {'estado': estado})
        check('T-48 . se puede elegir el estado «%s»' % estado,
              c == 200 and d.get('estado') == estado, 'estado=%d devuelve=%s' % (c, d.get('estado')))
    # «auto» restablece, y «conectado» sigue valiendo por el cliente antiguo
    c, d = pedir('/api/chat/estado', ga, {'estado': 'auto'})
    check('T-48 . «auto» restablece al automático', c == 200 and d.get('elegido') == 'auto',
          'elegido=%s' % d.get('elegido'))
    c, d = pedir('/api/chat/estado', ga, {'estado': 'conectado'})
    check('T-48 . se sigue aceptando «conectado» del cliente antiguo',
          c == 200 and d.get('estado') == 'disponible', 'devuelve=%s' % d.get('estado'))
    c, _ = pedir('/api/chat/estado', ga, {'estado': 'bailando'})
    check('T-48 . rechaza un estado inventado', c == 400, 'estado=%d' % c)

    # 2) AUTO-AUSENTE: se avisa de que se cierra la sesion (como hace la app al salir) y
    #    el puntito NO puede seguir diciendo conectado
    pedir('/api/chat/presence/offline', ga, {'online': False})
    time.sleep(1)
    c, d = pedir('/api/chat/estado/%d' % uid_a, gb)
    # sin ninguna conexion viva la verdad es que no esta: gris, como en Teams
    check('T-48 . al cerrar la sesión se muestra Desconectado',
          c == 200 and d.get('estado') == 'desconectado', 'dice %s' % d.get('estado'))

    # 3) con el socket abierto (como la app) pasa a Conectado
    s = sio_cli.Client(reconnection=False)
    s.connect(BASE, headers={'Cookie': ga, 'User-Agent': UA_APP},
              transports=['websocket'], wait_timeout=15)
    time.sleep(2)
    pedir('/api/chat/estado', ga, {'estado': 'conectado'})
    c, d = pedir('/api/chat/estado', ga)
    check('T-48 . con el socket abierto se muestra Disponible',
          d.get('estado') == 'disponible', 'dice %s' % d.get('estado'))

    # 4) elegir Ocupado se refleja al momento, y lo ve otra persona
    pedir('/api/chat/estado', ga, {'estado': 'ocupado'})
    c, d = pedir('/api/chat/estado/%d' % uid_a, gb)
    check('T-48 . el Ocupado elegido lo ve otra persona en el acto',
          d.get('estado') == 'ocupado', 'la otra cuenta ve %s' % d.get('estado'))

    # 5) «Ocupado» aguanta aunque se cierre la aplicacion (excepcion pactada)
    s.disconnect()
    time.sleep(3)
    c, d = pedir('/api/chat/estado/%d' % uid_a, gb)
    check('T-48 . «Ocupado» elegido a mano aguanta sin conexión (excepción pactada)',
          d.get('estado') == 'ocupado', 'dice %s' % d.get('estado'))

    # 6) pero «Disponible» a mano NO puede mentir cuando no hay conexion
    pedir('/api/chat/estado', ga, {'estado': 'disponible'})
    pedir('/api/chat/presence/offline', ga, {'online': False})
    time.sleep(1)
    c, d = pedir('/api/chat/estado/%d' % uid_a, gb)
    check('T-48 . «Disponible» a mano NO miente si no hay conexión',
          d.get('estado') == 'desconectado', 'dice %s' % d.get('estado'))

    # 7) varios de una vez, para pintar una lista
    c, d = pedir('/api/chat/estado/varios', ga, {'usuarios': [uid_a, uid_b]})
    check('T-48 . se pueden pedir varios estados de una vez',
          c == 200 and len(d.get('estados') or {}) == 2,
          'devuelve %d' % len(d.get('estados') or {}))

    # «No molestar» silencia lo no urgente, pero el aviso LLEGA igual (contrato T-47)
    pedir('/api/chat/estado', ga, {'estado': 'no_molestar'})
    c, d = pedir('/api/chat/estado', ga)
    check('T-48 . «No molestar» marca que hay que silenciar los avisos',
          d.get('silencia_avisos') is True, 'silencia_avisos=%s' % d.get('silencia_avisos'))
    pedir('/api/chat/estado', ga, {'estado': 'auto'})

    # 8) el detalle explica POR QUE (para que el cliente pueda contarlo)
    c, d = pedir('/api/chat/estado', ga)
    check('T-48 . el estado propio explica si es automático',
          'automatico' in d and 'elegido' in d and 'conectado' in d,
          'elegido=%s efectivo=%s automatico=%s' % (d.get('elegido'), d.get('estado'), d.get('automatico')))

    print('\nCandado T-48 (estados de presencia): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
