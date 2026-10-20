#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-30 · Candado del ECOSISTEMA reuniones ⇄ calendario.

Comprueba el ida y vuelta completo:
  1. calendario → reunión: crear un evento con `meet` crea la sala, pone el enlace
     en el evento y los deja vinculados por un mismo id (identidad única);
  2. modificar el evento actualiza la reunión; eliminarlo la cancela;
  3. reunión → calendario: una reunión del servicio se refleja como evento;
  4. la reunión queda accesible por su id (misma identidad en ambos lados).
La prueba borra lo que crea.

Uso: humo-reuniones [cuenta]
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaTeams/0.4.42'
fallas = []


def check(nombre, ok, detalle=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + nombre + (' - ' + detalle if detalle else ''))
    if not ok:
        fallas.append(nombre)


def token(correo):
    # Sesion COMPLETA (JWT + sesion IMAP en Redis): un JWT suelto da 401 en el correo.
    sys.path.insert(0, '/opt/maquita-webmail/backend')
    from sesion_prueba import abrir
    t = abrir(correo)
    if not t:
        raise SystemExit('no se pudo abrir la sesion de pruebas de %s' % correo)
    return t


def api(tok, metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    r.add_header('User-Agent', UA)
    r.add_header('Cookie', 'access_token=' + tok)
    if datos:
        r.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        txt = resp.read().decode('utf-8', 'ignore')
        return resp.status, (json.loads(txt) if txt.strip() else None)
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'ignore')
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt[:200]


