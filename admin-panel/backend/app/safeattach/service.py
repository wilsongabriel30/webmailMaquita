"""Safe Attachments — servicio: escanea correos entregados, analiza adjuntos y
(según config) retira a cuarentena los que tengan adjuntos maliciosos.

Filosofía Maquita: MUEVE a cuarentena (no borra, reversible), modo SIMULACION por
defecto, fail-safe (ante error en un correo/usuario, lo salta y sigue).
Reusa el motor app.safeattach.analyzers + extract, y doveadm (igual que ZAP).
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta

import redis.asyncio as aioredis

from app.wrappers import doveadm
from app.safeattach.extract import scan_email

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SEV = {"clean": 0, "suspicious": 1, "malicious": 2}


def _redis_url() -> str:
    try:
        for line in open("/opt/maquita-webmail/backend/.env"):
            if line.startswith("REDIS_URL="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return "redis://localhost:6379/0"


async def _fetch_raw(user: str, guid: str, uid: str) -> bytes:
    out, _, rc = await doveadm._run(
        "doveadm", "fetch", "-u", user, "text", "mailbox-guid", guid, "uid", uid)
    return (out or "").encode("utf-8", "surrogateescape")


def _first_header(text: str, name: str) -> str:
    pat = re.compile(r"^" + re.escape(name) + r":\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    m = pat.search(text or "")
    return m.group(1).strip() if m else ""


async def _active_users(db) -> list[str]:
    rows = await db.fetch("SELECT username FROM mailbox WHERE active = true ORDER BY username")
    return [r["username"] for r in rows]


async def scan(db, *, only_user: str | None = None, force_dry: bool = False) -> dict:
    """Escanea adjuntos de correos recientes. NUNCA lanza excepción."""
    cfg = await db.fetchrow("SELECT * FROM safeattach_config WHERE id = 1")
    if not cfg or not cfg["enabled"]:
        return {"ok": False, "reason": "Safe Attachments deshabilitado"}

    enforce = bool(cfg["enforce"]) and not force_dry
    window_h = int(cfg["window_hours"])
    max_per_user = int(cfg["max_per_user"])
    qfolder = cfg["quarantine_folder"] or "Junk"
    quarantine_suspicious = bool(cfg["quarantine_suspicious"])
    act_min = SEV["suspicious"] if quarantine_suspicious else SEV["malicious"]
    since = (datetime.now() - timedelta(hours=window_h)).strftime("%Y-%m-%d")

    r = aioredis.from_url(_redis_url(), decode_responses=True)
    users = [only_user] if only_user else await _active_users(db)
    summary = {"ok": True, "enforce": enforce, "users": 0, "scanned": 0,
               "with_attach": 0, "flagged": 0, "moved": 0, "errors": 0, "since": since}

    for user in users:
        summary["users"] += 1
        try:
            msgs = await doveadm.search_messages(user, f"mailbox INBOX SINCE {since}")
        except Exception:
            summary["errors"] += 1
            continue
        for msg in msgs[:max_per_user]:
            guid, uid = msg.get("mailbox_guid"), msg.get("uid")
            if not guid or not uid:
                continue
            summary["scanned"] += 1
            try:
                raw = await _fetch_raw(user, guid, uid)
                if not raw:
                    continue
                res = scan_email(raw)
                if res["count"] == 0:
                    continue
                summary["with_attach"] += 1
                # reputacion por hash (feed MalwareBazaar en Redis) -- async, seguro
                for a in res["attachments"]:
                    try:
                        if await r.sismember("tintel:malhash", a["sha256"]):
                            a["verdict"] = "malicious"
                            a["reasons"].append("Hash en feed de malware (MalwareBazaar)")
                    except Exception:
                        pass
                worst = max((SEV.get(a["verdict"], 0) for a in res["attachments"]), default=0)
                if worst < act_min:
                    continue
                # hay adjunto que amerita acción
                text = raw.decode("utf-8", "ignore")
                sender = _first_header(text, "from")
                subject = _first_header(text, "subject")
                msgid = _first_header(text, "message-id")
                summary["flagged"] += 1

                status = "simulado"
                moved_done = False
                if enforce:
                    moved = await doveadm.move_message(user, qfolder, guid, uid)
                    if moved:
                        status = "cuarentena"
                        summary["moved"] += 1
                        moved_done = True
                    else:
                        status = "error"
                        summary["errors"] += 1
                # registrar cada adjunto problemático
                for a in res["attachments"]:
                    if SEV.get(a["verdict"], 0) < act_min:
                        continue
                    await db.execute(
                        "INSERT INTO safeattach_results (username, message_id, subject, sender, "
                        "filename, sha256, verdict, reasons, mailbox_from, uid, guid, status) "
                        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) "
                        "ON CONFLICT (username, message_id, sha256) DO UPDATE SET "
                        "status=EXCLUDED.status, verdict=EXCLUDED.verdict, reasons=EXCLUDED.reasons, created_at=now()",
                        user, msgid, (subject or "")[:500], (sender or "")[:255],
                        (a["filename"] or "")[:255], a["sha256"], a["verdict"],
                        "; ".join(a["reasons"])[:2000], "INBOX", str(uid), guid, status)
            except Exception:
                summary["errors"] += 1
                continue
    try:
        await r.aclose()
    except Exception:
        pass
    return summary


async def release_action(db, action_id: int) -> dict:
    """Suelta un correo retirado: lo devuelve de cuarentena a la bandeja. Por Message-ID."""
    row = await db.fetchrow("SELECT * FROM safeattach_results WHERE id = $1", action_id)
    if not row:
        return {"ok": False, "reason": "no existe"}
    if row["status"] == "liberado":
        return {"ok": True, "already": True}
    cfg = await db.fetchrow("SELECT quarantine_folder FROM safeattach_config WHERE id = 1")
    qfolder = (cfg["quarantine_folder"] if cfg else "Junk") or "Junk"
    user, msgid = row["username"], row["message_id"]
    if not msgid:
        return {"ok": False, "reason": "sin Message-ID; mover manualmente"}
    try:
        found = await doveadm.search_messages(user, f'mailbox {qfolder} HEADER Message-ID "{msgid}"')
    except Exception:
        found = []
    if not found:
        await db.execute("UPDATE safeattach_results SET status='liberado' WHERE message_id=$1 AND username=$2", msgid, user)
        return {"ok": True, "note": "no estaba en cuarentena"}
    ok = False
    for m in found:
        try:
            ok = await doveadm.move_message(user, "INBOX", m["mailbox_guid"], m["uid"]) or ok
        except Exception:
            pass
    if ok:
        await db.execute("UPDATE safeattach_results SET status='liberado' WHERE message_id=$1 AND username=$2", msgid, user)
    return {"ok": ok}
