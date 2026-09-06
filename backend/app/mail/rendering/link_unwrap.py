"""
Desenvoltura de enlaces de rastreo en correos entrantes.

QUÉ HACE
--------
Muchos proveedores envían su correo a través de servicios de terceros (Amazon
SES, Postmark, ...) que **reemplazan cada enlace del mensaje por uno propio**
para contar los clics:

    Usuario hace clic → track.pstmrk.it (registra el clic) → destino real

Este módulo detecta esos enlaces y los reemplaza por el destino real, cuando
ese destino viene embebido dentro del propio enlace.

POR QUÉ
-------
1. **Robustez**: si el intermediario falla o está bloqueado, el enlace muere
   aunque el destino esté sano. Ocurrió el 2026-08-24: los enlaces de
   recuperación de contraseña de un proveedor no abrían en toda la LAN.
2. **Privacidad**: al no pasar por el rastreador, esas empresas dejan de
   registrar quién de la organización abrió qué.
3. **Transparencia**: el usuario ve a dónde va realmente el enlace, lo que
   además ayuda a detectar phishing.

DÓNDE ACTÚA
-----------
Solo **al mostrar** el mensaje, nunca al recibirlo. El correo original se
guarda intacto en el buzón, con su firma DKIM válida. Esto es deliberado:
modificar el cuerpo al recibirlo invalidaría la firma y destruiría el
original, y sería irreversible.

PRINCIPIO DE SEGURIDAD
----------------------
**Ante la duda, no tocar.** Si un enlace no se puede desenvolver con
certeza, se deja exactamente como está. Es preferible dejar pasar un enlace
con rastreo a romper un enlace legítimo.

LIMITACIÓN CONOCIDA
-------------------
No todos los servicios se pueden desenvolver. Algunos (HubSpot, buena parte
de Mailchimp) usan identificadores opacos: el destino real solo lo conoce el
servidor del tercero. Esos enlaces se dejan intactos a propósito, y por eso
sigue haciendo falta la excepción de DNS que permite alcanzarlos.

Ver: 03-INFRAESTRUCTURA/RED-MIKROTIK/fix-dns-bloqueaba-awstrack-enlaces-correo-20260824.md
"""

import re
import urllib.parse
from typing import Optional, Tuple

# Esquemas aceptados en el destino. Cualquier otro (javascript:, data:, file:)
# se descarta por seguridad: no se sustituye el enlace.
ESQUEMAS_PERMITIDOS = ("http://", "https://")

# Longitud máxima razonable de una URL desenvuelta. Evita que un patrón mal
# formado produzca una cadena enorme.
MAX_LARGO_URL = 4000


def _es_destino_valido(url: str) -> bool:
    """Comprueba que lo extraído sea una URL http(s) plausible."""
    if not url or len(url) > MAX_LARGO_URL:
        return False
    if not url.lower().startswith(ESQUEMAS_PERMITIDOS):
        return False
    # Debe tener un host después del esquema
    try:
        partes = urllib.parse.urlparse(url)
        return bool(partes.netloc) and "." in partes.netloc
    except (ValueError, AttributeError):
        return False


def _desenvolver_amazon_ses(url: str) -> Optional[str]:
    """
    Amazon SES (awstrack.me).

    Formato:
        https://XXXX.r.us-east-1.awstrack.me/L0/<URL-codificada>/1/<id>/<firma>

    El destino va URL-encoded justo después de "/L0/".
    """
    m = re.search(r"awstrack\.me/L0/(.+?)/\d+/", url)
    if not m:
        return None
    return urllib.parse.unquote(m.group(1))


def _desenvolver_postmark(url: str) -> Optional[str]:
    """
    Postmark (pstmrk.it).

    Formato:
        https://track.pstmrk.it/<cod>/<destino-sin-esquema>/<tokens...>

    El destino va sin "https://", por lo que hay que reponerlo.
    """
    m = re.search(r"pstmrk\.it/\w+/(.+?)/[A-Za-z0-9_-]{2,6}/", url)
    if not m:
        return None
    destino = urllib.parse.unquote(m.group(1))
    if not destino.lower().startswith(ESQUEMAS_PERMITIDOS):
        destino = "https://" + destino
    return destino


# Cada entrada: (marca identificativa en el enlace, función que lo desenvuelve).
# Para añadir un servicio nuevo basta con sumar una función y su entrada aquí.
DESENVOLVEDORES = (
    ("awstrack.me", _desenvolver_amazon_ses),
    ("pstmrk.it", _desenvolver_postmark),
)


def desenvolver_url(url: str) -> Optional[str]:
    """
    Devuelve la URL real escondida dentro de un enlace de rastreo,
    o None si no es un enlace de rastreo conocido o no se puede desenvolver
    con seguridad.

    Es una función pura: no lanza excepciones y no modifica su entrada.
    """
    if not url or not isinstance(url, str):
        return None

    for marca, desenvolvedor in DESENVOLVEDORES:
        if marca not in url:
            continue
        try:
            destino = desenvolvedor(url)
        except Exception:
            # Ante cualquier fallo inesperado, se deja el enlace intacto.
            return None
        if destino and _es_destino_valido(destino):
            return destino
        return None
    return None


def desenvolver_enlaces_html(html: str) -> Tuple[str, int]:
    """
    Recorre los href de un HTML y sustituye los enlaces de rastreo conocidos
    por su destino real.

    Devuelve: (html_resultante, cantidad_de_enlaces_desenvueltos)

    Si el HTML viene vacío o algo falla, devuelve el original sin tocar.
    """
    if not html or not isinstance(html, str):
        return html, 0

    # Salida rápida: si no aparece ninguna marca conocida, no se procesa nada.
    if not any(marca in html for marca, _ in DESENVOLVEDORES):
        return html, 0

    contador = 0

    def _reemplazar(match: "re.Match") -> str:
        nonlocal contador
        prefijo, url, sufijo = match.group(1), match.group(2), match.group(3)
        destino = desenvolver_url(url)
        if not destino:
            return match.group(0)  # no se toca
        contador += 1
        # Se escapan las comillas del destino para no romper el atributo.
        destino_seguro = destino.replace('"', "%22").replace("'", "%27")
        return f"{prefijo}{destino_seguro}{sufijo}"

    try:
        # Captura href="..." y href='...' conservando el tipo de comilla.
        patron = re.compile(r'(href\s*=\s*")([^"]+)(")', re.IGNORECASE)
        resultado = patron.sub(_reemplazar, html)
        patron_simple = re.compile(r"(href\s*=\s*')([^']+)(')", re.IGNORECASE)
        resultado = patron_simple.sub(_reemplazar, resultado)
    except Exception:
        # Si el procesamiento falla, se devuelve el HTML original intacto.
        return html, 0

    return resultado, contador
