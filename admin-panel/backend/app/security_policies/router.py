"""Politicas de seguridad — anti-suplantacion, impersonation, DLP tarjetas (panel :8443)."""
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/security-policies", tags=["security-policies"])


def _db(r: Request):
    return r.app.state.db


class CfgIn(BaseModel):
    impersonation_enabled: bool
    impersonation_terms: list[str]
    dlp_block_cards_external: bool


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT impersonation_enabled, impersonation_terms, dlp_block_cards_external "
        "FROM security_config WHERE id = 1")
    try:
        domains = [r["domain"] for r in await db.fetch("SELECT domain FROM domain ORDER BY domain")]
    except Exception:
        domains = []
    return {
        "impersonation_enabled": bool(row["impersonation_enabled"]) if row else True,
        "impersonation_terms": list(row["impersonation_terms"]) if row and row["impersonation_terms"] else [],
        "dlp_block_cards_external": bool(row["dlp_block_cards_external"]) if row else True,
        "status": {
            "anti_spoof": True,
            "protected_domains": domains,
            "reject_score": 20,
        },
    }


@router.post("")
async def save_config(body: CfgIn, request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    terms = [t.strip().lower() for t in body.impersonation_terms if t and t.strip()]
    await db.execute(
        "UPDATE security_config SET impersonation_enabled = $1, impersonation_terms = $2, "
        "dlp_block_cards_external = $3, updated_at = now() WHERE id = 1",
        body.impersonation_enabled, terms, body.dlp_block_cards_external)
    return {"ok": True}
