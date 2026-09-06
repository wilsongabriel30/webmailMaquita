"""Score — cálculo y actualización de score de importancia de contactos."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user

from .helpers import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.post("/recalculate-scores")
async def recalculate_scores(
    request: Request,
    username: str = Depends(get_current_user),
):
    """Recalcula el score de importancia de todos los contactos del usuario.

    Fórmula:
      +10 por email enviado al contacto (max 100)
      +5 por email recibido del contacto (max 50)
      +20 si es favorito
      +15 si fue contactado en los últimos 7 días
      +10 si fue contactado en los últimos 30 días (y no en 7)
      +5 por cada lista a la que pertenece
    """
    db = request.app.state.db_pool

    # Obtener todos los contactos activos
    contacts = await db.fetch(
        "SELECT id, email, is_favorite, last_contacted_at FROM user_contacts "
        "WHERE owner = $1 AND deleted_at IS NULL",
        username,
    )

    if not contacts:
        return {"status": "ok", "updated": 0}

    now = datetime.now().astimezone()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Pre-cargar conteos de sent_recipients para todos los emails
    emails = [c["email"].strip().lower() for c in contacts if c["email"]]
    sent_counts = {}
    if emails:
        rows = await db.fetch(
            "SELECT LOWER(recipient_email) AS email, COUNT(*) AS cnt "
            "FROM sent_recipients WHERE LOWER(sender) = LOWER($1) "
            "AND LOWER(recipient_email) = ANY($2::text[]) "
            "GROUP BY LOWER(recipient_email)",
            username, emails,
        )
        for r in rows:
            sent_counts[r["email"]] = r["cnt"]

    # Pre-cargar conteos de listas por contacto
    list_counts = {}
    contact_ids = [c["id"] for c in contacts]
    if contact_ids:
        rows = await db.fetch(
            "SELECT contact_id, COUNT(*) AS cnt FROM contact_list_members "
            "WHERE contact_id = ANY($1::int[]) GROUP BY contact_id",
            contact_ids,
        )
        for r in rows:
            list_counts[r["contact_id"]] = r["cnt"]

    updated = 0
    for contact in contacts:
        score = 0
        email = contact["email"].strip().lower() if contact["email"] else ""

        # +10 por email enviado (max 100)
        sent_n = sent_counts.get(email, 0)
        score += min(sent_n * 10, 100)

        # +5 por email recibido (max 50) — usamos sent_recipients inverso
        recv_n = 0
        if email:
            recv_n = await db.fetchval(
                "SELECT COUNT(*) FROM sent_recipients "
                "WHERE LOWER(sender) = $1 AND LOWER(recipient_email) = LOWER($2)",
                email, username,
            ) or 0
        score += min(recv_n * 5, 50)

        # +20 si favorito
        if contact["is_favorite"]:
            score += 20

        # +15 si contactado en últimos 7 días, +10 si en últimos 30
        lca = contact["last_contacted_at"]
        if lca:
            if lca.tzinfo is None:
                from datetime import timezone
                lca = lca.replace(tzinfo=timezone.utc)
            if lca >= seven_days_ago:
                score += 15
            elif lca >= thirty_days_ago:
                score += 10

        # +5 por lista
        lists_n = list_counts.get(contact["id"], 0)
        score += lists_n * 5

        await db.execute(
            "UPDATE user_contacts SET contact_score = $1 WHERE id = $2",
            score, contact["id"],
        )
        updated += 1

    ip = request.client.host if request.client else ""
    await audit(db, username, None, "recalculate_scores", {"updated": updated}, ip)

    return {"status": "ok", "updated": updated}
