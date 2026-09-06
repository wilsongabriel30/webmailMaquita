"""
DLP — Servicio: lee configuracion de la BD, ejecuta los detectores y decide
la accion (allow / audit / warn / block) por tipo de dato. Tambien registra
violaciones para auditoria del admin.
"""

from __future__ import annotations

import json
import re

from .detectors import detect_all

# Reglas por defecto (si la BD no las tiene). action=None => usa default_action.
DEFAULT_RULES = {
    "cedula": {"enabled": True, "action": None},
    "ruc": {"enabled": True, "action": None},
    "tarjeta": {"enabled": True, "action": None},
    "iban": {"enabled": True, "action": None},
    "cuenta": {"enabled": True, "action": None},
    "keyword": {"enabled": True, "action": None},
}
_SEVERITY = {"allow": 0, "audit": 1, "warn": 2, "block": 3}


def _strip_html(html: str) -> str:
    if not html:
        return ""
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = (
        txt.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"\s+", " ", txt)


async def get_config(db) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT enabled, default_action, rules, "
            "COALESCE(milter_enforce,false) AS milter_enforce, "
            "COALESCE(scan_attachments,true) AS scan_attachments FROM dlp_config WHERE id = 1"
        )
    except Exception:
        return {
            "enabled": False,
            "default_action": "warn",
            "rules": dict(DEFAULT_RULES),
        }
    if not row:
        return {
            "enabled": False,
            "default_action": "warn",
            "rules": dict(DEFAULT_RULES),
        }
    rules = row["rules"]
    if isinstance(rules, str):
        try:
            rules = json.loads(rules or "{}")
        except ValueError:
            rules = {}
    merged = dict(DEFAULT_RULES)
    for k, v in (rules or {}).items():
        merged[k] = {
            **DEFAULT_RULES.get(k, {"enabled": True, "action": None}),
            **(v or {}),
        }
    return {
        "enabled": bool(row["enabled"]),
        "default_action": row["default_action"] or "warn",
        "rules": merged,
        "milter_enforce": bool(row["milter_enforce"]),
        "scan_attachments": bool(row["scan_attachments"]),
    }


async def get_keywords(db) -> list[str]:
    try:
        rows = await db.fetch("SELECT term FROM dlp_keywords ORDER BY term")
        return [r["term"] for r in rows]
    except Exception:
        return []


async def scan(db, subject: str = "", text_body: str = "", html_body: str = "") -> dict:
    """Analiza un correo saliente. Devuelve {enabled, action, findings[]}.

    action global = la mas severa entre los hallazgos (allow<audit<warn<block).
    """
    cfg = await get_config(db)
    if not cfg["enabled"]:
        return {"enabled": False, "action": "allow", "findings": []}

    keywords = await get_keywords(db)
    blob = "\n".join([subject or "", text_body or "", _strip_html(html_body)])
    raw = detect_all(blob, keywords)

    findings, worst = [], "allow"
    for f in raw:
        rule = cfg["rules"].get(f.data_type, {"enabled": True, "action": None})
        if not rule.get("enabled", True):
            continue
        action = rule.get("action") or cfg["default_action"]
        findings.append(
            {
                "type": f.data_type,
                "label": f.label,
                "sample": f.sample,
                "count": f.count,
                "action": action,
            }
        )
        if _SEVERITY.get(action, 0) > _SEVERITY.get(worst, 0):
            worst = action
    if not findings:
        worst = "allow"
    return {"enabled": True, "action": worst, "findings": findings}


async def log_violation(
    db,
    username: str,
    recipients,
    subject: str,
    findings: list[dict],
    action: str,
    overridden: bool,
    reason: str | None = None,
    external: bool = False,
) -> None:
    try:
        await db.execute(
            "INSERT INTO dlp_violations (username, recipients, subject, data_types, action, overridden, reason, external) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            username,
            json.dumps(recipients if isinstance(recipients, list) else [recipients]),
            (subject or "")[:500],
            json.dumps(sorted({f["type"] for f in findings})),
            action,
            overridden,
            (reason or None),
            bool(external),
        )
    except Exception:
        pass  # auditoria nunca debe romper el envio
