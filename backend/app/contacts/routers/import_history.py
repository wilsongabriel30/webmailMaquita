"""Importar contactos desde el historial de correo (remitentes y destinatarios).

Recorre INBOX (remitentes) y Enviados (destinatarios), extrae las direcciones
únicas con su nombre, descarta las que ya son contactos y crea el resto.
Es lo que hace que la agenda deje de estar vacía tras años de correos.
"""
import os
import re as _re

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# "Nombre Apellido <correo@dominio>" | "correo@dominio"
_RE_DIR = _re.compile(r'^\s*(?:"?([^"<]*?)"?\s*)?<?([^<>@\s]+@[^<>@\s]+\.[^<>@\s]+)>?\s*$')
# Remitentes automáticos que no son personas (no ensucian la agenda)
_IGNORAR = ('no-reply', 'noreply', 'no_reply', 'mailer-daemon', 'postmaster',
            'notifications@', 'notification@', 'bounce', 'donotreply', 'do-not-reply',
            'automated', 'newsletter', 'noreply@', 'alertas@', 'notificaciones@')


def _parse(cadena: str):
    """De un header From/To saca (nombre, correo) del PRIMER destinatario válido."""
    if not cadena:
        return None
    # tomar solo la primera direccion si vienen varias
    primera = cadena.split(',')[0]
    m = _RE_DIR.match(primera.strip())
    if not m:
        return None
    nombre = (m.group(1) or '').strip()
    correo = m.group(2).strip().lower()
    if any(x in correo for x in _IGNORAR):
        return None
    return nombre, correo


@router.post("/import/from-history")
async def import_from_history(request: Request, username: str = Depends(get_current_user)):
    """Crea contactos a partir de los correos. Devuelve {importados, revisados, total}."""
    limite = int(os.getenv("CONTACTS_HISTORY_LIMIT", "1500"))
    db = request.app.state.db_pool
    password = await get_user_password(request, username)

    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import list_messages

    # direcciones únicas: correo -> nombre (preferimos el nombre no vacío)
    candidatos: dict[str, str] = {}
    revisados = 0
    imap = await get_imap_connection(username, password)
    try:
        # INBOX: los remitentes. Enviados: los destinatarios (a quién le escribes).
        for carpeta, campo in (("INBOX", "from"), ("Sent", "to"), ("Enviados", "to")):
            try:
                res = await list_messages(imap, carpeta, 1, limite, "")
            except Exception:
                continue
            for m in (res or {}).get("messages", []) or []:
                revisados += 1
                parsed = _parse(m.get(campo, ""))
                if not parsed:
                    continue
                nombre, correo = parsed
                if correo == username.lower():
                    continue
                if correo not in candidatos or (nombre and not candidatos[correo]):
                    candidatos[correo] = nombre
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    if not candidatos:
        return {"importados": 0, "revisados": revisados, "total": 0,
                "mensaje": "No se encontraron direcciones nuevas en el historial."}

    # ya existentes (por correo) para no duplicar
    filas = await db.fetch(
        "SELECT LOWER(email) AS e FROM user_contacts WHERE owner=$1 AND deleted_at IS NULL",
        username)
    existentes = {r["e"] for r in filas}

    importados = 0
    for correo, nombre in candidatos.items():
        if correo in existentes:
            continue
        n = nombre or correo.split("@")[0].replace(".", " ").title()
        partes = n.split()
        first = partes[0] if partes else n
        last = " ".join(partes[1:]) if len(partes) > 1 else ""
        try:
            await db.execute(
                "INSERT INTO user_contacts (owner, display_name, email, first_name, last_name, source) "
                "VALUES ($1,$2,$3,$4,$5,'historial')",
                username, n, correo, first, last)
            importados += 1
        except Exception:
            pass

    total = await db.fetchval(
        "SELECT COUNT(*) FROM user_contacts WHERE owner=$1 AND deleted_at IS NULL", username)
    return {"importados": importados, "revisados": revisados, "total": total}
