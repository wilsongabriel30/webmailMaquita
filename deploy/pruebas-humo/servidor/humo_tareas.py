#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-34 · Candado de TAREAS ASIGNADAS del correo (ciclo completo por la API).

Comprueba, con dos cuentas reales (quien asigna y quien recibe):
  1. asignar con plazo, prioridad y correo enlazado;
  2. que le aparece a quien la recibe («mis») y a quien la asigno («asignadas por mi»);
  3. aceptar, comentar, poner en curso y completar;
  4. el semaforo de plazos y el aviso al asignador al completarse;
  5. cadena (al completar A se activa B) y correo enlazado accesible;
  6. que la tarea con plazo llega al calendario del asignado;
  7. limpieza: borra lo que creo la prueba.

Uso: humo-tareas [asignador] [asignado]
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaTeams/0.4.42'
fallas = []
creadas = []


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
        resp = urllib.request.urlopen(r, timeout=25)
        cuerpo_txt = resp.read().decode('utf-8', 'ignore')
        return resp.status, (json.loads(cuerpo_txt) if cuerpo_txt.strip() else None)
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'ignore')
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt[:200]


def main(jefe=CUENTA, persona=PERSONA):
    tj, tp = token(jefe), token(persona)
    plazo = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()

    # 1) asignar, con correo enlazado
    est, tarea = api(tj, 'POST', '/api/tareas/asignar', {
        'titulo': 'Prueba de humo T-34', 'descripcion': 'Tarea creada por el candado; se borra sola.',
        'asignados': [persona], 'plazo': plazo, 'prioridad': 'high', 'etiquetas': ['humo'],
        'correo': {'folder': 'INBOX', 'uid': 263, 'subject': 'Prueba T-35: adjunto para lectura sin conexion'},
        'subtareas': ['primer paso', 'segundo paso'],
    })
    ok1 = est == 201 and isinstance(tarea, dict) and tarea.get('id')
    check('T-34 (1) . asignar tarea con plazo, prioridad y correo enlazado', ok1,
          'estado=%s' % est if not ok1 else 'id=%s' % str(tarea.get('id'))[:8])
    if not ok1:
        print('\nCandado T-34: no se pudo crear la tarea; se detiene.')
        return 1
    tid = tarea['id']
    creadas.append(tid)
    check('T-34 (7) . guarda las subtareas del checklist', tarea.get('subtareas_total') == 2,
          'subtareas=%s' % tarea.get('subtareas_total'))
    check('T-34 (1) . conserva el correo de origen como contexto', bool(tarea.get('correo')),
          'correo=%s' % json.dumps(tarea.get('correo'))[:60])
    check('T-34 (3) . el semaforo marca el plazo', tarea.get('semaforo') in ('verde', 'amarillo', 'rojo'),
          'semaforo=%s' % tarea.get('semaforo'))

    # 2) la ve quien la recibe y quien la asigno
    est, mias = api(tp, 'GET', '/api/tareas/mis')
    check('T-34 (3) . aparece en «Mis tareas» de quien la recibe',
          est == 200 and any(t['id'] == tid for t in (mias or [])), 'estado=%s' % est)
    est, asignadas = api(tj, 'GET', '/api/tareas/asignadas-por-mi')
    check('T-34 (3) . aparece en «Asignadas por mí» de quien la creo',
          est == 200 and any(t['id'] == tid for t in (asignadas or [])), 'estado=%s' % est)

    # el plazo llega al calendario del asignado (se comprueba CON LA TAREA VIVA:
    # al completarla se retira del calendario, que es el comportamiento correcto) (se comprueba por la API y, si no, en la BD)
    from urllib.parse import quote
    desde = quote((datetime.now(timezone.utc) - timedelta(days=1)).isoformat())   # el «+» de la zona debe ir codificado
    hasta = quote((datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
    est, cal = api(tp, 'GET', '/api/calendar/events?start=%s&end=%s' % (desde, hasta))
    texto_cal = json.dumps(cal)[:20000] if cal else ''
    en_api = 'Prueba de humo T-34' in texto_cal
    dsn_cal = subprocess.run(['bash', '-lc',
        "grep -o 'DATABASE_URL=.*' /opt/maquita-webmail/backend/.env | cut -d= -f2- | sed 's/+asyncpg//'"],
        capture_output=True, text=True).stdout.strip()
    fila = subprocess.run(['psql', dsn_cal, '-tAc',
                           "select c.owner_email || ' | ' || e.summary from events e join calendars c on c.id=e.calendar_id "
                           "where e.uid like 'task-%s%%'" % tid], capture_output=True, text=True).stdout.strip()
    check('T-34 (5) . el plazo de la tarea llega al calendario del asignado', bool(fila),
          'evento=%s' % (fila or 'no se creo'))
    check('T-34 (5) . y se ve al consultar el calendario por la API', en_api,
          'la API devolvio %d eventos' % (len(cal) if isinstance(cal, list) else -1))

    # 3) aceptar, comentar, en curso, completar
    est, _ = api(tp, 'POST', '/api/tareas/%s/aceptar' % tid)
    check('T-34 (7) . el asignado puede ACEPTAR la tarea', est == 200, 'estado=%s' % est)
    est, com = api(tp, 'POST', '/api/tareas/%s/comentarios' % tid, {'texto': 'Comentario del candado @%s' % jefe})
    check('T-34 (3) . comentarios con mención', est == 201 and com and com.get('texto'), 'estado=%s' % est)
    est, _ = api(tp, 'PATCH', '/api/tareas/%s/estado' % tid, {'estado': 'en_curso'})
    check('T-34 (3) . cambio de estado a «en curso»', est == 200, 'estado=%s' % est)
    est, completada = api(tp, 'POST', '/api/tareas/%s/completar' % tid)
    check('T-34 (3) . completar la tarea', est == 200 and completada.get('estado') == 'completada',
          'estado=%s' % (completada.get('estado') if isinstance(completada, dict) else est))

    fila_post = subprocess.run(['psql', dsn_cal, '-tAc',
                                "select count(*) from events where uid like 'task-%s%%'" % tid],
                               capture_output=True, text=True).stdout.strip()
    check('T-34 (5) . al completarla, la tarea se retira del calendario', fila_post == '0',
          'eventos restantes=%s' % fila_post)

    # 4) avisos generados (al asignar y al completar)
    dsn = subprocess.run(['bash', '-lc',
                          "grep -o 'DATABASE_URL=.*' /opt/maquita-webmail/backend/.env | cut -d= -f2- | sed 's/+asyncpg//'"],
                         capture_output=True, text=True).stdout.strip()
    tipos = subprocess.run(['psql', dsn, '-tAc',
                            "select string_agg(distinct tipo, ',') from task_avisos where card_id = '%s'" % tid],
                           capture_output=True, text=True).stdout.strip()
    check('T-34 (2) . deja avisos para el canal de notificaciones', bool(tipos),
          'tipos=%s' % (tipos or 'ninguno'))

    # 5) cadena: una tarea que se activa al completarse otra
    est, tarea_a = api(tj, 'POST', '/api/tareas/asignar', {
        'titulo': 'Prueba de humo T-34 (cadena A)', 'asignados': [persona],
        'plazo': plazo, 'prioridad': 'medium'})
    if est == 201:
        creadas.append(tarea_a['id'])
        est, tarea_b = api(tj, 'POST', '/api/tareas/asignar', {
            'titulo': 'Prueba de humo T-34 (cadena B)', 'asignados': [persona],
            'activa_tarea_id': tarea_a['id'], 'en_espera': True})
        if est == 201:
            creadas.append(tarea_b['id'])
            api(tp, 'POST', '/api/tareas/%s/completar' % tarea_a['id'])
            est, tb = api(tp, 'GET', '/api/tareas/%s' % tarea_b['id'])
            check('T-34 (4) . tarea en CADENA: al completar A se activa B',
                  est == 200 and tb.get('estado') != 'espera', 'estado de B=%s' % (tb or {}).get('estado'))
        else:
            check('T-34 (4) . tarea en CADENA: al completar A se activa B', False, 'no se pudo crear B (%s)' % est)
    else:
        check('T-34 (4) . tarea en CADENA: al completar A se activa B', False, 'no se pudo crear A (%s)' % est)

    # 8) el anti-olvido: vencimiento y escalamiento al jefe
    vencido = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    est, tv = api(tj, 'POST', '/api/tareas/asignar',
                  {'titulo': 'Prueba de humo T-34 (vencida)', 'asignados': [persona],
                   'plazo': vencido, 'escalar_a': jefe})
    if est == 201:
        creadas.append(tv['id'])
        subprocess.run(['/opt/maquita-webmail/backend/app/tareas/recordatorios.py'], capture_output=True, text=True)
        est, tv2 = api(tp, 'GET', '/api/tareas/%s' % tv['id'])
        check('T-34 (3) . una tarea pasada de plazo queda «vencida» en rojo',
              (tv2 or {}).get('estado') == 'vencida' and (tv2 or {}).get('semaforo') == 'rojo',
              'estado=%s semaforo=%s' % ((tv2 or {}).get('estado'), (tv2 or {}).get('semaforo')))
        avisos_v = subprocess.run(['psql', dsn, '-tAc',
                                   "select string_agg(distinct tipo, ',') from task_avisos where card_id = '%s'" % tv['id']],
                                  capture_output=True, text=True).stdout.strip()
        check('T-34 (2) . avisa al asignado Y al asignador cuando vence (anti-olvido)',
              'vencida' in avisos_v and 'vencida_asignador' in avisos_v, 'avisos=%s' % avisos_v)
        check('T-34 (7) . escalamiento al jefe de la tarea vencida', 'escalada' in avisos_v,
              'avisos=%s' % avisos_v)
    else:
        check('T-34 (3) . una tarea pasada de plazo queda «vencida» en rojo', False, 'no se pudo crear (%s)' % est)

    # 7) limpieza
    borradas = 0
    for t in creadas:
        e, _ = api(tj, 'DELETE', '/api/tareas/%s' % t)
        if e in (204, 200):
            borradas += 1
    check('T-34 . la prueba limpia lo que creo', borradas == len(creadas),
          '%d de %d borradas' % (borradas, len(creadas)))

    print('\nCandado T-34 (tareas asignadas): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else CUENTA
    b = sys.argv[2] if len(sys.argv) > 2 else PERSONA
    sys.exit(main(a, b))