def main(cuenta=CUENTA):
    tok = token(cuenta)
    est, cals = api(tok, 'GET', '/api/calendar/calendars')
    if est != 200 or not cals:
        print('[FALLA ] no se pudo leer el calendario (%s)' % est)
        return 1
    cal_id = cals[0]['id']
    inicio = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    fin = inicio + timedelta(hours=1)

    # 1) calendario -> reunión
    est, ev = api(tok, 'POST', '/api/calendar/events', {
        'calendar_id': cal_id, 'summary': 'Prueba de humo T-30', 'description': 'Candado del ecosistema',
        'dtstart': inicio.isoformat(), 'dtend': fin.isoformat(), 'meet': True, 'timezone': 'America/Guayaquil',
    })
    ok = est in (200, 201) and isinstance(ev, dict)
    check('T-30 (2) . crear un evento «con videollamada» funciona', ok, 'estado=%s' % est)
    if not ok:
        print('\nCandado T-30: no se pudo crear el evento; se detiene.')
        return 1
    ev_id = ev['id']
    check('T-30 (2) . el evento recibe el enlace de la sala Meet', bool(ev.get('meet_url')),
          'url=%s' % (ev.get('meet_url') or 'ninguna')[:60])
    check('T-30 (3) . identidad única: el evento queda vinculado a la reunión por su id',
          bool(ev.get('reunion_id')), 'reunion_id=%s' % ev.get('reunion_id'))
    rid = ev.get('reunion_id')

    # 2) la reunión existe en el servicio, con el mismo id (se consulta la agenda del servicio)
    def reunion_en_agenda(rid_):
        e, ag = api(tok, 'GET', '/api/chat/reuniones/proximas')
        lista = (ag or {}).get('reuniones', ag) if isinstance(ag, dict) else (ag or [])
        for r_ in (lista or []):
            if str(r_.get('id')) == str(rid_):
                return e, r_
        return e, None
    est, reunion = reunion_en_agenda(rid) if rid else (0, None)
    check('T-30 (3) . la reunión existe en el servicio con ese mismo id', est == 200 and bool(reunion),
          'estado=%s encontrada=%s' % (est, bool(reunion)))

    # 3) modificar el evento actualiza la reunión
    nuevo_inicio = inicio + timedelta(hours=2)
    est, ev2 = api(tok, 'PUT', '/api/calendar/events/%s' % ev_id, {
        'summary': 'Prueba de humo T-30 (movida)', 'dtstart': nuevo_inicio.isoformat(),
        'dtend': (nuevo_inicio + timedelta(hours=1)).isoformat(),
    })
    check('T-30 (2) . modificar el evento no rompe el vínculo', est == 200 and (ev2 or {}).get('reunion_id') == rid,
          'estado=%s reunion_id=%s' % (est, (ev2 or {}).get('reunion_id')))
    if rid:
        est, r2 = reunion_en_agenda(rid)
        hora = json.dumps(r2) if r2 else ''
        check('T-30 (2) . la reunión refleja el cambio de hora',
              bool(r2) and (nuevo_inicio.strftime('%H:%M') in hora or nuevo_inicio.strftime('%Y-%m-%dT%H') in hora
                            or nuevo_inicio.strftime('%Y-%m-%d %H') in hora),
              'agenda=%s' % hora[:120])

    # 4) eliminar el evento cancela la reunión
    est, _ = api(tok, 'DELETE', '/api/calendar/events/%s' % ev_id)
    check('T-30 (2) . eliminar el evento responde correctamente', est in (200, 204), 'estado=%s' % est)
    if rid:
        est, r3 = reunion_en_agenda(rid)
        texto = json.dumps(r3).lower() if r3 else ''
        cancelada = (r3 is None) or 'cancel' in texto
        check('T-30 (2) . al eliminar el evento, la reunión queda cancelada', cancelada,
              'sigue en la agenda' if not cancelada else 'fuera de la agenda')

    # 5) sentido inverso: reunión creada en el servicio (lo que hace la web del servicio) → evento
    ini2 = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    est, r = api(tok, 'POST', '/api/chat/reuniones',
                 {'asunto': 'Prueba de humo T-30 (desde reuniones)', 'inicio': ini2.isoformat(),
                  'duracion_minutos': 30})
    rid2 = ((r or {}).get('reunion') or {}).get('id') if isinstance(r, dict) else None
    if rid2:
        api(tok, 'POST', '/api/chat/reuniones/%s/calendario' % rid2)
        d1 = quote((datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        d2 = quote((datetime.now(timezone.utc) + timedelta(days=4)).isoformat())
        est, evs = api(tok, 'GET', '/api/calendar/events?start=%s&end=%s' % (d1, d2))
        mios = [e for e in (evs or []) if 'Prueba de humo T-30 (desde reuniones)' in json.dumps(e)]
        check('T-30 (1) . una reunión creada en el servicio de reuniones aparece en el calendario del creador',
              bool(mios), '%d evento(s)' % len(mios))
        check('T-30 (1) . ese evento trae el enlace de la sala',
              bool(mios and mios[0].get('meet_url')), (mios[0].get('meet_url') if mios else '')[:50])
        for e in mios:
            api(tok, 'DELETE', '/api/calendar/events/%s' % e['id'])
        api(tok, 'POST', '/api/chat/reuniones/%s/cancelar' % rid2)
    else:
        check('T-30 (1) . una reunión creada en el servicio de reuniones aparece en el calendario del creador', False,
              'no se pudo crear la reunión (%s)' % est)

    # 6) grabaciones ligadas al registro único (contrato T-30 punto 4). Solo si la instalación
    # tiene servicio de reuniones con grabaciones: HUMO_DSN_GRABACIONES=postgresql://… (lectura).
    dsn_grab = os.environ.get('HUMO_DSN_GRABACIONES', '')
    if dsn_grab:
        import subprocess
        fila = subprocess.run(['psql', dsn_grab, '-tAF|', '-c',
                               'select count(*), count(reunion_id), count(vence_en) from reuniones_grabaciones'],
                              capture_output=True, text=True).stdout.strip()
        partes = fila.split('|') if fila else []
        check('T-30 (4) . las grabaciones quedan ligadas a la reunión y con caducidad',
              len(partes) == 3 and partes[0] == partes[1] == partes[2] and int(partes[0] or 0) > 0,
              'grabaciones=%s ligadas=%s con caducidad=%s' % tuple(partes) if len(partes) == 3 else fila)
    # (la purga por retención se comprueba en VM 136, donde vive su cron: candado humo-llamadas)

    # 7) el evento ya no está en el calendario
    desde = quote((datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    hasta = quote((datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
    est, eventos = api(tok, 'GET', '/api/calendar/events?start=%s&end=%s' % (desde, hasta))
    quedan = [e for e in (eventos or []) if 'Prueba de humo T-30' in json.dumps(e)]
    check('T-30 . la prueba no deja nada en el calendario', not quedan, '%d restos' % len(quedan))

    print('\nCandado T-30 (reuniones ⇄ calendario): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CUENTA))
