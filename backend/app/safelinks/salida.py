"""Safe Links — al ENVIAR un correo, los enlaces de nuestra pasarela vuelven a su destino real (12/11/2026).

El enlace seguro protege a quien LEE en nuestro servidor: envuelve los enlaces de los correos que
recibimos. Pero al responder, reenviar o copiar un enlace desde un correo ya envuelto, ese enlace
(«https://<portal del correo>/api/safelink?u=…») salía tal cual hacia la persona de fuera, y para
abrirlo tenía que llegar a nuestro servidor de correo, que filtra por país. El 11/11/2026 una
contraparte en el extranjero no pudo abrir un enlace del Drive por esto.

Aquí se deshace la envoltura en el cuerpo que sale (HTML y texto). Nunca rompe el envío: ante
cualquier duda el texto queda como estaba.
"""

from __future__ import annotations

import html as html_lib
import logging
import re

from . import propios

log = logging.getLogger(__name__)

# Un enlace de la pasarela tal como aparece en el cuerpo (en HTML el «&» va como «&amp;»).
_PASARELA = re.compile(
    r"https?://[^\s\"'<>()\[\]]+/api/safelink\?[^\s\"'<>()\[\]]+", re.IGNORECASE
)


def _real(crudo: str) -> str | None:
    url = html_lib.unescape(crudo)
    if not propios.es_pasarela(url):
        return None
    destino = propios.desenvolver(url)
    if destino == url or not destino.lower().startswith(("http://", "https://")):
        return None
    return destino


def desenvolver_html(html: str | None) -> tuple[str | None, int]:
    if not html or "/api/safelink?" not in html:
        return html, 0
    n = 0

    def cambiar(m: re.Match) -> str:
        nonlocal n
        destino = _real(m.group(0))
        if destino is None:
            return m.group(0)
        n += 1
        return html_lib.escape(destino, quote=True)

    try:
        return _PASARELA.sub(cambiar, html), n
    except Exception as error:  # noqa: BLE001 — el correo sale igual
        log.warning(
            "No se pudieron desenvolver los enlaces del HTML: %s", type(error).__name__
        )
        return html, 0


def desenvolver_texto(texto: str | None) -> tuple[str | None, int]:
    if not texto or "/api/safelink?" not in texto:
        return texto, 0
    n = 0

    def cambiar(m: re.Match) -> str:
        nonlocal n
        destino = _real(m.group(0))
        if destino is None:
            return m.group(0)
        n += 1
        return destino

    try:
        return _PASARELA.sub(cambiar, texto), n
    except Exception as error:  # noqa: BLE001
        log.warning(
            "No se pudieron desenvolver los enlaces del texto: %s", type(error).__name__
        )
        return texto, 0
