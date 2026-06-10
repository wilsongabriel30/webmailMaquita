"""Safe Attachments — extracción de adjuntos de un correo RFC822 y análisis del email."""
from __future__ import annotations
from email import message_from_bytes
from email.message import Message

from app.safeattach.analyzers import analyze

SKIP_CT = ("text/plain", "text/html", "multipart/alternative", "multipart/mixed",
           "multipart/related", "multipart/report", "message/rfc822")


def extract_attachments(raw: bytes) -> list[tuple[str, bytes]]:
    """Devuelve [(filename, data)] de los adjuntos reales del correo."""
    out = []
    try:
        msg: Message = message_from_bytes(raw)
    except Exception:
        return out
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = (part.get_content_disposition() or "").lower()
        fname = part.get_filename()
        ctype = (part.get_content_type() or "").lower()
        # adjunto = tiene disposition attachment, o nombre de archivo, y no es cuerpo
        if disp == "attachment" or fname:
            if not fname and ctype in SKIP_CT:
                continue
            try:
                data = part.get_payload(decode=True)
            except Exception:
                data = None
            if data:
                out.append((fname or "sin_nombre", data))
    return out


def scan_email(raw: bytes, redis_client=None) -> dict:
    """Analiza todos los adjuntos de un correo. Veredicto = peor de los adjuntos."""
    results = [analyze(name, data, redis_client=redis_client) for name, data in extract_attachments(raw)]
    sev = {"clean": 0, "suspicious": 1, "malicious": 2}
    verdict = "clean"
    for r in results:
        if sev[r["verdict"]] > sev[verdict]:
            verdict = r["verdict"]
    return {"verdict": verdict, "attachments": results, "count": len(results)}
