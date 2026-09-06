"""
Milter — DLP saliente Nivel 3 (2026-08-28).

Aplica la MISMA política que el webmail (app.dlp.service / policy / attachments)
a los correos que salen por SMTP directo (Outlook, móvil, otros clientes).

Controlado desde el panel admin (tabla dlp_config):
  enabled          -> interruptor general (apagado = no se revisa nada)
  rules/default    -> acción por tipo de dato (warn/block/audit)
  milter_enforce   -> True: un 'block' a externos se RECHAZA en el servidor (5.7.1)
                      False: solo cabecera X-DLP-Alert + registro (modo observación)
  scan_attachments -> revisar también el contenido de los adjuntos
  trusted_domains  -> dominios externos de confianza (no cuentan como externos)

Fail-open: ante cualquier error, el correo se entrega intacto.
"""
from __future__ import annotations
import json
from email import message_from_bytes

from purepythonmilter import Continue, AppendHeader, RejectWithCode

from app.dlp import service as dlp_service
from app.dlp import policy as dlp_policy
from app.dlp import attachments as dlp_att

_SEV = {"allow": 0, "audit": 1, "warn": 2, "block": 3}


def _attachments_from_mime(headers, body: bytes) -> list[dict]:
    out = []
    try:
        raw = b"\r\n".join(f"{n}: {t}".encode("utf-8", "replace") for n, t in headers) + b"\r\n\r\n" + body
        msg = message_from_bytes(raw)
        for p in msg.walk():
            fn = p.get_filename()
            if not fn or p.is_multipart():
                continue
            out.append({"filename": fn, "content": p.get_payload(decode=True) or b"",
                        "content_type": p.get_content_type()})
    except Exception:
        pass
    return out


EXEMPT_SENDERS_FILE = "/etc/maquita-mail/dlp-exempt-senders.txt"


def _exempt_senders() -> set:
    """Remitentes de SISTEMA exentos del DLP (uno por linea). Caso de uso: noreply@ de
    Raices Nomina, que envia a cada trabajador SU rol de pagos (con cedula) a su correo
    personal. Se lee en cada mensaje para poder cambiarlo sin reiniciar."""
    out = set()
    try:
        with open(EXEMPT_SENDERS_FILE) as fh:
            for ln in fh:
                ln = ln.strip().lower()
                if ln and not ln.startswith("#"):
                    out.add(ln)
    except Exception:
        pass
    return out


async def run(st: dict, sender: str, pool, text: str, manips: list,
              legacy_block_cards: bool = False) -> Continue:
    cfg = await dlp_service.get_config(pool)
    if not cfg.get("enabled"):
        return Continue(manipulations=manips) if manips else Continue()
    if (sender or "").lower().strip("<>") in _exempt_senders():
        manips.append(AppendHeader(headername="X-DLP-Exempt", headertext="remitente de sistema autorizado"))
        return Continue(manipulations=manips)

    scan = await dlp_service.scan(pool, "", text, "")
    findings = list(scan.get("findings", []))

    if cfg.get("scan_attachments", True):
        atts = _attachments_from_mime(st["headers"], bytes(st["body"]))
        if atts and not st.get("trunc"):
            att_text, unins = dlp_att.extract_all(atts)
            if att_text:
                s2 = await dlp_service.scan(pool, "", att_text, "")
                for f in s2.get("findings", []):
                    f["label"] = f["label"] + " (en adjunto)"
                    findings.append(f)
            if unins:
                findings.append({"type": "adjunto", "label": "Adjunto no inspeccionable",
                                 "sample": "", "count": len(unins), "action": "warn"})

    if not findings:
        return Continue(manipulations=manips) if manips else Continue()

    worst = max((f["action"] for f in findings), key=lambda a: _SEV.get(a, 0))
    dec = await dlp_policy.decide(pool, {"findings": findings, "action": worst},
                                  st["rcpts"], await dlp_policy.is_admin(pool, sender),
                                  sender=sender)
    ext = bool(dec.get("external"))
    types = sorted({f["type"] for f in findings})
    has_card = "tarjeta" in types

    block = (dec["action"] == "block" and bool(cfg.get("milter_enforce"))) \
        or (legacy_block_cards and has_card and ext)
    subj = next((t for n, t in st["headers"] if n.lower() == "subject"), "")
    try:
        await pool.execute(
            "INSERT INTO dlp_violations (username, recipients, subject, data_types, action, overridden, external) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            sender, json.dumps(st["rcpts"]), (subj or "")[:500], json.dumps(types),
            "milter_reject" if block else f"milter_{dec['action']}", (not block), ext)
        if dec.get("exento"):
            # Queda constancia de que salio por excepcion, no por no detectarse.
            await pool.execute(
                "UPDATE dlp_violations SET reason = $1 WHERE id = "
                "(SELECT max(id) FROM dlp_violations)",
                "Remitente exento: se permitio el envio y se registro para revision")
    except Exception:
        pass

    if block:
        return RejectWithCode(
            primary_code=(5, 5, 4), enhanced_code=(5, 7, 1),
            text="Bloqueado por Proteccion de datos de Maquita: el mensaje contiene datos sensibles ("
                 + ", ".join(types) + ") dirigidos a destinatarios externos. Quite esos datos o use el webmail para solicitar autorizacion.")
    manips.append(AppendHeader(headername="X-DLP-Alert",
                               headertext="posibles datos sensibles: " + ", ".join(types)
                               + (" (externo)" if ext else "")))
    return Continue(manipulations=manips)
