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
    PurePythonMilter, Continue, AppendHeader, ReplaceBodyChunk, RejectWithCode,
)
from purepythonmilter.api.models import connection_id_context  # noqa: E402
from app.dlp import detectors  # noqa: E402
from app.safelinks import inbound_rewriter  # noqa: E402

LOCAL_DOMAINS = {"maquita.org", "maquita.com.ec"}
MAX_BODY = 12_000_000   # cuerpos mayores no se reescriben (se entregan intactos)

# Caché del interruptor del panel (evita consultar la BD en cada correo)
_toggle = {"val": False, "ts": 0.0}
_phish = {"mode": "off", "ext": False, "ts": 0.0}
_domains_cache = {"val": None, "ts": 0.0}


async def _local_domains(pool) -> set:
    """Dominios locales desde la tabla 'domain', cacheados 60s. Fallback al set fijo."""
    now = time.monotonic()
    if _domains_cache["val"] is not None and now - _domains_cache["ts"] < 60:
        return _domains_cache["val"]
    try:
        rows = await pool.fetch("SELECT domain FROM domain")
        vals = {(r["domain"] or "").lower() for r in rows if r["domain"]}
        if vals:
            _domains_cache["val"] = vals
    except Exception:
        pass
    if _domains_cache["val"] is None:
        _domains_cache["val"] = set(LOCAL_DOMAINS)
    _domains_cache["ts"] = now
    return _domains_cache["val"]


_attach = {"on": False, "ts": 0.0}


async def _attach_scan_enabled(pool) -> bool:
    now = time.monotonic()
    if now - _attach["ts"] < 20:
        return _attach["on"]
    try:
        row = await pool.fetchrow("SELECT milter_attach_scan FROM safeattach_config WHERE id = 1")
        _attach["on"] = bool(row and row["milter_attach_scan"])
    except Exception:
        _attach["on"] = False
    _attach["ts"] = now
    return _attach["on"]


async def _inbound_attachments(st, pool) -> list:
    """Detecta adjuntos Office con macros -> cabecera X-Macro-Attachment. Fail-open."""
    try:
        if not await _attach_scan_enabled(pool):
            return []
        if any(n.lower() == "x-macro-attachment" for n, _ in st["headers"]):
            return []   # ya analizado (reinyeccion del content_filter)
        from app.security import cdr
        raw = _reconstruct(st["headers"], bytes(st["body"]))
        msg = message_from_bytes(raw)
        found = []
        for part in msg.walk():
            fn = part.get_filename()
            if not fn:
                continue
            payload = part.get_payload(decode=True) or b""
            if not payload or len(payload) > 8_000_000:
                continue
            if cdr.is_ooxml(fn, payload) and cdr.has_macros(payload, fn):
                found.append(fn)
        if found:
            return [AppendHeader(headername="X-Macro-Attachment",
                                 headertext="adjuntos con macros: " + ", ".join(found[:5]))]
        return []
    except Exception:
        return []


