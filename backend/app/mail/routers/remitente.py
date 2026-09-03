"""
Remitente externo — Maquita Webmail
===================================
Marca los correos cuyo remitente es de FUERA de la organización (banner discreto,
no de alarma), con la posibilidad de "marcar como conocido": el remitente se agrega
a los contactos del usuario (tabla user_contacts) y el banner deja de salir para él.

- externo  = el dominio del remitente NO está en la tabla `domain` (dominios hospedados).
- conocido = el remitente ya es un contacto del usuario (o fue marcado como conocido).
"""
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail", tags=["mail"])


def _dominio(email: str) -> str:
    email = (email or "").strip().lower()
    return email.split("@", 1)[1] if "@" in email else ""


async def _es_externo(db, email: str) -> bool:
    dom = _dominio(email)
    if not dom:
        return False
    interno = await db.fetchval(
        "SELECT 1 FROM domain WHERE active = true AND LOWER(domain) = $1", dom
    )
    return not bool(interno)


async def _es_conocido(db, username: str, email: str) -> bool:
    email = (email or "").strip().lower()
    if not email:
        return False
    row = await db.fetchval(
        "SELECT 1 FROM user_contacts "
        "WHERE owner = $1 AND LOWER(email) = $2 AND deleted_at IS NULL",
        username, email,
    )
    return bool(row)


@router.get("/remitente-estado")
async def remitente_estado(request: Request, email: str, username: str = Depends(get_current_user)):
    """Dice si el remitente es externo y si ya es un contacto conocido del usuario."""
    db = request.app.state.db_pool
    externo = await _es_externo(db, email)
    conocido = await _es_conocido(db, username, email) if externo else False
    return {"externo": externo, "conocido": conocido}


@router.post("/remitente-conocido")
async def remitente_conocido(request: Request, username: str = Depends(get_current_user)):
    """Marca un remitente externo como conocido -> lo agrega a los contactos del usuario.
    Idempotente: si ya es contacto, no duplica."""
    body = await request.json()
    email = (body.get("email") or "").strip()
    nombre = (body.get("nombre") or "").strip() or email
    if not email or "@" not in email:
        raise HTTPException(400, "Email de remitente inválido")
    db = request.app.state.db_pool
    ya = await db.fetchval(
        "SELECT id FROM user_contacts "
        "WHERE owner = $1 AND LOWER(email) = LOWER($2) AND deleted_at IS NULL",
        username, email,
    )
    if not ya:
        await db.execute(
            "INSERT INTO user_contacts (owner, display_name, email, source) "
            "VALUES ($1, $2, $3, 'remitente_conocido')",
            username, nombre, email,
        )
        logger.info("Remitente marcado como conocido: %s -> %s", username, email)
    return {"ok": True, "conocido": True}
