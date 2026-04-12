"""Avatars — lookup batch de nombres/iniciales por email."""
import json
from fastapi import APIRouter, Request, Depends
from app.auth.dependencies import get_current_user
from .helpers import compute_initials

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/avatars")
async def get_avatars(emails: str = "", request: Request = None, username: str = Depends(get_current_user)):
    """Dado un CSV de emails, retorna {email: {name, initials}} con cache Redis."""
    if not emails:
        return {}
    email_list = [e.strip().lower() for e in emails.split(",") if e.strip()]
    if not email_list or len(email_list) > 200:
        return {}

    redis = request.app.state.redis
    db = request.app.state.db_pool
    result = {}
    uncached = []

    # Buscar en cache primero
    for email in email_list:
        cached = await redis.get(f"avatar:{email}")
        if cached:
            try:
                result[email] = json.loads(cached)
            except (json.JSONDecodeError, TypeError):
                uncached.append(email)
        else:
            uncached.append(email)

    if not uncached:
        return result

    # Fuente 1: user_preferences (display_name configurado)
    rows = await db.fetch("""
        SELECT LOWER(m.username) AS email, COALESCE(up.display_name, '') AS display_name
        FROM mailbox m LEFT JOIN user_preferences up ON up.username = m.username
        WHERE LOWER(m.username) = ANY($1::text[])
    """, uncached)
    found = {}
    for row in rows:
        name = row["display_name"]
        if name and name.strip():
            found[row["email"]] = name.strip()

    # Fuente 2: mailbox name
    still_missing = [e for e in uncached if e not in found]
    if still_missing:
        rows = await db.fetch(
            "SELECT LOWER(username) AS email, COALESCE(name, '') AS name FROM mailbox WHERE LOWER(username) = ANY($1::text[])",
            still_missing
        )
        for row in rows:
            if row["name"] and row["name"].strip():
                found[row["email"]] = row["name"].strip()

    # Fuente 3: sent_recipients (historial de envío)
    still_missing = [e for e in uncached if e not in found]
    if still_missing:
        rows = await db.fetch("""
            SELECT LOWER(recipient_email) AS email, recipient_name AS name
            FROM sent_recipients WHERE LOWER(recipient_email) = ANY($1::text[])
            AND recipient_name IS NOT NULL AND recipient_name != '' LIMIT 500
        """, still_missing)
        for row in rows:
            if row["name"] and row["name"].strip() and row["email"] not in found:
                found[row["email"]] = row["name"].strip()

    # Fuente 4: user_contacts (contactos activos)
    still_missing = [e for e in uncached if e not in found]
    if still_missing:
        rows = await db.fetch("""
            SELECT LOWER(email) AS email, display_name AS name FROM user_contacts
            WHERE LOWER(email) = ANY($1::text[]) AND display_name != '' AND deleted_at IS NULL LIMIT 500
        """, still_missing)
        for row in rows:
            if row["name"] and row["name"].strip() and row["email"] not in found:
                found[row["email"]] = row["name"].strip()

    # Cachear resultados (10 min)
    for email in uncached:
        name = found.get(email, "")
        initials = compute_initials(name) if name else ""
        entry = {"name": name, "initials": initials}
        result[email] = entry
        await redis.set(f"avatar:{email}", json.dumps(entry), ex=600)

    return result
