"""Communication Compliance — escaneo de comunicaciones según políticas del admin.

A diferencia de DLP (que avisa/bloquea al remitente sobre SUS datos), esto
MONITOREA el contenido según políticas (conducta, términos confidenciales, etc.)
y crea entradas en una cola de revisión para el área de cumplimiento. No bloquea.
"""
from __future__ import annotations
import json
import re

_TAG_RE = re.compile(r"<[^>]+>")


def _strip(html: str) -> str:
    if not html:
        return ""
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    txt = _TAG_RE.sub(" ", txt)
    return re.sub(r"\s+", " ", txt).strip()


async def get_policies(db, direction: str):
    try:
        return await db.fetch(
            "SELECT id, name, terms, scope, severity FROM comm_policies "
            "WHERE enabled AND (scope = 'all' OR scope = $1)", direction)
    except Exception:
        return []


async def scan(db, username: str, direction: str, recipients,
               subject: str = "", text_body: str = "", html_body: str = "") -> int:
    policies = await get_policies(db, direction)
    if not policies:
        return 0
    blob = " ".join([subject or "", text_body or "", _strip(html_body)])
    low = blob.lower()
    flagged = 0
    for p in policies:
        terms = p["terms"]
        if isinstance(terms, str):
            try:
                terms = json.loads(terms or "[]")
            except ValueError:
                terms = []
        matched = []
        for t in (terms or []):
            t = (t or "").strip().lower()
            if t and re.search(r"\b" + re.escape(t) + r"\b", low):
                matched.append(t)
        if not matched:
            continue
        snippet = (blob[:240] + ("…" if len(blob) > 240 else "")).strip()
        try:
            await db.execute(
                "INSERT INTO comm_flags (policy_id, policy_name, username, direction, recipients, "
                "subject, snippet, matched_terms, severity) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                p["id"], p["name"], username, direction,
                json.dumps(recipients if isinstance(recipients, list) else [recipients]),
                (subject or "")[:500], snippet, json.dumps(sorted(set(matched))), p["severity"])
            flagged += 1
        except Exception:
            pass
    return flagged
