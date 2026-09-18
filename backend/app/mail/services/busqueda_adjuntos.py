"""Búsqueda por nombre o extensión de archivo adjunto.

IMAP no permite buscar por el nombre de los adjuntos, así que se hace en dos pasos:
1. La búsqueda IMAP se acota a mensajes multipart (los que pueden llevar archivos).
2. De esos se pide BODYSTRUCTURE (solo la estructura, no el contenido) y se conservan los
   que tengan un archivo cuyo nombre contenga el texto o termine en la extensión pedida.

Operadores en la barra: `adjunto:factura` (nombre) y `adjunto:.pdf` o `adjunto:pdf`
(extensión). `adjunto:si` sigue significando «con adjuntos».
"""

import re
from email.header import decode_header, make_header

_RE_TOKEN = re.compile(
    r'(?:^|\s)(?:adjunto|archivo|attachment|ext|extension|extensión):(?:"([^"]+)"|(\S+))',
    re.I,
)
_RE_NOMBRE = re.compile(
    r'\((?:"(?:NAME|FILENAME)\*?"|(?:NAME|FILENAME)\*?)\s+"((?:[^"\\]|\\.)*)"', re.I
)
_RE_UID = re.compile(r"\b(\d+) FETCH \(UID (\d+)\b")
_EXTENSIONES_CONOCIDAS = {
    "pdf",
    "zip",
    "rar",
    "7z",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "csv",
    "txt",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "xml",
    "json",
    "odt",
    "ods",
    "odp",
    "mp3",
    "mp4",
    "eml",
    "ics",
    "vcf",
}
TOPE_CANDIDATOS = 4000  # se revisan como mucho los 4000 más recientes
TANDA = 250


def extraer_patrones(query: str) -> tuple[str, list[str]]:
    """Separa los operadores de adjunto del resto de la consulta.

    Devuelve (consulta sin esos operadores, patrones). Un patrón que empieza por «.» o que es
    una extensión conocida se compara con la extensión; el resto, como texto dentro del nombre.
    """
    patrones: list[str] = []

    def quitar(m: re.Match) -> str:
        valor = (m.group(1) or m.group(2) or "").strip().lower()
        if not valor or valor in ("si", "sí", "yes"):
            return m.group(
                0
            )  # «adjunto:si» lo trata el analizador normal (con adjuntos)
        patrones.append(valor)
        return " "

    resto = _RE_TOKEN.sub(quitar, query or "")
    return re.sub(r"\s+", " ", resto).strip(), patrones


def _decodificar(nombre: str) -> str:
    nombre = nombre.replace('\\"', '"').replace("\\\\", "\\")
    try:
        if "=?" in nombre:
            return str(make_header(decode_header(nombre)))
    except Exception:
        pass
    # RFC 2231: utf-8''nombre%20con%20espacios
    if "''" in nombre:
        from urllib.parse import unquote

        return unquote(nombre.split("''", 1)[1])
    return nombre


def nombres_de_estructura(estructura: str) -> list[str]:
    """Nombres de archivo que aparecen en un BODYSTRUCTURE."""
    return [_decodificar(m.group(1)) for m in _RE_NOMBRE.finditer(estructura)]


def coincide(nombres: list[str], patrones: list[str]) -> bool:
    for patron in patrones:
        p = patron.lstrip(".")
        por_extension = patron.startswith(".") or p in _EXTENSIONES_CONOCIDAS
        ok = False
        for n in nombres:
            nl = n.lower()
            if por_extension and nl.rsplit(".", 1)[-1] == p and "." in nl:
                ok = True
            elif not por_extension and p in nl:
                ok = True
            if ok:
                break
        if not ok:
            return False
    return True


async def filtrar_uids_por_adjunto(
    imap, uids: list[int], patrones: list[str]
) -> list[int]:
    """Conserva, en el mismo orden, los UIDs con algún adjunto que cumpla los patrones."""
    if not patrones or not uids:
        return uids
    candidatos = uids[:TOPE_CANDIDATOS]
    resultado: list[int] = []
    for i in range(0, len(candidatos), TANDA):
        tanda = candidatos[i : i + TANDA]
        try:
            resp = await imap.uid(
                "fetch", ",".join(str(u) for u in tanda), "(BODYSTRUCTURE)"
            )
        except Exception:
            continue
        if resp.result != "OK":
            continue
        texto = "\n".join(
            (
                l.decode("utf-8", "replace")
                if isinstance(l, (bytes, bytearray))
                else str(l)
            )
            for l in resp.lines
        )
        # Cada respuesta empieza por «<seq> FETCH (UID <uid> …»; lo que sigue es su estructura.
        trozos = _RE_UID.split(texto)
        # split devuelve: [pre, seq, uid, cuerpo, seq, uid, cuerpo, ...]
        encontrados: set[int] = set()
        for j in range(1, len(trozos) - 2, 3):
            uid = int(trozos[j + 1])
            if coincide(nombres_de_estructura(trozos[j + 2]), patrones):
                encontrados.add(uid)
        resultado.extend(u for u in tanda if u in encontrados)
    return resultado
