"""Avisos de T-34 por el canal T-03 (evento `notificacion`, tipo `tarea`), FUERA del chat.
El servicio de notificaciones vive en el chat (POST /api/chat/notificaciones, sin sesión): se autentica con la cabecera
X-Notif-Secret = NOTIF_SECRET (mismo valor en el .env del backend y del chat). Nunca rompe la operación.
Además de la app (T-03), cada aviso llega por CORREO (desde Raíces Tareas <tareas@maquita.org>, SMTP local) y a la
campanita de Raíces (tabla `notifications` de la BD nomina, usuario por correo institucional). 28/08/2026."""
import logging

import httpx

import os

log = logging.getLogger(__name__)
CHAT = 'https://mail.maquita.org'
URL_TAREAS = 'https://mail.maquita.org/webmail/tasks?app=1&vista=seguimiento'


def url_tarea(tarea_id) -> str:
    return f'{URL_TAREAS}&tarea={tarea_id}'


_nombres = {'t': 0, 'd': {}}


def nombre(correo: str) -> str:
    """Nombre real según nómina (nombres.json, lo escribe jefes.py cada hora); si no está, se deriva del correo."""
    import json, time
    if time.time() - _nombres['t'] > 600:
        try:
            _nombres['d'] = json.load(open('/opt/maquita-webmail/backend/app/tareas/nombres.json', encoding='utf-8'))
        except Exception:
            pass
        _nombres['t'] = time.time()
    return _nombres['d'].get((correo or '').lower()) or (correo or '').split('@')[0].replace('.', ' ').title()


async def emitir(correos, titulo: str, texto: str, url: str, en_nombre_de: str, extra: dict | None = None,
                 db=None, card_id=None, tipo_registro: str = 'tarea', incluir_originador: bool = False) -> int:
    """Envía el aviso `tarea` a los correos indicados (se descarta al propio originador). Devuelve destinatarios."""
    correos = sorted({c for c in (correos or []) if c and (incluir_originador or c != en_nombre_de)})
    if not correos:
        return 0
    cuerpo = {'correos': correos, 'tipo': 'tarea', 'titulo': titulo[:120], 'texto': texto[:300], 'url': url,
              'origen': 'tareas', **(extra or {})}
    n = 0
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f'{CHAT}/api/chat/notificaciones', json=cuerpo, headers={'X-Notif-Secret': _secreto()})
            if r.status_code == 200:
                n = int((r.json() or {}).get('destinatarios') or 0)
            else:
                log.warning('aviso tarea %s: %s %s', tipo_registro, r.status_code, r.text[:120])
    except Exception as e:
        log.warning('aviso tarea %s: %s', tipo_registro, e)
    await _correo(correos, titulo, texto, url)
    await _campanita(correos, titulo, texto, url)
    if db is not None:
        try:
            for a in correos:
                await db.execute('INSERT INTO task_avisos (card_id, tipo, a, texto, enviado) VALUES ($1,$2,$3,$4,$5)',
                                 card_id, tipo_registro, a, texto[:300], n > 0)
        except Exception as e:
            log.warning('registro aviso: %s', e)
    return n


def _secreto() -> str:
    if os.getenv('NOTIF_SECRET'):
        return os.environ['NOTIF_SECRET']
    for l in open('/opt/maquita-webmail/backend/.env', encoding='utf-8'):
        if l.startswith('NOTIF_SECRET='):
            return l.split('=', 1)[1].strip()
    return ''


REMITENTE = 'Raíces Tareas <tareas@maquita.org>'
PIE = ('Este aviso también llega a la app Raíces para Windows, con notificaciones en el escritorio: '
       'descárgala en https://mail.maquita.org/app')


async def _correo(correos, titulo, texto, url):
    """Correo por cada aviso (SMTP local, sin TLS ni clave: el servidor de correo es esta misma máquina)."""
    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate, make_msgid
        from html import escape
        msg = MIMEMultipart('alternative')
        msg['From'] = REMITENTE; msg['To'] = ', '.join(correos); msg['Subject'] = f'[Tareas] {titulo}'
        msg['Date'] = formatdate(localtime=True); msg['Message-ID'] = make_msgid(domain='maquita.org')
        msg.attach(MIMEText(f'{titulo}\n\n{texto}\n\nAbrir la tarea: {url}\n\n{PIE}', 'plain', 'utf-8'))
        msg.attach(MIMEText(f'<div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#233">'
                            f'<h3 style="margin:0 0 8px;color:#1b5e3a">{escape(titulo)}</h3><p>{escape(texto)}</p>'
                            f'<p><a href="{escape(url)}" style="background:#1b7f4a;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">Abrir la tarea</a></p>'
                            f'<p style="color:#667;font-size:13px">{escape(PIE)}</p></div>', 'html', 'utf-8'))
        await aiosmtplib.send(msg, hostname='127.0.0.1', port=25, start_tls=False, timeout=15)
    except Exception as e:
        log.warning('correo de aviso: %s', e)


async def _campanita(correos, titulo, texto, url):
    """Notificación en la campanita de Raíces (misma tabla que usa el sistema: notifications de la BD nomina)."""
    try:
        import asyncpg
        from app.tareas.servicio import _nomina_dsn
        con = await asyncpg.connect(_nomina_dsn(), timeout=5)
        try:
            for c in correos:
                uid = await con.fetchval("""SELECT u.id FROM usuarios u LEFT JOIN trabajadores t ON t.id = u.trabajador_id
                                            WHERE lower(u.email) = $1 OR lower(t.email_institucional) = $1
                                            ORDER BY u.active DESC NULLS LAST, u.last_login DESC NULLS LAST LIMIT 1""", c.lower())
                if uid:
                    await con.execute("""INSERT INTO notifications (user_id, type, title, message, action_url, reference_type, is_read, created_at)
                                         VALUES ($1, 'tarea', $2, $3, $4, 'tarea', false, now())""", uid, titulo[:255], texto, url)
        finally:
            await con.close()
    except Exception as e:
        log.warning('campanita de aviso: %s', e)
