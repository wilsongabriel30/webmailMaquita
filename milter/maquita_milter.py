#!/opt/maquita-webmail/backend/venv/bin/python
"""Milter de Maquita — Fase 1: DLP en correo SALIENTE (todos los clientes).

INSPECCIONA el correo saliente (Outlook, móvil, Thunderbird, etc.), y si detecta
datos sensibles agrega una cabecera X-DLP-Alert y lo registra en dlp_violations.
NO modifica el cuerpo, NO rechaza, NO retiene: es SOLO visibilidad/auditoría.
Diseño FAIL-OPEN: ante cualquier error, deja pasar el correo intacto.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
from email import message_from_bytes

sys.path.insert(0, "/opt/maquita-webmail/backend")

import asyncpg  # noqa: E402
from purepythonmilter import (  # noqa: E402
    PurePythonMilter, Continue, AppendHeader,
)
from purepythonmilter.api.models import connection_id_context  # noqa: E402
from app.dlp import detectors  # noqa: E402

LOCAL_DOMAINS = {"maquita.org", "maquita.com.ec"}
MAX_BODY = 2_000_000

_state: dict = {}
_pool = None
_pool_lock = asyncio.Lock()


def _dsn() -> str:
    try:
        for line in open("/opt/maquita-webmail/backend/.env"):
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.getenv("DATABASE_URL", "")


async def _get_pool():
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=4)
    return _pool


def _cid():
    try:
        return connection_id_context.get()
    except Exception:
        return "default"


def _st():
    k = _cid()
    s = _state.get(k)
    if s is None:
        s = {"from": "", "rcpts": [], "headers": [], "body": bytearray()}
        _state[k] = s
    return s


async def on_mail_from(cmd) -> Continue:
    _state[_cid()] = {"from": (cmd.address or "").lower(), "rcpts": [], "headers": [], "body": bytearray()}
    return Continue()


async def on_rcpt(cmd) -> Continue:
    _st()["rcpts"].append((cmd.address or "").lower())
    return Continue()


async def on_header(cmd) -> Continue:
    st = _st()
    if len(st["headers"]) < 250:
        st["headers"].append((cmd.name, cmd.text))
    return Continue()


async def on_body_chunk(cmd) -> Continue:
    st = _st()
    if len(st["body"]) < MAX_BODY:
        st["body"].extend(cmd.data_raw or b"")
    return Continue()


def _extract_text(headers, body: bytes) -> str:
    subj = next((t for n, t in headers if n.lower() == "subject"), "")
    parts = [subj]
    try:
        raw = b"\r\n".join(f"{n}: {t}".encode("utf-8", "replace") for n, t in headers) + b"\r\n\r\n" + body
        msg = message_from_bytes(raw)
        for p in msg.walk():
            ct = p.get_content_type()
            if ct in ("text/plain", "text/html"):
                try:
                    payload = p.get_payload(decode=True) or b""
                    s = payload.decode(p.get_content_charset() or "utf-8", "replace")
                    if ct == "text/html":
                        s = re.sub(r"<[^>]+>", " ", s)
                    parts.append(s)
                except Exception:
                    pass
    except Exception:
        try:
            parts.append(body.decode("utf-8", "replace"))
        except Exception:
            pass
    return " ".join(parts)


async def on_end_of_message(cmd) -> Continue:
    st = _state.pop(_cid(), None)
    if not st:
        return Continue()
    try:
        sender = st["from"]
        dom = sender.split("@")[-1] if "@" in sender else ""
        if dom not in LOCAL_DOMAINS:   # solo SALIENTE (remitente local)
            return Continue()
        pool = await _get_pool()
        try:
            kws = [r["term"] for r in await pool.fetch("SELECT term FROM dlp_keywords")]
        except Exception:
            kws = []
        text = _extract_text(st["headers"], bytes(st["body"]))
        findings = detectors.detect_all(text, kws)
        if not findings:
            return Continue()
        types = sorted({f.data_type for f in findings})
        subj = next((t for n, t in st["headers"] if n.lower() == "subject"), "")
        try:
            await pool.execute(
                "INSERT INTO dlp_violations (username, recipients, subject, data_types, action, overridden) "
                "VALUES ($1,$2,$3,$4,'milter_log',true)",
                sender, json.dumps(st["rcpts"]), (subj or "")[:500], json.dumps(types))
        except Exception:
            pass
        return Continue(manipulations=[AppendHeader(headername="X-DLP-Alert",
                                                    headertext="posibles datos sensibles: " + ", ".join(types))])
    except Exception:
        return Continue()   # FAIL-OPEN: nunca afecta la entrega


async def on_abort(cmd) -> Continue:
    _state.pop(_cid(), None)
    return Continue()


milter = PurePythonMilter(
    name="maquita_dlp",
    hook_on_mail_from=on_mail_from,
    hook_on_rcpt_to=on_rcpt,
    hook_on_header=on_header,
    hook_on_body_chunk=on_body_chunk,
    hook_on_end_of_message=on_end_of_message,
    hook_on_abort=on_abort,
    can_add_headers=True,
)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    milter.run_server(host="127.0.0.1", port=11335)
