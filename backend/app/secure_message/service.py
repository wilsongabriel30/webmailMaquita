"""Servicio de mensajes seguros (OME): crear, enviar notificación + OTP,
verificar y descifrar. La identidad del externo se prueba con un código de un
solo uso enviado a su propio correo.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import html as html_lib
import json
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings
from . import crypto


def gen_token() -> str:
    return secrets.token_urlsafe(24)


def gen_otp() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _hash_code(token: str, email: str, code: str) -> str:
    return hashlib.sha256(f"{token}|{email.lower()}|{code}".encode()).hexdigest()


def portal_url(token: str) -> str:
    dom = (get_settings().cookie_domain or "mail.maquita.org").lstrip(".")
    return f"https://{dom}/secure/{token}"


async def get_config(db) -> dict:
    row = await db.fetchrow(
        "SELECT enabled, expire_days, max_views, intro_text FROM secure_config WHERE id = 1")
    if not row:
        return {"enabled": True, "expire_days": 7, "max_views": 0, "intro_text": ""}
    return dict(row)


def _parse_list(v):
    if isinstance(v, str):
        try:
            return json.loads(v or "[]")
        except ValueError:
            return []
    return v or []


# ── Envío de correos del sistema (notificación + OTP) ───────────────────────
async def _send_system_mail(to_addr: str, subject: str, html_body: str,
                            from_addr: str | None = None) -> bool:
    s = get_settings()
    sender = from_addr or f"no-reply@{s.mail_domain}"
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content("Tu cliente de correo no soporta HTML.")
    msg.add_alternative(html_body, subtype="html")
    try:
        # Relay local de Postfix (sin auth desde localhost)
        await aiosmtplib.send(msg, hostname="127.0.0.1", port=25, timeout=20, start_tls=False)
        return True
    except Exception:
        return False


def _notif_html(sender_name: str, sender: str, subject: str, url: str,
                expires_at, intro: str) -> str:
    exp = ""
    if expires_at:
        exp = f"<p style='color:#888;font-size:13px'>Este mensaje caduca el {expires_at.strftime('%d/%m/%Y')}.</p>"
    intro_html = f"<p>{html_lib.escape(intro)}</p>" if intro else ""
    safe_subj = html_lib.escape(subject or "(sin asunto)")
    safe_from = html_lib.escape(sender_name or sender)
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto">
  <div style="background:#0078d4;color:#fff;padding:18px 24px;border-radius:8px 8px 0 0">
    <div style="font-size:18px;font-weight:600">🔒 Mensaje seguro</div>
  </div>
  <div style="border:1px solid #e1dfdd;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <p><b>{safe_from}</b> te envió un mensaje seguro de Maquita.</p>
    <p style="color:#555"><b>Asunto:</b> {safe_subj}</p>
    {intro_html}
    <p style="text-align:center;margin:26px 0">
      <a href="{url}" style="background:#0078d4;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:600;display:inline-block">Abrir mensaje seguro</a>
    </p>
    <p style="color:#888;font-size:13px">Al abrirlo te pediremos un código que enviaremos a tu correo para confirmar tu identidad. No necesitas crear ninguna cuenta.</p>
    {exp}
    <p style="color:#aaa;font-size:12px">Si no esperabas este mensaje, puedes ignorarlo.</p>
  </div>
</div>"""


def _otp_html(code: str, subject: str) -> str:
    safe_subj = html_lib.escape(subject or "")
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:460px;margin:0 auto;text-align:center">
  <p>Tu código para abrir el mensaje seguro{(' «' + safe_subj + '»') if safe_subj else ''}:</p>
  <div style="font-size:34px;letter-spacing:8px;font-weight:700;color:#0078d4;margin:18px 0">{code}</div>
  <p style="color:#888;font-size:13px">El código vence en 10 minutos. No lo compartas con nadie.</p>
