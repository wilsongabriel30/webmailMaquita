"""ZAP — Zero-hour Auto Purge (retiro de correos ya entregados).

Re-evalúa correos entregados recientemente contra los feeds de amenazas
ACTUALIZADOS. Si un correo tiene un enlace a un dominio ahora confirmado como
malicioso, lo RETIRA a cuarentena (lo MUEVE, no lo borra) y queda registrado
para soltarlo desde el panel :8443.

Filosofía Maquita (NO perder correos):
- Por defecto solo actúa sobre MALWARE de alta confianza (URLhaus).
- Respeta la lista blanca de remitentes y los dominios locales.
- MUEVE a cuarentena (Junk), nunca borra. 100% reversible desde :8443.
- Modo SIMULACIÓN por defecto: registra qué retiraría, sin tocar nada.
- Fail-safe: ante cualquier error en un correo/usuario, lo salta y sigue.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta

import redis.asyncio as aioredis

from app.wrappers import doveadm

LOCAL_DOMAINS = {"maquita.org", "maquita.com.ec"}
WHITELIST_MAP = "/etc/rspamd/local.d/maps/whitelist_senders.map"
_URL_RE = re.compile(r'https?://([^/"\'\s>)\]}]+)', re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def _redis_url() -> str:
    try:
        for line in open("/opt/maquita-webmail/backend/.env"):
            if line.startswith("REDIS_URL="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return "redis://localhost:6379/0"


def _load_whitelist() -> set:
    out = set()
    try:
        for line in open(WHITELIST_MAP):
            line = line.strip().lower()
            if line and not line.startswith("#"):
                out.add(line)
    except Exception:
        pass
    return out


def _host_candidates(host: str):
    """a.b.c.com -> [a.b.c.com, b.c.com, c.com] (cubre subdominios)."""
    host = (host or "").strip().lower().rstrip(".")
    if "@" in host:                       # credenciales embebidas user@host
        host = host.split("@")[-1]
    host = host.split(":")[0]             # quitar puerto
    labels = [l for l in host.split(".") if l]
    cands = []
    for i in range(len(labels) - 1):
        cands.append(".".join(labels[i:]))
    return cands


def _is_local(host: str) -> bool:
    return any(c in LOCAL_DOMAINS for c in _host_candidates(host))


def _extract_hosts(text: str) -> set:
    hosts = set()
    for m in _URL_RE.finditer(text or ""):
        h = m.group(1).strip().lower()
        if "@" in h:
            h = h.split("@")[-1]
        h = h.split(":")[0].rstrip(".")
        if "." in h and h not in ("localhost",):
            hosts.add(h)
    return hosts


async def _fetch_text(user: str, guid: str, uid: str) -> str:
    out, _, rc = await doveadm._run(
        "doveadm", "fetch", "-u", user, "text",
        "mailbox-guid", guid, "uid", uid)
    return out or ""


async def _active_users(db) -> list[str]:
    rows = await db.fetch("SELECT username FROM mailbox WHERE active = true ORDER BY username")
    return [r["username"] for r in rows]


async def scan(db, *, only_user: str | None = None, force_dry: bool = False) -> dict:
    """Escanea y (según config) retira. Devuelve resumen. NUNCA lanza excepción.
    force_dry=True fuerza modo simulación aunque la config esté en enforce."""
    cfg = await db.fetchrow("SELECT * FROM zap_config WHERE id = 1")
    if not cfg or not cfg["enabled"]:
        return {"ok": False, "reason": "ZAP deshabilitado"}

    enforce = bool(cfg["enforce"]) and not force_dry
    window_h = int(cfg["window_hours"])
    include_phish = bool(cfg["include_phishing"])
    max_per_user = int(cfg["max_per_user"])
    qfolder = cfg["quarantine_folder"] or "Junk"
    since = (datetime.now() - timedelta(hours=window_h)).strftime("%Y-%m-%d")

    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        malware = set(await r.smembers("tintel:malware"))
    except Exception:
        malware = set()
    whitelist = _load_whitelist()

    users = [only_user] if only_user else await _active_users(db)
    summary = {"ok": True, "enforce": enforce, "users": 0, "scanned": 0,
               "flagged": 0, "moved": 0, "errors": 0, "since": since}

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
                text = await _fetch_text(user, guid, uid)
                if not text:
                    continue
                hosts = _extract_hosts(text)
                if not hosts:
                    continue
                bad_host, feed = None, None
                for h in hosts:
                    if _is_local(h):
                        continue
                    cands = _host_candidates(h)
                    if any(c in malware for c in cands):
                        bad_host, feed = h, "malware"
                        break
                    if include_phish:
                        for c in cands:
                            if await r.sismember("tintel:phish", c):
                                bad_host, feed = h, "phishing"
                                break
                        if bad_host:
                            break
                if not bad_host:
                    continue

                # extraer remitente + asunto + message-id de las cabeceras del texto
                sender = _first_header(text, "from")
                subject = _first_header(text, "subject")
                msgid = _first_header(text, "message-id")
                sender_addr = ""
                me = _EMAIL_RE.search(sender or "")
                if me:
                    sender_addr = me.group(0).lower()

                # respetar lista blanca: si el remitente "siempre llega", no tocar
                if sender_addr and sender_addr in whitelist:
                    continue

                summary["flagged"] += 1
                status = "simulado"
                if enforce:
                    moved = await doveadm.move_message(user, qfolder, guid, uid)
                    if moved:
                        status = "cuarentena"
                        summary["moved"] += 1
                    else:
                        status = "error"
                        summary["errors"] += 1
                await db.execute(
                    "INSERT INTO zap_actions (username, message_id, subject, sender, bad_host, feed, "
                    "mailbox_from, uid, guid, status) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) "
                    "ON CONFLICT (username, message_id, bad_host) DO UPDATE SET status=EXCLUDED.status, created_at=now()",
                    user, msgid, (subject or "")[:500], (sender or "")[:255],
                    bad_host, feed, "INBOX", str(uid), guid, status)
            except Exception:
                summary["errors"] += 1
                continue
    try:
        await r.aclose()
    except Exception:
        pass
    return summary


def _first_header(text: str, name: str) -> str:
    pat = re.compile(r"^" + re.escape(name) + r":\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    m = pat.search(text or "")
    return m.group(1).strip() if m else ""


async def release_action(db, action_id: int, do_whitelist: bool = False) -> dict:
    """Suelta un correo retirado por ZAP: lo devuelve de cuarentena a la bandeja.
    Lo localiza por Message-ID (su uid pudo cambiar al moverse). Fail-safe."""
    row = await db.fetchrow("SELECT * FROM zap_actions WHERE id = $1", action_id)
    if not row:
        return {"ok": False, "reason": "no existe"}
    if row["status"] == "liberado":
        return {"ok": True, "already": True}
    cfg = await db.fetchrow("SELECT quarantine_folder FROM zap_config WHERE id = 1")
    qfolder = (cfg["quarantine_folder"] if cfg else "Junk") or "Junk"
    user, msgid = row["username"], row["message_id"]
    if not msgid:
        return {"ok": False, "reason": "sin Message-ID; mover manualmente"}
    try:
        found = await doveadm.search_messages(user, f'mailbox {qfolder} HEADER Message-ID "{msgid}"')
    except Exception:
        found = []
    if not found:
        # quizá ya no está en cuarentena
        await db.execute("UPDATE zap_actions SET status='liberado' WHERE id=$1", action_id)
        return {"ok": True, "note": "no estaba en cuarentena"}
    ok = False
    for m in found:
        try:
            ok = await doveadm.move_message(user, "INBOX", m["mailbox_guid"], m["uid"]) or ok
        except Exception:
            pass
    whitelisted = None
    if ok and do_whitelist:
        whitelisted = await _whitelist_sender(row["sender"])
    if ok:
        await db.execute("UPDATE zap_actions SET status='liberado' WHERE id=$1", action_id)
    return {"ok": ok, "whitelisted": whitelisted}


async def _whitelist_sender(sender: str):
    """Agrega el remitente a la lista blanca de rspamd (que siempre llegue)."""
    import asyncio as _aio
    m = _EMAIL_RE.search(sender or "")
    if not m:
        return None
    addr = m.group(0).lower()
    try:
        existing = set()
        try:
            existing = {l.strip().lower() for l in open(WHITELIST_MAP) if l.strip() and not l.startswith("#")}
        except Exception:
            pass
        if addr not in existing:
            with open(WHITELIST_MAP, "a") as fh:
                fh.write(addr + "\n")
            await _aio.create_subprocess_exec("systemctl", "reload", "rspamd")
        return addr
    except Exception:
        return None
