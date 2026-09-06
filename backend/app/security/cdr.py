"""CDR — Content Disarm & Reconstruction (básico) para adjuntos Office.

Desarma macros de documentos OOXML (.docm/.xlsm/.pptm/.docx con vbaProject, etc.)
quitando las partes VBA del paquete ZIP. NO ejecuta nada (a diferencia de un
sandbox): solo reconstruye el documento sin el código embebido.

Limitaciones (documentar en el README):
- Solo OOXML (paquetes ZIP). Formatos OLE legacy (.doc/.xls binarios) no se
  reconstruyen aquí: deben bloquearse o pasar por sandbox.
- No sustituye a un sandbox dinámico (CAPE/Cuckoo) para amenazas no basadas en macros.
"""

import io
import zipfile

_OOXML_EXT = (
    ".docx",
    ".docm",
    ".dotm",
    ".xlsx",
    ".xlsm",
    ".xltm",
    ".pptx",
    ".pptm",
    ".potm",
    ".ppam",
    ".xlam",
)
_VBA_MARKERS = ("vbaproject.bin", "vbadata.xml", "vbaprojectsignature.bin")


def is_ooxml(filename: str, content: bytes) -> bool:
    return filename.lower().endswith(_OOXML_EXT) and content[:2] == b"PK"


def disarm(content: bytes, filename: str) -> tuple[bytes, list[str]]:
    """Devuelve (contenido_desarmado, acciones). Si no aplica, devuelve el original."""
    actions: list[str] = []
    if not is_ooxml(filename, content):
        return content, actions
    try:
        zin = zipfile.ZipFile(io.BytesIO(content))
        out = io.BytesIO()
        removed = False
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                low = item.filename.lower()
                if any(m in low for m in _VBA_MARKERS):
                    actions.append(f"eliminado: {item.filename}")
                    removed = True
                    continue
                data = zin.read(item.filename)
                # quitar la declaración del vbaProject del Content_Types
                if low.endswith("[content_types].xml") and b"vbaProject" in data:
                    import re

                    data = re.sub(rb"<Override[^>]*vbaProject[^>]*/>", b"", data)
                    actions.append("limpiado: [Content_Types].xml")
                zout.writestr(item, data)
        if removed:
            actions.append("macros desarmadas (CDR)")
            return out.getvalue(), actions
        return content, actions
    except Exception as e:  # noqa: BLE001
        return content, [f"cdr_error: {e}"]


def has_macros(content: bytes, filename: str) -> bool:
    if not is_ooxml(filename, content):
        return False
    try:
        names = zipfile.ZipFile(io.BytesIO(content)).namelist()
        return any(any(m in n.lower() for m in _VBA_MARKERS) for n in names)
    except Exception:  # noqa: BLE001
        return False