def _load_env_keys() -> None:
    """Carga claves del .env del webmail al entorno (el servicio milter no usa
    EnvironmentFile). Necesario para que el clasificador alcance el gateway."""
    keys = ("OLLAMA_URL", "IA_API_KEY", "PHISH_CLASSIFIER_KIND",
            "PHISH_CLASSIFIER_MODEL", "PHISH_CLASSIFIER_TIMEOUT")
    try:
        for line in open("/opt/maquita-webmail/backend/.env"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k in keys and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass

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


async def _phishing_config(pool):
    """(mode, external) del panel, cacheado 20s. mode: off|header."""
    now = time.monotonic()
    if now - _phish["ts"] < 20:
        return _phish["mode"], _phish["ext"]
    try:
        row = await pool.fetchrow("SELECT phishing_milter_mode, phishing_milter_external FROM safelinks_config WHERE id = 1")
        _phish["mode"] = (row and row["phishing_milter_mode"]) or "off"
        _phish["ext"] = bool(row and row["phishing_milter_external"])
    except Exception:
        _phish["mode"], _phish["ext"] = "off", False
    _phish["ts"] = now
    return _phish["mode"], _phish["ext"]


async def _inbound_phishing(st, pool) -> list:
    """Clasifica el entrante y devuelve manipulaciones (cabeceras). Heuristica en
    todos; escala al modelo solo en banda incierta [30,70). Fail-open."""
    try:
        mode, ext = await _phishing_config(pool)
        if mode == "off":
            return []
        if any(n.lower() == "x-maquita-phishing" for n, _ in st["headers"]):
            return []   # ya clasificado (reinyeccion del content_filter) -> no duplicar
        from app.safelinks import classifier
        sender = next((t for n, t in st["headers"] if n.lower() == "from"), "")
        subject = next((t for n, t in st["headers"] if n.lower() == "subject"), "")
        text = _extract_text(st["headers"], bytes(st["body"]))[:20000]
        res = await asyncio.to_thread(classifier.score_message, sender=sender,
                                      subject=subject, body=text, use_external=False)
        if ext and 30 <= res["score"] < 70:
            res = await asyncio.to_thread(classifier.score_message, sender=sender,
                                          subject=subject, body=text, use_external=True)
        return [AppendHeader(headername="X-Maquita-Phishing",
                             headertext=f"{res['label']}; score={res['score']}; src={res['source']}")]
    except Exception:
        return []


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
    manips = await _inbound_safeattach(st, pool)   # Safe Attachments tambien en interno/saliente
    try:
        kws = [r["term"] for r in await pool.fetch("SELECT term FROM dlp_keywords")]
    except Exception:
        kws = []
    text = _extract_text(st["headers"], bytes(st["body"]))
    findings = detectors.detect_all(text, kws)
    if findings:
        types = sorted({f.data_type for f in findings})
        subj = next((t for n, t in st["headers"] if n.lower() == "subject"), "")
        # Bloquear SOLO tarjetas de credito (Luhn) que salen a destinatarios EXTERNOS
        has_card = any(f.data_type == "tarjeta" for f in findings)
        locals_ = await _local_domains(pool)
        has_external = any((r.split("@")[-1].lower() not in locals_) for r in st["rcpts"] if "@" in r)
        block = has_card and has_external
        try:
            await pool.execute(
                "INSERT INTO dlp_violations (username, recipients, subject, data_types, action, overridden) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                sender, json.dumps(st["rcpts"]), (subj or "")[:500], json.dumps(types),
                "milter_reject" if block else "milter_log", (not block))
        except Exception:
            pass
        if block:
            return RejectWithCode(
                primary_code=(5, 5, 4), enhanced_code=(5, 7, 1),
                text="Bloqueado por politica DLP: no se permite enviar numeros de tarjeta de credito a destinatarios externos.")
        manips.append(AppendHeader(headername="X-DLP-Alert",
                                   headertext="posibles datos sensibles: " + ", ".join(types)))
    return Continue(manipulations=manips) if manips else Continue()


_EXE_EXT = {".exe", ".scr", ".bat", ".cmd", ".com", ".pif", ".msi", ".js", ".jse",
            ".vbs", ".vbe", ".jar", ".ps1", ".lnk", ".hta", ".cpl", ".reg", ".wsf",
            ".msc", ".gadget", ".vb", ".ws", ".sct", ".inf"}


async def _inbound_safeattach(st, pool) -> list:
    """Safe Attachments INLINE: analiza cada adjunto (multi-motor estatico) y los ejecutables.
    Si es malicioso/sospechoso/ejecutable -> cabecera X-Maquita-Quarantine (sieve lo manda a Junk).
    Fail-open: si algo falla, el correo se entrega intacto."""
    import os as _os, asyncio as _aio, logging as _lg
    try:
        if not await _attach_scan_enabled(pool):
            return []
        if any(n.lower() == "x-maquita-quarantine" for n, _ in st["headers"]):
            return []
        raw = _reconstruct(st["headers"], bytes(st["body"]))
        msg = message_from_bytes(raw)
        mid = next((v for n, v in st["headers"] if n.lower() == "message-id"), "")
        flagged = []
        for part in msg.walk():
            fn = part.get_filename()
            if not fn:
                continue
            ext = _os.path.splitext(fn)[1].lower()
            ct = part.get_content_type() or ""
            reason = ""
            psize = 0
            if ext in _EXE_EXT:
                reason = "ejecutable (" + ext + ")"   # por extension: sin importar tamaño/truncamiento
            else:
                try:
                    payload = part.get_payload(decode=True) or b""
                except Exception:
                    continue
                psize = len(payload)
                if not payload or psize > 25_000_000:
                    continue
                try:
                    from app.safeattach import scan_attachment
                    rep = await _aio.wait_for(_aio.to_thread(scan_attachment, payload, fn, ct), timeout=15)
                    res = (rep or {}).get("result")
                    if res in ("malicious", "suspicious"):
                        thr = "; ".join(str(t.get("threat", "")) for t in (rep.get("threats") or [])[:2])
                        reason = res + ": " + thr
                except Exception:
                    reason = ""
            if reason:
                flagged.append((fn, reason))
                try:
                    await pool.execute(
                        "INSERT INTO attachment_scans (message_id, filename, content_type, size, "
                        "scan_result, threats_found, scanned_by, scanned_at) "
                        "VALUES ($1,$2,$3,$4,$5,$6::jsonb,'milter',now())",
                        mid, fn, ct, psize, "quarantined", json.dumps([reason[:300]]))
                except Exception:
                    pass
        if flagged:
            txt = "; ".join(fn + " [" + r + "]" for fn, r in flagged[:5])
            return [AppendHeader(headername="X-Maquita-Quarantine", headertext=txt[:400])]
        return []
    except Exception as _e:
        _lg.warning("Safe Attachments milter: %r", _e)
        return []


async def _inbound_impersonation(st, pool, locals_) -> list:
    """Anti-impersonation: correo de dominio AJENO cuyo NOMBRE visible suplanta a Maquita
    (marca o dominio propio en el display-name) -> cuarentena en Junk. Fail-open."""
    try:
        from email.utils import parseaddr
        from email.header import decode_header, make_header
        if any(n.lower() == "x-maquita-quarantine" for n, _ in st["headers"]):
            return []
        from_hdr = next((v for n, v in st["headers"] if n.lower() == "from"), "")
        if not from_hdr:
            return []
        name, addr = parseaddr(from_hdr)
        try:
            name = str(make_header(decode_header(name))) if name else ""
        except Exception:
            pass
        if not name:
            return []
        addr_dom = addr.split("@")[-1].lower() if "@" in addr else ""
        if addr_dom and addr_dom in locals_:
            return []   # dominio propio -> ya lo cubre MAQ_OWN_DOMAIN_SPOOF
        terms = set(["maquita", "mcch", "cushunchic"])
        for d in locals_:
            terms.add(str(d).lower())
        name_l = name.lower()
        hit = next((t for t in terms if t and t in name_l), None)
        if hit:
            return [AppendHeader(headername="X-Maquita-Quarantine",
                                 headertext=("impersonation: nombre '" + name[:50] +
                                             "' (dominio real " + (addr_dom or "?") + ")")[:300])]
        return []
    except Exception:
        return []


async def _inbound_safelinks(st, pool, locals_) -> Continue:
    if st.get("trunc"):
        return Continue()   # cuerpo truncado -> entregar intacto (fail-safe)
    if not any((r.split("@")[-1] in locals_) for r in st["rcpts"] if "@" in r):
        return Continue()   # sin destinatario local
    manips = []
    if await _inbound_enabled(pool):
        raw = _reconstruct(st["headers"], bytes(st["body"]))
        new_body = inbound_rewriter.rewrite_inbound(raw)
        if new_body:
            manips.append(ReplaceBodyChunk(chunk=new_body))   # Safe Links
    manips.extend(await _inbound_phishing(st, pool))          # Anti-phishing (default off)
    manips.extend(await _inbound_attachments(st, pool))      # Macros en adjuntos (default off)
    manips.extend(await _inbound_safeattach(st, pool))     # Safe Attachments inline + ejecutables -> cuarentena
    manips.extend(await _inbound_impersonation(st, pool, locals_))  # anti-impersonation (display-name)
    return Continue(manipulations=manips) if manips else Continue()


async def on_end_of_message(cmd) -> Continue:
    st = _state.pop(_cid(), None)
    if not st:
        return Continue()
    try:
        pool = await _get_pool()
        locals_ = await _local_domains(pool)
        sender = st["from"]
        dom = sender.split("@")[-1] if "@" in sender else ""
        if dom in locals_:
            return await _outbound_dlp(st, sender)        # SALIENTE: DLP
        return await _inbound_safelinks(st, pool, locals_)  # ENTRANTE
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
    _load_env_keys()
    milter.run_server(host="127.0.0.1", port=11335)
