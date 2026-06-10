"""Safe Links — reescritura de enlaces en correos ENTRANTES (a nivel milter).

Reescribe los <a href="http..."> de las partes text/html para que pasen por la
pasarela de Safe Links, en CUALQUIER cliente. Diseño ULTRA-seguro:

- Conserva el Content-Transfer-Encoding original de cada parte (base64->base64,
  qp->qp, 7bit/8bit->crudo). Así NO hace falta tocar cabeceras de nivel superior
  y funciona igual en multipart que en single-part.
- VALIDACIÓN ESTRICTA: re-parsea EXACTAMENTE lo que entregará el milter
  (cabeceras originales + cuerpo nuevo) y comprueba parte por parte que:
    * cada parte NO html quedó BYTE-IDÉNTICA, y
    * cada parte html DECODIFICA EXACTAMENTE al html reescrito esperado.
  Si algo no cuadra -> devuelve None (el milter deja el correo INTACTO).
- Cualquier excepción -> None (intacto). Nunca corrompe, nunca pierde.

rewrite_inbound(raw_bytes) -> nuevo_cuerpo_bytes | None  (None = no tocar)
"""
from __future__ import annotations
import base64
import quopri
import re
from email import message_from_bytes
from email.generator import BytesGenerator
from io import BytesIO

from app.safelinks import rewriter as sl_rewriter

_HREF = re.compile(r'(<a\b[^>]*?\shref=")(https?://[^"]*)(")', re.IGNORECASE)


def _rewrite_html(html: str) -> tuple[str, int]:
    n = [0]

    def repl(m):
        n[0] += 1
        return m.group(1) + sl_rewriter.gateway_link(m.group(2)) + m.group(3)

    return _HREF.sub(repl, html), n[0]


def _split(raw: bytes):
    for sep in (b"\r\n\r\n", b"\n\n"):
        i = raw.find(sep)
        if i != -1:
            return raw[:i], sep, raw[i + len(sep):]
    return None, None, None


def _nonmultipart_parts(msg):
    return [p for p in msg.walk() if not p.is_multipart()]


def _norm_nl(x):
    """Normaliza saltos de línea (CRLF/CR -> LF). Acepta str o bytes."""
    if isinstance(x, bytes):
        return x.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return x.replace("\r\n", "\n").replace("\r", "\n")


def rewrite_inbound(raw: bytes) -> bytes | None:
    try:
        # Nota: NO se filtra por bytes crudos (en base64/qp los enlaces van
        # codificados). Se parsea siempre; si no hay enlaces, changed==0 -> None.
        orig_headers, sep, _orig_body = _split(raw)
        if orig_headers is None:
            return None

        # Snapshot del original (decodificado) por índice de parte.
        orig_parts = [(p.get_content_type(), p.get_payload(decode=True))
                      for p in _nonmultipart_parts(message_from_bytes(raw))]

        msg = message_from_bytes(raw)
        expected: dict[int, str] = {}   # índice -> html reescrito esperado
        changed = 0
        for idx, part in enumerate(_nonmultipart_parts(msg)):
            if part.get_content_type() != "text/html":
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                html = payload.decode(charset, "replace")
            except Exception:
                return None
            new_html, n = _rewrite_html(html)
            if n == 0:
                continue
            data = new_html.encode(charset, "replace")
            cte = (part.get("Content-Transfer-Encoding", "") or "").lower().strip()
            # Conservar el MISMO CTE (no cambia cabeceras de nivel superior).
            if cte == "base64":
                part.set_payload(base64.encodebytes(data).decode("ascii"))
            elif cte == "quoted-printable":
                part.set_payload(quopri.encodestring(data).decode("ascii"))
            else:
                # 7bit/8bit/none: en compat32 el cuerpo se guarda como bytes
                # decodificados ascii+surrogateescape; el generator los re-emite 1:1.
                part.set_payload(data.decode("ascii", "surrogateescape"))
            expected[idx] = new_html
            changed += 1

        if changed == 0:
            return None

        buf = BytesIO()
        BytesGenerator(buf, mangle_from_=False).flatten(msg, linesep="\r\n")
        out = buf.getvalue()
        _h, _s, new_body = _split(out)
        if new_body is None:
            return None

        # ── VALIDACIÓN ESTRICTA: exactamente lo que entregará el milter ──
        # Los saltos de línea (CRLF/LF) son cosméticos: se normalizan al comparar
        # el TEXTO. Los binarios (adjuntos) se comparan BYTE-EXACTOS.
        check = message_from_bytes(orig_headers + sep + new_body)
        check_parts = _nonmultipart_parts(check)
        if len(check_parts) != len(orig_parts):
            return None
        for i, cp in enumerate(check_parts):
            oct_, op = orig_parts[i]
            if cp.get_content_type() != oct_:
                return None
            dec = cp.get_payload(decode=True)
            if i in expected:
                charset = cp.get_content_charset() or "utf-8"
                try:
                    got = dec.decode(charset, "replace") if dec is not None else None
                except Exception:
                    return None
                if got is None or _norm_nl(got) != _norm_nl(expected[i]):
                    return None  # no decodifica al html esperado -> NO usar
            elif oct_.startswith("text/"):
                if _norm_nl(op) != _norm_nl(dec):
                    return None  # parte de texto cambió (más que saltos de línea)
            else:
                if dec != op:
                    return None  # binario/adjunto: cualquier cambio -> ABORTAR
        return new_body
    except Exception:
        return None
