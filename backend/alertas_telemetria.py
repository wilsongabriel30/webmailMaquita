#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-37 punto 3 (31/08/2026): ALERTAS PROACTIVAS de la telemetria de las apps.

Corre cada 15 minutos (cron) y avisa a soporte por el canal de notificaciones
—el mismo que usa el cliente Windows— cuando:
  (a) un equipo quedo con una version anterior a la vigente publicada;
  (b) el mismo error se repite 3 o mas veces;
  (c) hay una oleada de fallos de sesion / peticiones de login;
  (d) hay una oleada de «sin conexion» de un mismo modulo (servicio caido).

Para no volverse ruido, cada alerta se guarda en `app_telemetria_alertas` y no
se repite hasta pasada su ventana de silencio. Solo datos tecnicos: nunca
contenido de correos, chats ni archivos.

Uso: alertas-telemetria [--dry-run]   (sin enviar, solo mostrar)
Autor: Wilson Arguello
"""
import hashlib
import os
import sys

import psycopg2
import requests

BASE = '/opt/maquita-webmail/backend'
CHAT_NOTIF_URL = os.getenv('CHAT_NOTIF_URL', 'http://193.16.0.136:8790/api/chat/notificaciones')
URL_VERSION = 'https://mail.maquita.org/static/teams/teams-windows-version.json'
DESTINATARIOS = [int(x) for x in os.getenv('TELEMETRIA_ALERTAS_IDS', '17').split(',') if x.strip().isdigit()]

DDL = """
CREATE TABLE IF NOT EXISTS app_telemetria_alertas (
    clave    TEXT PRIMARY KEY,
    enviada  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    detalle  TEXT NOT NULL DEFAULT ''
)
"""


def _env(clave, archivo=BASE + '/.env'):
    for linea in open(archivo, encoding='utf-8', errors='ignore'):
        if linea.startswith(clave + '='):
            return linea.strip().split('=', 1)[1].strip('"\'')
    return ''


def conectar():
    dsn = _env('DATABASE_URL').replace('+asyncpg', '')
    return psycopg2.connect(dsn)


def version_vigente():
    try:
        return requests.get(URL_VERSION, timeout=6).json().get('version', '')
    except Exception:
        return ''


def ya_avisado(cur, clave, horas):
    cur.execute("SELECT 1 FROM app_telemetria_alertas WHERE clave = %s AND enviada > NOW() - make_interval(hours => %s)",
                (clave, horas))
    return cur.fetchone() is not None


def marcar(cur, clave, detalle):
    cur.execute("""INSERT INTO app_telemetria_alertas (clave, enviada, detalle) VALUES (%s, NOW(), %s)
                   ON CONFLICT (clave) DO UPDATE SET enviada = NOW(), detalle = EXCLUDED.detalle""",
                (clave, detalle[:500]))


def avisar(titulo, texto, url='/tecnologia/telemetria-apps', dry=False):
    linea = '[%s] %s' % (titulo, texto)
    if dry:
        print('(no enviado) ' + linea)
        return True
    secreto = _env('NOTIF_SECRET')
    if not secreto or not DESTINATARIOS:
        print('sin secreto o sin destinatarios: ' + linea)
        return False
    try:
        r = requests.post(CHAT_NOTIF_URL, timeout=6,
                          headers={'X-Notif-Secret': secreto},
                          json={'usuario_ids': DESTINATARIOS, 'tipo': 'soporte',
                                'titulo': titulo[:120], 'texto': texto[:300],
                                'url': 'https://datos.maquita.com.ec' + url, 'origen': 'telemetria'})
        print('%s -> %s' % (linea, r.status_code))
        return r.status_code == 200
    except Exception as e:
        print('fallo el aviso (%s): %s' % (type(e).__name__, linea))
        return False


def _es_anterior(version, vigente):
    """True solo si `version` es REALMENTE anterior a `vigente` (comparacion numerica).
    Un equipo con una version mas nueva que la publicada (una prueba) no es una alerta."""
    def partes(v):
        try:
            return tuple(int(x) for x in str(v).strip().split('.'))
        except Exception:
            return None
    a, b = partes(version), partes(vigente)
    if a is None or b is None:
        return False
    return a < b


def regla_version_vieja(cur, vigente, dry):
    """(a) equipos activos que siguen con una version anterior a la vigente."""
    if not vigente:
        return 0
    cur.execute("""
        SELECT equipo, max(usuario), max(version) FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '24 hours' AND version <> '' AND equipo <> ''
        GROUP BY equipo HAVING max(version) <> %s
    """, (vigente,))
    filas = cur.fetchall()
    enviados = 0
    for equipo, usuario, version in filas:
        if not _es_anterior(version, vigente):
            continue          # version igual o mas nueva (equipo de pruebas): no es alerta
        clave = 'version-vieja:%s:%s' % (equipo, version)
        if ya_avisado(cur, clave, 12):
            continue
        texto = '%s (%s) sigue en %s; la vigente es %s. Se actualiza sola al abrir la app.' % (
            equipo, usuario or 'sin usuario', version, vigente)
        if avisar('App desactualizada', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_error_repetido(cur, dry):
    """(b) el mismo error 3 o mas veces en la ultima hora."""
    cur.execute("""
        SELECT equipo, usuario, modulo, left(detalle, 90) AS d, count(*) AS veces
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '60 minutes' AND nivel IN ('error', 'critico')
        GROUP BY 1, 2, 3, 4 HAVING count(*) >= 3 ORDER BY veces DESC LIMIT 10
    """)
    enviados = 0
    for equipo, usuario, modulo, detalle, veces in cur.fetchall():
        clave = 'error-repetido:' + hashlib.sha1(('%s|%s|%s' % (equipo, modulo, detalle)).encode()).hexdigest()[:16]
        if ya_avisado(cur, clave, 3):
            continue
        texto = '%s en %s: %d veces en una hora (%s) - %s' % (
            equipo or 'equipo sin nombre', modulo or 'la app', veces, usuario or 'sin usuario', detalle)
        if avisar('Error repetido en la app', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_oleada_sesion(cur, dry):
    """(c) oleada de fallos de sesion o peticiones de login (problema de tokens)."""
    cur.execute("""
        SELECT count(*), count(DISTINCT equipo) FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '30 minutes'
          AND evento IN ('sesion_fallo', 'pide_login', 'login_fallo')
    """)
    total, equipos = cur.fetchone()
    if (total or 0) < 5:
        return 0
    clave = 'oleada-sesion'
    if ya_avisado(cur, clave, 1):
        return 0
    texto = '%d fallos de sesion en 30 minutos en %d equipo(s). Suele ser un problema de tokens o un reinicio del backend.' % (total, equipos)
    if avisar('Oleada de fallos de sesion', texto, dry=dry):
        marcar(cur, clave, texto); return 1
    return 0


def regla_oleada_sin_red(cur, dry):
    """(d) oleada de «sin conexion» de un mismo modulo (posible servicio caido)."""
    cur.execute("""
        SELECT COALESCE(NULLIF(modulo, ''), 'sin modulo'), count(*), count(DISTINCT equipo)
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '30 minutes'
          AND evento IN ('modulo_sin_red', 'sin_conexion')
        GROUP BY 1 HAVING count(*) >= 5
    """)
    enviados = 0
    for modulo, total, equipos in cur.fetchall():
        clave = 'oleada-sin-red:%s' % modulo
        if ya_avisado(cur, clave, 1):
            continue
        texto = '%s no responde para %d equipo(s): %d avisos de «sin conexion» en 30 minutos.' % (modulo, equipos, total)
        if avisar('Posible servicio caido', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_ui_congelada(cur, dry):
    """(e) ventanas que se congelan: el cliente reporta `ui_congelada` con la duración.
    Avisa si un equipo acumula 3 o más congelamientos en una hora, o si uno solo
    pasó de 30 s (una ventana colgada esa cantidad de tiempo ya la sufre la persona)."""
    cur.execute("""
        SELECT equipo, max(usuario), count(*) AS veces,
               max(COALESCE(NULLIF(regexp_replace(detalle, '[^0-9]', '', 'g'), ''), '0')::int) AS peor,
               max(COALESCE(NULLIF(modulo, ''), 'la app')) AS modulo
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '60 minutes' AND evento = 'ui_congelada'
        GROUP BY equipo
        HAVING count(*) >= 3
            OR max(COALESCE(NULLIF(regexp_replace(detalle, '[^0-9]', '', 'g'), ''), '0')::int) >= 30
    """)
    enviados = 0
    for equipo, usuario, veces, peor, modulo in cur.fetchall():
        clave = 'ui-congelada:%s' % equipo
        if ya_avisado(cur, clave, 2):
            continue
        texto = ('%s (%s): la ventana se congelo %d vez(ces) en una hora, la peor %d s, en %s. '
                 'Suele ser un bucle de la pagina o falta de memoria.' % (
                     equipo, usuario or 'sin usuario', veces, peor, modulo))
        if avisar('Ventana congelada en un equipo', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_webview_reconstruido(cur, dry):
    """(f) el navegador embebido se cae y la app se rehace sola: si pasa 3 o más veces
    en una hora en el mismo equipo, algo lo está matando y hay que mirarlo."""
    cur.execute("""
        SELECT equipo, max(usuario) AS usuario, count(*) AS veces,
               max(COALESCE(NULLIF(modulo, ''), 'la app')) AS modulo,
               max(left(detalle, 90)) AS motivo
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '60 minutes' AND evento = 'webview_reconstruido'
        GROUP BY equipo HAVING count(*) >= 3
    """)
    enviados = 0
    for equipo, usuario, veces, modulo, motivo in cur.fetchall():
        clave = 'webview-reconstruido:%s' % equipo
        if ya_avisado(cur, clave, 2):
            continue
        texto = ('%s (%s): el navegador de la app se cayo y se rehizo %d veces en una hora '
                 '(%s). Motivo: %s. Revisar memoria del equipo o el runtime WebView2.' % (
                     equipo, usuario or 'sin usuario', veces, modulo, motivo or 'sin detalle'))
        if avisar('El navegador de la app se cae seguido', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_socket_chat(cur, dry):
    """(g) el socket de notificaciones se cae: si pasa 3 o más veces en una hora, esa
    persona se está quedando sin avisos de chat aunque la app parezca normal."""
    cur.execute("""
        SELECT equipo, max(usuario) AS usuario, count(*) AS veces, max(left(detalle, 90)) AS motivo
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '60 minutes'
          AND evento IN ('socket_chat_perdido', 'socket_chat_error')
        GROUP BY equipo HAVING count(*) >= 3
    """)
    enviados = 0
    for equipo, usuario, veces, motivo in cur.fetchall():
        clave = 'socket-chat:%s' % equipo
        if ya_avisado(cur, clave, 2):
            continue
        texto = ('%s (%s): el canal de notificaciones del chat se cayo %d veces en una hora. '
                 'Esa persona puede estar sin avisos. Motivo: %s' % (
                     equipo, usuario or 'sin usuario', veces, motivo or 'sin detalle'))
        if avisar('Se cae el canal de notificaciones', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def regla_sin_sesion(cur, dry):
    """(h) el socket salio sin la cookie chat_session: esa persona queda FUERA de su sala
    de notificaciones, o sea sin avisos de chat, hasta que la app recargue. Basta una vez
    para avisar: es la causa raiz de T-47."""
    cur.execute("""
        SELECT equipo, max(usuario) AS usuario, count(*) AS veces, max(version) AS version
        FROM app_telemetria
        WHERE recibido > NOW() - INTERVAL '60 minutes'
          AND evento = 'socket_sin_chat_session'
        GROUP BY equipo
    """)
    enviados = 0
    for equipo, usuario, veces, version in cur.fetchall():
        clave = 'sin-sesion:%s' % equipo
        if ya_avisado(cur, clave, 2):
            continue
        texto = ('%s (%s, version %s): el canal de notificaciones abrio SIN la cookie de '
                 'sesion %d vez/veces en una hora. Mientras dura, esa persona no recibe '
                 'avisos de chat. La app deberia recargar sola; si se repite, revisar el '
                 'inicio de sesion en ese equipo.' % (equipo, usuario or 'sin usuario',
                                                      version or 'desconocida', veces))
        if avisar('Canal de notificaciones sin sesion', texto, dry=dry):
            marcar(cur, clave, texto); enviados += 1
    return enviados


def main():
    dry = '--dry-run' in sys.argv
    vigente = version_vigente()
    con = conectar()
    con.autocommit = True
    with con.cursor() as cur:
        cur.execute(DDL)
        total = (regla_version_vieja(cur, vigente, dry)
                 + regla_error_repetido(cur, dry)
                 + regla_oleada_sesion(cur, dry)
                 + regla_oleada_sin_red(cur, dry)
                 + regla_ui_congelada(cur, dry)
                 + regla_webview_reconstruido(cur, dry)
                 + regla_socket_chat(cur, dry)
                 + regla_sin_sesion(cur, dry))
    con.close()
    print('alertas enviadas: %d (version vigente: %s)%s' % (total, vigente or '?', ' [simulacion]' if dry else ''))


if __name__ == '__main__':
    main()
