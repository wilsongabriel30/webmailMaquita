"""Safe Links — firma y reescritura de enlaces en el HTML del correo.

Solo se reescriben enlaces http/https. La firma HMAC evita que la pasarela se
use como redirector abierto: enlaces sin firma válida SIEMPRE muestran aviso.
"""

import base64
import hashlib
import hmac
import html as html_lib
import re

from app import organizacion
from app.config import get_settings

from . import propios


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


def gateway_link(url: str, base: str | None = None) -> str:
    # El href viene del HTML del correo, donde "&" se escribe "&amp;". Hay que
    # deshacer las entidades ANTES de codificar: si no, el destino recibe
    # "&amp;token=..." y lee un parametro "amp;token" en vez de "token"
    # (rompia activaciones y restablecimientos de clave con varios parametros).
    # Ya es un enlace de la pasarela (correo citado o reenviado): no se envuelve otra vez
    # (05/11/2026; la doble envoltura hacía saltar el aviso contra nuestro propio dominio).
    limpio = html_lib.unescape(url)
    if propios.es_pasarela(limpio):
        # Envoltura antigua de un enlace de la casa (Drive, sistema de gestión…): se muestra directa.
        destino = propios.desenvolver(limpio)
        return destino if propios.es_de_la_casa(propios._host(destino)) else limpio
    # Los enlaces de la casa no se envuelven (12/11/2026): no son un riesgo y, envueltos, dejan de
    # abrir para quien los recibe reenviados fuera de los países permitidos.
    if propios.es_de_la_casa(propios._host(limpio)):
        return limpio
    ub = encode_url(html_lib.unescape(url))
    base = (base or get_settings().public_base_url or organizacion.url_correo()).rstrip(
        "/"
    )
    return f"{base}/api/safelink?u={ub}&s={sign(ub)}"


_HREF = re.compile(r'(<a\b[^>]*?\shref=")(https?://[^"]*)(")', re.IGNORECASE)


def rewrite(html: str, base: str | None = None) -> str:
    """`base`: dirección por la que entra quien lee (su portal). Sin ella, la general."""
    if not html or "<a" not in html.lower():
        return html
    return _HREF.sub(
        lambda m: m.group(1) + gateway_link(m.group(2), base) + m.group(3), html
    )
