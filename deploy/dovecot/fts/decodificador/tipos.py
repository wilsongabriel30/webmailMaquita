"""Qué formatos decodifica y cómo se reconoce cada uno por su contenido, no solo por su MIME.

Dovecot pregunta primero la lista de formatos (el decodificador sin argumentos la imprime: un
Content-Type y sus extensiones por línea) y luego llama con el Content-Type de cada adjunto. El tipo
declarado lo pone quien envía, así que se comprueba con los primeros bytes: un «PDF» que en realidad
es un ZIP se trata como ZIP, y un ejecutable disfrazado no se abre con nada.
"""

import zipfile

# Content-Type → (clase, extensiones). Las extensiones sirven a Dovecot para los adjuntos que
# llegan como application/octet-stream.
FORMATOS = [
    ("application/pdf", "pdf", ["pdf"]),
    ("application/x-pdf", "pdf", ["pdf"]),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "ooxml", ["docx"]),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "ooxml", ["xlsx"]),
    ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "ooxml", ["pptx"]),
    # Con macros: se lee solo el texto; el código VBA (vbaProject.bin) ni se abre ni se ejecuta.
    ("application/vnd.ms-word.document.macroenabled.12", "ooxml", ["docm"]),
    ("application/vnd.ms-excel.sheet.macroenabled.12", "ooxml", ["xlsm"]),
    ("application/vnd.ms-powerpoint.presentation.macroenabled.12", "ooxml", ["pptm"]),
    ("application/vnd.oasis.opendocument.text", "odf", ["odt"]),
    ("application/vnd.oasis.opendocument.spreadsheet", "odf", ["ods"]),
    ("application/vnd.oasis.opendocument.presentation", "odf", ["odp"]),
    ("application/msword", "ole", ["doc"]),
    ("application/vnd.ms-excel", "ole", ["xls"]),
    ("application/vnd.ms-powerpoint", "ole", ["ppt"]),
    ("application/rtf", "rtf", ["rtf"]),
    ("text/rtf", "rtf", ["rtf"]),
    ("text/html", "html", ["html", "htm"]),
    ("application/xhtml+xml", "html", ["xhtml"]),
    ("application/zip", "zip", ["zip"]),
    ("application/x-zip-compressed", "zip", ["zip"]),
    ("application/x-tar", "tar", ["tar"]),
    ("application/gzip", "gzip", ["gz", "tgz"]),
    ("application/x-gzip", "gzip", ["gz", "tgz"]),
    ("application/x-compressed-tar", "gzip", ["tgz"]),
    ("application/x-bzip2", "bzip2", ["bz2", "tbz2"]),
    ("application/x-xz", "xz", ["xz", "txz"]),
    ("application/x-7z-compressed", "7z", ["7z"]),
    ("image/jpeg", "imagen", ["jpg", "jpeg"]),
    ("image/png", "imagen", ["png"]),
    ("image/tiff", "imagen", ["tif", "tiff"]),
    ("image/webp", "imagen", ["webp"]),
    ("image/heic", "imagen", ["heic"]),
]
CLASE_POR_TIPO = {ct: clase for ct, clase, _ in FORMATOS}
CLASE_POR_EXTENSION = {ext: clase for _, clase, exts in FORMATOS for ext in exts}
# Dentro de un comprimido no hay Content-Type: estos se leen como texto por su extensión.
CLASE_POR_EXTENSION.update({e: "texto" for e in ("txt", "csv", "md", "log", "json", "xml")})


def lista_para_dovecot() -> str:
    """Una línea por formato y una línea vacía al final: sin ella Dovecot da la lista por incompleta
    («parser script didn't send empty EOF line»)."""
    return "\n".join(f"{ct} {' '.join(exts)}" for ct, _, exts in FORMATOS) + "\n\n"


def por_firma(datos: bytes) -> str | None:
    """Clase según los primeros bytes; None si no se reconoce."""
    cab = datos[:600]
    if cab.startswith(b"%PDF-"):
        return "pdf"
    if cab.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return "zip"  # familia ZIP: ooxml, odf o comprimido; lo decide clase_de_zip
    if cab.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"
    if cab.startswith(b"{\\rtf"):
        return "rtf"
    if cab.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if cab.startswith(b"\x1f\x8b"):
        return "gzip"
    if cab.startswith(b"BZh") and cab[3:4].isdigit():
        return "bzip2"
    if cab.startswith(b"\xfd7zXZ\x00"):
        return "xz"
    if len(cab) >= 262 and cab[257:262] == b"ustar":
        return "tar"
    if cab.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"II*\x00", b"MM\x00*")):
        return "imagen"
    if cab[:4] == b"RIFF" and cab[8:12] == b"WEBP":
        return "imagen"
    if cab[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return "imagen"
    if cab.startswith((b"MZ", b"\x7fELF", b"#!")):
        return "ejecutable"
    inicio = cab.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if inicio.startswith((b"<!doctype html", b"<html", b"<?xml")) and b"<html" in cab.lower():
        return "html"
    return None


def clase_de_zip(zf: zipfile.ZipFile) -> str:
    """Un ZIP puede ser un documento de Office, uno de LibreOffice o un comprimido sin más."""
    nombres = set(zf.namelist()[:5000])
    if "[Content_Types].xml" in nombres and any(
        n.startswith(("word/", "xl/", "ppt/")) for n in nombres
    ):
        return "ooxml"
    if "mimetype" in nombres and "content.xml" in nombres:
        return "odf"
    return "zip"


def decidir(declarado: str, datos: bytes, nombre: str = "") -> str | None:
    """La clase con la que se decodifica. La firma manda sobre lo declarado.

    `nombre` es el del archivo dentro de un comprimido (sin Content-Type): su extensión hace de tipo
    declarado.
    """
    clase_decl = CLASE_POR_TIPO.get((declarado or "").strip().lower())
    if nombre and "." in nombre:
        clase_decl = CLASE_POR_EXTENSION.get(nombre.rsplit(".", 1)[1].lower(), clase_decl)
    firma = por_firma(datos)
    if firma == "ejecutable":
        return None
    if firma == "zip":
        return "zip"  # el llamador abre el ZIP y lo afina con clase_de_zip
    if firma:
        return firma
    # Sin firma reconocible solo se aceptan los formatos de texto.
    if clase_decl in ("html", "texto"):
        return clase_decl
    return None
