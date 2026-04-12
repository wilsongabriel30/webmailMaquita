"""Interacciones — historial de emails enviados/recibidos con un contacto + stats."""
import re
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.clients.imap_client import get_imap_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _decode_lines(lines) -> list[str]:
    result = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            result.append(line.decode("utf-8", errors="replace"))
        elif isinstance(line, str):
            result.append(line)
    return result


async def _get_contact_email(db, contact_id: int, username: str) -> str:
    """Obtiene el email de un contacto verificando ownership."""
    row = await db.fetchrow(
        "SELECT email FROM user_contacts WHERE id = $1 AND owner = $2 AND deleted_at IS NULL",
        contact_id, username,
    )
    if not row:
        raise HTTPException(404, "Contacto no encontrado")
    return row["email"].strip().lower()


async def _search_folder(imap, folder: str, search_criteria: str, direction: str, limit: int = 50) -> list[dict]:
    """Busca emails en una carpeta IMAP y retorna lista de interacciones."""
    results = []
    try:
        resp = await imap.select(folder)
        if resp.result != "OK":
            return results

        search_resp = await imap.uid_search(*search_criteria.split(" ", 1))
        if search_resp.result != "OK":
            return results

        uids = []
        for line in _decode_lines(search_resp.lines):
            line = line.strip()
            if line and not line.endswith("completed."):
                uids.extend(int(x) for x in line.split() if x.isdigit())

        if not uids:
            return results

        # Tomar los más recientes
        uids.sort(reverse=True)
        uids = uids[:limit]
        uid_set = ",".join(str(u) for u in uids)

        fetch_resp = await imap.uid(
            "fetch", uid_set,
            "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])",
        )
        if fetch_resp.result != "OK":
            return results

        current_uid = None
        subject = ""
        date_str = ""
        for line in _decode_lines(fetch_resp.lines):
            uid_m = re.search(r"UID\s+(\d+)", line)
            if uid_m:
                if current_uid and (subject or date_str):
                    results.append({
                        "uid": current_uid,
                        "subject": subject,
                        "date": date_str,
                        "direction": direction,
                        "folder": folder,
                    })
                current_uid = int(uid_m.group(1))
                subject = ""
                date_str = ""
            subj_m = re.search(r"^Subject:\s*(.+)", line, re.IGNORECASE)
            if subj_m:
                subject = subj_m.group(1).strip()
            date_m = re.search(r"^Date:\s*(.+)", line, re.IGNORECASE)
            if date_m:
                date_str = date_m.group(1).strip()

        # Último pendiente
        if current_uid and (subject or date_str):
            results.append({
                "uid": current_uid,
                "subject": subject,
                "date": date_str,
                "direction": direction,
                "folder": folder,
            })
    except Exception as e:
        logger.warning(f"Error buscando en {folder}: {e}")
    return results


def _parse_date_for_sort(date_str: str) -> datetime:
    """Intenta parsear fecha de email para ordenar."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M:%S",
    ]
    clean = re.sub(r"\s*\(.*?\)\s*$", "", date_str.strip())
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return datetime.min.replace(tzinfo=timezone.utc)


@router.get("/{contact_id}/interactions")
async def get_interactions(
    contact_id: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Retorna historial de emails enviados/recibidos con un contacto."""
    db = request.app.state.db_pool
    contact_email = await _get_contact_email(db, contact_id, username)

    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        # Emails enviados a este contacto
        sent = await _search_folder(imap, "Sent", f"TO {contact_email}", "sent", 50)
        # Emails recibidos de este contacto
        received = await _search_folder(imap, "INBOX", f"FROM {contact_email}", "received", 50)

        # Combinar y ordenar por fecha DESC
        all_interactions = sent + received
        all_interactions.sort(key=lambda x: _parse_date_for_sort(x["date"]), reverse=True)

        return {"interactions": all_interactions, "total": len(all_interactions)}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/{contact_id}/stats")
async def get_contact_stats(
    contact_id: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Retorna estadísticas de interacción con un contacto."""
    db = request.app.state.db_pool
    contact_email = await _get_contact_email(db, contact_id, username)

    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        sent = await _search_folder(imap, "Sent", f"TO {contact_email}", "sent", 200)
        received = await _search_folder(imap, "INBOX", f"FROM {contact_email}", "received", 200)

        total_sent = len(sent)
        total_received = len(received)

        sent_dates = [_parse_date_for_sort(s["date"]) for s in sent if s["date"]]
        recv_dates = [_parse_date_for_sort(r["date"]) for r in received if r["date"]]

        all_dates = [d for d in sent_dates + recv_dates if d != datetime.min.replace(tzinfo=timezone.utc)]

        last_sent = max(sent_dates).isoformat() if sent_dates and max(sent_dates) != datetime.min.replace(tzinfo=timezone.utc) else None
        last_received = max(recv_dates).isoformat() if recv_dates and max(recv_dates) != datetime.min.replace(tzinfo=timezone.utc) else None
        first_interaction = min(all_dates).isoformat() if all_dates else None

        return {
            "total_sent": total_sent,
            "total_received": total_received,
            "last_sent": last_sent,
            "last_received": last_received,
            "first_interaction": first_interaction,
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
