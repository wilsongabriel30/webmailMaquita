"""Safe Links — firma y reescritura de enlaces en el HTML del correo.

Solo se reescriben enlaces http/https. La firma HMAC evita que la pasarela se
use como redirector abierto: enlaces sin firma válida SIEMPRE muestran aviso.
"""

import base64
import hashlib
import hmac
import html as html_lib
import re

from app.config import get_settings


def _secret() -> bytes:
    return (get_settings().secret_key or "maquita-fallback").encode()


def encode_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode().rstrip("=")


def decode_url(u_b64: str) -> str:
    pad = "=" * (-len(u_b64) % 4)
    return base64.urlsafe_b64decode((u_b64 + pad).encode()).decode("utf-8", "replace")


def sign(u_b64: str) -> str:
    return hmac.new(_secret(), u_b64.encode(), hashlib.sha256).hexdigest()[:32]


def verify(u_b64: str, sig: str) -> bool:
    return hmac.compare_digest(sign(u_b64), sig or "")


def gateway_link(url: str) -> str:
    # El href viene del HTML del correo, donde "&" se escribe "&amp;". Hay que
    # deshacer las entidades ANTES de codificar: si no, el destino recibe
    # "&amp;token=..." y lee un parametro "amp;token" en vez de "token"
    # (rompia activaciones y restablecimientos de clave con varios parametros).
    ub = encode_url(html_lib.unescape(url))
    base = (get_settings().public_base_url or "https://mail.maquita.org").rstrip("/")
    return f"{base}/api/safelink?u={ub}&s={sign(ub)}"


_HREF = re.compile(r'(<a\b[^>]*?\shref=")(https?://[^"]*)(")', re.IGNORECASE)


def rewrite(html: str) -> str:
    if not html or "<a" not in html.lower():
        return html
    return _HREF.sub(lambda m: m.group(1) + gateway_link(m.group(2)) + m.group(3), html)
