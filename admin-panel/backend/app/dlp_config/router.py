"""Protección de datos (DLP) — configuración desde el panel admin.

Permite activar/desactivar la prevención de fuga de datos, elegir la acción por
tipo de dato (advertir / bloquear / solo registrar), gestionar palabras clave y
ver la actividad reciente. Tablas: dlp_config (fila única), dlp_keywords,
dlp_violations.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/dlp-config", tags=["dlp-config"])

DATA_TYPES = ["cedula", "ruc", "tarjeta", "iban", "cuenta", "keyword"]
DEFAULT_RULES = {t: {"enabled": True, "action": None} for t in DATA_TYPES}


def _db(r: Request):
    return r.app.state.db


class RuleIn(BaseModel):
    enabled: bool = True
    action: str | None = None   # None => usar default_action


class DlpConfigIn(BaseModel):
    enabled: bool = True
    default_action: str = "warn"          # warn | block | audit
    rules: dict[str, RuleIn] = {}
    keywords: list[str] = []
    milter_enforce: bool = False        # rechazar en servidor (Outlook/movil)
    scan_attachments: bool = True       # revisar contenido de adjuntos
    trusted_domains: list[str] = []     # dominios externos de confianza
    remitentes_exentos: list[str] = []  # remitentes que pueden enviar datos sensibles fuera


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow(
        "SELECT enabled, default_action, rules, COALESCE(milter_enforce,false) AS milter_enforce, "
        "COALESCE(scan_attachments,true) AS scan_attachments, COALESCE(trusted_domains,'[]'::jsonb) AS trusted_domains, "
        "COALESCE(remitentes_exentos,'[]'::jsonb) AS remitentes_exentos "
        "FROM dlp_config WHERE id = 1")
    rules = dict(DEFAULT_RULES)
    enabled, default_action = True, "warn"
    if row:
        enabled = row["enabled"]
        default_action = row["default_action"] or "warn"
        r = row["rules"]
        if isinstance(r, str):
            try:
                r = json.loads(r or "{}")
            except ValueError:
                r = {}
        for k, v in (r or {}).items():
            rules[k] = {**DEFAULT_RULES.get(k, {"enabled": True, "action": None}), **(v or {})}
    kw_rows = await _db(request).fetch("SELECT term FROM dlp_keywords ORDER BY term")
    td = row["trusted_domains"] if row else []
    if isinstance(td, str):
        try: td = json.loads(td or "[]")
        except ValueError: td = []
    ex = row["remitentes_exentos"] if row else []
    if isinstance(ex, str):
        try: ex = json.loads(ex or "[]")
        except ValueError: ex = []
    return {
        "enabled": enabled,
        "default_action": default_action,
        "rules": rules,
        "keywords": [r["term"] for r in kw_rows],
        "milter_enforce": bool(row["milter_enforce"]) if row else False,
        "scan_attachments": bool(row["scan_attachments"]) if row else True,
        "trusted_domains": list(td or []),
        # Remitentes que pueden enviar datos sensibles fuera. La violación se
        # SIGUE registrando: solo cambia que el correo sale. Caso real: nómina.
        "remitentes_exentos": list(ex or []),
    }


@router.put("")
async def save_config(body: DlpConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    if body.default_action not in ("warn", "block", "audit"):
        body.default_action = "warn"
    rules = {}
    for t in DATA_TYPES:
        r = body.rules.get(t)
        if r is None:
            rules[t] = {"enabled": True, "action": None}
        else:
            act = r.action if r.action in ("warn", "block", "audit") else None
            rules[t] = {"enabled": bool(r.enabled), "action": act}

    await _db(request).execute(
        """
        INSERT INTO dlp_config (id, enabled, default_action, rules, milter_enforce, scan_attachments, trusted_domains, remitentes_exentos, updated_at)
        VALUES (1, $1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, now())
        ON CONFLICT (id) DO UPDATE SET
          enabled = EXCLUDED.enabled, default_action = EXCLUDED.default_action,
          rules = EXCLUDED.rules, milter_enforce = EXCLUDED.milter_enforce,
          scan_attachments = EXCLUDED.scan_attachments, trusted_domains = EXCLUDED.trusted_domains,
          remitentes_exentos = EXCLUDED.remitentes_exentos,
          updated_at = now()
        """,
        body.enabled, body.default_action, json.dumps(rules), bool(body.milter_enforce),
        bool(body.scan_attachments),
        json.dumps(sorted({(d or "").strip().lower().lstrip("@") for d in body.trusted_domains if (d or "").strip()})),
        json.dumps(sorted({(x or "").strip().lower() for x in body.remitentes_exentos if (x or "").strip() and "@" in x})))

    # Reemplazar palabras clave (set completo)
    terms = sorted({(k or "").strip() for k in body.keywords if (k or "").strip()})
    await _db(request).execute("DELETE FROM dlp_keywords")
    for t in terms:
        await _db(request).execute(
            "INSERT INTO dlp_keywords (term) VALUES ($1) ON CONFLICT (term) DO NOTHING", t[:120])

    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "dlp_config_update",
        f"enabled={body.enabled} action={body.default_action} smtp_reject={body.milter_enforce} adjuntos={body.scan_attachments}",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True}


@router.get("/violations")
async def list_violations(request: Request, admin: dict = Depends(get_current_admin),
                          limit: int = 50):
    limit = max(1, min(limit, 200))
    rows = await _db(request).fetch(
        "SELECT username, recipients, subject, data_types, action, overridden, created_at, reason, external "
        "FROM dlp_violations ORDER BY created_at DESC LIMIT $1", limit)
    out = []
    for r in rows:
        rec = r["recipients"]
        dt = r["data_types"]
        if isinstance(rec, str):
            try: rec = json.loads(rec)
            except ValueError: rec = []
        if isinstance(dt, str):
            try: dt = json.loads(dt)
            except ValueError: dt = []
        out.append({
            "username": r["username"],
            "recipients": rec,
            "subject": r["subject"],
            "data_types": dt,
            "action": r["action"],
            "overridden": r["overridden"],
            "reason": r["reason"],
            "external": bool(r["external"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return {"violations": out}