</div>"""


# ── Crear y enviar ──────────────────────────────────────────────────────────
async def create_and_notify(db, sender: str, sender_name: str, subject: str,
                            recipients: list[str], html_body: str,
                            files: list[dict]) -> dict:
    cfg = await get_config(db)
    token = gen_token()
    body_ct, nonce = crypto.encrypt((html_body or "").encode("utf-8"))
    expires_at = None
    if cfg["expire_days"] and cfg["expire_days"] > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=cfg["expire_days"])
    recips = sorted({(r or "").strip().lower() for r in recipients if (r or "").strip()})

    await db.execute(
        "INSERT INTO secure_messages (token, sender, sender_name, subject, recipients, "
        "body_ct, nonce, expires_at, max_views) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        token, sender, sender_name or "", subject or "", json.dumps(recips),
        body_ct, nonce, expires_at, int(cfg["max_views"] or 0))

    for f in (files or []):
        content = f.get("content") or b""
        fct, fn = crypto.encrypt(content)
        await db.execute(
            "INSERT INTO secure_message_files (token, filename, content_type, body_ct, nonce) "
            "VALUES ($1,$2,$3,$4,$5)",
            token, f.get("filename", "archivo"), f.get("content_type", "application/octet-stream"),
            fct, fn)

    url = portal_url(token)
    notif = _notif_html(sender_name, sender, subject, url, expires_at, cfg.get("intro_text") or "")
    sent_ok = []
    for r in recips:
        ok = await _send_system_mail(r, f"🔒 Mensaje seguro: {subject or '(sin asunto)'}",
                                     notif, from_addr=sender)
        if ok:
            sent_ok.append(r)
    return {"token": token, "url": url, "recipients": recips,
            "notified": sent_ok, "expires_at": expires_at.isoformat() if expires_at else None}


# ── Estado del mensaje ──────────────────────────────────────────────────────
async def _load(db, token: str):
    return await db.fetchrow(
        "SELECT token, sender, sender_name, subject, recipients, revoked, expires_at, "
        "max_views, view_count FROM secure_messages WHERE token = $1", token)


def _status(msg) -> str | None:
    if msg is None:
        return "not_found"
    if msg["revoked"]:
        return "revoked"
    if msg["expires_at"] and msg["expires_at"] < datetime.now(timezone.utc):
        return "expired"
    if msg["max_views"] and msg["view_count"] >= msg["max_views"]:
        return "exhausted"
    return None  # ok


async def meta(db, token: str) -> dict:
    msg = await _load(db, token)
    st = _status(msg)
    if st == "not_found":
        return {"ok": False, "status": "not_found"}
    return {
        "ok": st is None, "status": st or "ok",
        "subject": msg["subject"], "sender_name": msg["sender_name"] or msg["sender"],
    }


# ── OTP ─────────────────────────────────────────────────────────────────────
async def send_otp(db, token: str, email: str, ip: str = "") -> dict:
    msg = await _load(db, token)
    st = _status(msg)
    if st:
        return {"ok": False, "status": st}
    email = (email or "").strip().lower()
    if email not in _parse_list(msg["recipients"]):
        await db.execute("INSERT INTO secure_message_access (token,email,action,ip) VALUES ($1,$2,'denied',$3)", token, email, ip)
        return {"ok": False, "status": "not_recipient"}
    code = gen_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db.execute("DELETE FROM secure_message_otps WHERE token=$1 AND email=$2", token, email)
    await db.execute(
        "INSERT INTO secure_message_otps (token,email,code_hash,expires_at) VALUES ($1,$2,$3,$4)",
        token, email, _hash_code(token, email, code), expires)
    await _send_system_mail(email, "Tu código de acceso", _otp_html(code, msg["subject"]))
    await db.execute("INSERT INTO secure_message_access (token,email,action,ip) VALUES ($1,$2,'otp_sent',$3)", token, email, ip)
    return {"ok": True}


async def verify_and_read(db, token: str, email: str, code: str, ip: str = "") -> dict:
    msg = await _load(db, token)
    st = _status(msg)
    if st:
        return {"ok": False, "status": st}
    email = (email or "").strip().lower()
    row = await db.fetchrow(
        "SELECT id, code_hash, expires_at, attempts FROM secure_message_otps "
        "WHERE token=$1 AND email=$2 ORDER BY id DESC LIMIT 1", token, email)
    if not row or row["expires_at"] < datetime.now(timezone.utc):
        return {"ok": False, "status": "code_expired"}
    if row["attempts"] >= 5:
        return {"ok": False, "status": "too_many"}
    if not hmac.compare_digest(row["code_hash"], _hash_code(token, email, (code or "").strip())):
        await db.execute("UPDATE secure_message_otps SET attempts=attempts+1 WHERE id=$1", row["id"])
        return {"ok": False, "status": "bad_code"}

    # OK -> descifrar
    full = await db.fetchrow("SELECT body_ct, nonce, subject, sender_name, sender FROM secure_messages WHERE token=$1", token)
    body = crypto.decrypt(full["body_ct"], full["nonce"]).decode("utf-8", "replace")
    files = []
    for fr in await db.fetch("SELECT id, filename, content_type, body_ct, nonce FROM secure_message_files WHERE token=$1 ORDER BY id", token):
        content = crypto.decrypt(fr["body_ct"], fr["nonce"])
        files.append({"filename": fr["filename"], "content_type": fr["content_type"],
                      "content_b64": base64.b64encode(content).decode()})
    await db.execute("UPDATE secure_messages SET view_count=view_count+1 WHERE token=$1", token)
    await db.execute("DELETE FROM secure_message_otps WHERE token=$1 AND email=$2", token, email)
    await db.execute("INSERT INTO secure_message_access (token,email,action,ip) VALUES ($1,$2,'opened',$3)", token, email, ip)
    return {"ok": True, "subject": full["subject"],
            "sender_name": full["sender_name"] or full["sender"],
            "html": body, "files": files}
