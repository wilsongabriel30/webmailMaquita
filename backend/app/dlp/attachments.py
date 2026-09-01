"""
DLP — Nivel 2 (2026-08-28): extracción de texto de adjuntos salientes para
pasarlos por los mismos detectores que el cuerpo del correo.

Soporta: txt/csv/json/xml/html, docx, xlsx, pptx, pdf, zip (recursivo, 1 nivel).
Lo que no se puede leer (zip cifrado, imágenes, formatos desconocidos, archivos
grandes) se reporta como "no inspeccionable" para que la política avise.
Diseño fail-open: cualquier error -> texto vacío, nunca rompe el envío.
"""
from __future__ import annotations
import io
import re
import zipfile

MAX_BYTES = 25 * 1024 * 1024      # no leer adjuntos mayores a 25 MB
MAX_TEXT = 2_000_000              # tope de caracteres extraídos por adjunto
_TEXT_EXT = {"txt", "csv", "tsv", "json", "xml", "html", "htm", "md", "log", "eml"}
_IMG_EXT = {"png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff", "webp", "heic"}
_ZIP_XML = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/slides/"}


def _ext(name: str) -> str:
    return (name or "").rsplit(".", 1)[-1].lower() if "." in (name or "") else ""


def _strip_xml(data: bytes) -> str:
    txt = data.decode("utf-8", "replace")
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt)


def _office(content: bytes, prefix: str) -> str:
    out = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for n in z.namelist():
            if n.startswith(prefix) and n.endswith(".xml") or n == "xl/sharedStrings.xml":
                out.append(_strip_xml(z.read(n)))
                if sum(len(o) for o in out) > MAX_TEXT:
                    break
    return " ".join(out)


def _pdf(content: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(content), maxpages=200) or ""


def _zip(content: bytes, depth: int) -> tuple[str, list[str]]:
    texts, unins = [], []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for info in z.infolist()[:200]:
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                unins.append(f"{info.filename} (zip con contraseña)")
                continue
            try:
                data = z.read(info)
            except RuntimeError:
                unins.append(f"{info.filename} (zip cifrado)")
                continue
            t, u = extract_text(data, info.filename, depth=depth + 1)
            texts.append(t)
            unins.extend(u)
    return " ".join(texts), unins


def extract_text(content: bytes, filename: str, content_type: str = "", depth: int = 0) -> tuple[str, list[str]]:
    """Devuelve (texto, [motivos de no inspeccionable])."""
    name = filename or "adjunto"
    ext = _ext(name)
    if not content:
        return "", []
    if len(content) > MAX_BYTES:
        return "", [f"{name} (demasiado grande para inspeccionar)"]
    if ext in _IMG_EXT or (content_type or "").startswith("image/"):
        return "", [f"{name} (imagen: no se puede inspeccionar el contenido)"]
    try:
        if ext in _TEXT_EXT or (content_type or "").startswith("text/"):
            return content.decode("utf-8", "replace")[:MAX_TEXT], []
        if ext in _ZIP_XML:
            return _office(content, _ZIP_XML[ext])[:MAX_TEXT], []
        if ext == "pdf" or content_type == "application/pdf":
            t = _pdf(content)[:MAX_TEXT]
            return (t, []) if t.strip() else ("", [f"{name} (PDF sin texto, posible imagen escaneada)"])
        if ext == "zip" and depth < 1:
            return _zip(content, depth)
        if ext in ("doc", "xls", "ppt", "rar", "7z"):
            return "", [f"{name} (formato .{ext} no inspeccionable)"]
    except Exception as e:  # fail-open
        return "", [f"{name} (error al leer: {type(e).__name__})"]
    return "", []


def extract_all(attachments: list[dict]) -> tuple[str, list[str]]:
    """attachments: [{filename, content(bytes), content_type}] -> (texto, no_inspeccionables)."""
    texts, unins = [], []
    for a in attachments or []:
        t, u = extract_text(a.get("content") or b"", a.get("filename") or "", a.get("content_type") or "")
        if t:
            texts.append(f"\n[ADJUNTO {a.get('filename')}]\n{t}")
        unins.extend(u)
    return "".join(texts), unins
