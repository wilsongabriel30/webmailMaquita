#!/opt/maquita-webmail/backend/venv/bin/python
"""Milter de Maquita — Fase 1 (DLP saliente) + Fase 2 (Safe Links entrante).

SALIENTE (remitente local): inspecciona y, si detecta datos sensibles, agrega la
cabecera X-DLP-Alert y lo registra. NO modifica el cuerpo. Solo visibilidad.

ENTRANTE (remitente externo, destinatario local): si el interruptor del panel
(safelinks_config.milter_inbound_enabled) está ENCENDIDO, reescribe los enlaces
<a href> a la pasarela de Safe Links para que TODOS los clientes (Outlook, móvil,
etc.) tengan protección al hacer clic. El reescritor valida el resultado parte
por parte; si algo no cuadra, deja el correo INTACTO.

Diseño FAIL-OPEN en todo: ante cualquier error -> el correo se entrega intacto.
NUNCA rechaza, NUNCA retiene, NUNCA corrompe.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import time
from email import message_from_bytes

sys.path.insert(0, "/opt/maquita-webmail/backend")

import asyncpg  # noqa: E402
from purepythonmilter import (  # noqa: E402
    PurePythonMilter, Continue, AppendHeader, ReplaceBodyChunk,
)
from purepythonmilter.api.models import connection_id_context  # noqa: E402
from app.dlp import detectors  # noqa: E402
from app.safelinks import inbound_rewriter  # noqa: E402

LOCAL_DOMAINS = {"maquita.org", "maquita.com.ec"}
MAX_BODY = 12_000_000   # cuerpos mayores no se reescriben (se entregan intactos)

# Caché del interruptor del panel (evita consultar la BD en cada correo)
_toggle = {"val": False, "ts": 0.0}

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
        s = {"from": "", "rcpts": [], "headers": [], "body": bytearray(), "trunc": False}
        _state[k] = s
    return s


async def _inbound_enabled(pool) -> bool:
    """Lee el interruptor del panel, cacheado 20s."""
    now = time.monotonic()
    if now - _toggle["ts"] < 20:
        return _toggle["val"]
    try:
        row = await pool.fetchrow("SELECT milter_inbound_enabled FROM safelinks_config WHERE id = 1")
        _toggle["val"] = bool(row and row["milter_inbound_enabled"])
    except Exception:
        _toggle["val"] = False
    _toggle["ts"] = now
    return _toggle["val"]


def _reconstruct(headers, body: bytes) -> bytes:
    return b"\r\n".join(f"{n}: {t}".encode("utf-8", "replace") for n, t in headers) + b"\r\n\r\n" + body


async def on_mail_from(cmd) -> Continue:
    _state[_cid()] = {"from": (cmd.address or "").lower(), "rcpts": [], "headers": [], "body": bytearray(), "trunc": False}
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
        if len(st["body"]) >= MAX_BODY:
            st["trunc"] = True   # cuerpo grande: no reescribir (entregar intacto)
    else:
        st["trunc"] = True
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


async def _outbound_dlp(st, sender) -> Continue:
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


async def _inbound_safelinks(st) -> Continue:
    if st.get("trunc"):
        return Continue()   # cuerpo truncado -> entregar intacto (fail-safe)
    if not any((r.split("@")[-1] in LOCAL_DOMAINS) for r in st["rcpts"] if "@" in r):
        return Continue()   # sin destinatario local
    pool = await _get_pool()
    if not await _inbound_enabled(pool):
        return Continue()   # interruptor del panel APAGADO
    raw = _reconstruct(st["headers"], bytes(st["body"]))
    new_body = inbound_rewriter.rewrite_inbound(raw)
    if not new_body:
        return Continue()   # sin enlaces, sin cambios, o no fue seguro -> intacto
    return Continue(manipulations=[ReplaceBodyChunk(chunk=new_body)])


async def on_end_of_message(cmd) -> Continue:
    st = _state.pop(_cid(), None)
    if not st:
        return Continue()
    try:
        sender = st["from"]
        dom = sender.split("@")[-1] if "@" in sender else ""
        if dom in LOCAL_DOMAINS:
            return await _outbound_dlp(st, sender)        # SALIENTE: DLP
        return await _inbound_safelinks(st)               # ENTRANTE: Safe Links
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
    can_change_body=True,
)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    milter.run_server(host="127.0.0.1", port=11335)
