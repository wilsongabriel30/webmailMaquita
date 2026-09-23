"""Imágenes pegadas en el cuerpo del correo: salen incrustadas (`cid:`), no como `data:`.

El redactor guarda la imagen pegada como `data:image/...;base64,...` para poder mostrarla y
redimensionarla en el acto. Outlook, Gmail y la mayoría de clientes NO muestran imágenes
`data:` en un correo recibido, así que al enviar cada una se convierte en una parte MIME
inline con su Content-ID y el `src` pasa a `cid:...`. El ancho y alto que la persona le dio
en el redactor (atributos `width`/`height`) se conservan tal cual.
"""

import base64
import binascii
import hashlib
import re

# Una imagen pegada razonable (captura de pantalla, foto) pesa pocos MB.
BYTES_MAX = 10 * 1024 * 1024

_EXTENSION = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}

_SRC_DATA = re.compile(
    r"""(<img\b[^>]*?\ssrc\s*=\s*)(["'])data:(image/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)\2""",
    re.IGNORECASE,
)


def incrustar_imagenes_data(html: str) -> tuple[str, list[dict]]:
    """Devuelve (html con `cid:`, adjuntos inline) con la forma que espera el envío."""
    if not html or "data:image/" not in html.lower():
        return html, []
    adjuntos: dict[str, dict] = {}

    def _reemplazar(m: re.Match) -> str:
        tipo = m.group(3).lower()
        extension = _EXTENSION.get(tipo)
        if not extension:
            return m.group(0)
        try:
            datos = base64.b64decode(re.sub(r"\s+", "", m.group(4)), validate=True)
        except (binascii.Error, ValueError):
            return m.group(0)
        if not datos or len(datos) > BYTES_MAX:
            return m.group(0)
        huella = hashlib.sha256(datos).hexdigest()[:32]
        cid = f"{huella}@cuerpo"
        adjuntos.setdefault(
            cid,
            {
                "filename": f"imagen-{len(adjuntos) + 1}.{extension}",
                "content": datos,
                "content_type": "image/jpeg" if extension == "jpg" else tipo,
                "is_inline": True,
                "cid": cid,
            },
        )
        return f"{m.group(1)}{m.group(2)}cid:{cid}{m.group(2)}"

    return _SRC_DATA.sub(_reemplazar, html), list(adjuntos.values())
