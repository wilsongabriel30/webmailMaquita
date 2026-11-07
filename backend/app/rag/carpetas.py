"""Qué carpetas de un buzón entran en el índice de «Conversa con tu correo».

Se indexan TODAS las carpetas personales (Enviados, carpetas propias y sus subcarpetas, las
traídas de Zimbra como «INBOX.Bandeja entrada Respaldo»...) salvo Papelera, Spam/Junk y
Borradores, y lo que no es del buzón (carpetas compartidas por otras personas y virtuales).
El nombre se compara por cada nivel de la ruta, sin mayúsculas ni tildes y sin los sufijos
que dejan las migraciones («Trash (2)», «Trash{82820000}», «Correo no deseado1»), así que
«Trash.Viejos» también queda fuera, pero no «Proveedores Draft 2024».
"""

import re
import unicodedata

from app.mail.clients.imap_client import _decode_lines, _imap_utf7_decode

# Por nombre de cada nivel (normalizado). Visto en los 261 buzones de VM 130 (04/11/2026).
NOMBRES_EXCLUIDOS = frozenset(
    {
        # Papelera
        "trash",
        "papelera",
        "deleted items",
        "deleted messages",
        "elementos eliminados",
        # Spam / Junk (y la cuarentena de virus)
        "junk",
        "junk e-mail",
        "junk email",
        "spam",
        "spambox",
        "correo no deseado",
        "correo electronico no deseado",
        "unwanted",
        "infected items",
        # Borradores
        "drafts",
        "draft",
        "borradores",
        "borrador",
    }
)
# Marcas SPECIAL-USE (RFC 6154) que Dovecot pone a esas carpetas, se llamen como se llamen.
MARCAS_EXCLUIDAS = frozenset({"trash", "junk", "drafts"})
# No son del buzón: carpetas que otra persona comparte (namespace «Compartidos/») y virtuales.
PREFIJOS_EXCLUIDOS = ("Compartidos/", "Virtual.", "Virtual/")

_RE_LIST = re.compile(r'\(([^)]*)\)\s+(?:"([^"]*)"|NIL)\s+(.+)$')
_NOMBRES_ENVIADOS = {
    "sent",
    "sent items",
    "sent messages",
    "enviados",
    "elementos enviados",
}


def normalizar(nivel: str) -> str:
    """«Correo electrónico no deseado1» -> «correo electronico no deseado»."""
    s = unicodedata.normalize("NFKD", nivel or "").encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"\{[0-9a-f]+\}$", "", s)  # Trash{82820000}
    s = re.sub(r"\s*\(\d+\)$", "", s)  # Trash (2)
    s = re.sub(r"\d+$", "", s)  # Correo no deseado1
    return s.strip()


def excluida(nombre: str, marcas=(), delimitador: str = ".") -> bool:
    """True si la carpeta NO se indexa."""
    if not nombre:
        return True
    if any(nombre.startswith(p) for p in PREFIJOS_EXCLUIDOS):
        return True
    marcas_n = {m.strip().lstrip("\\").lower() for m in marcas or ()}
    if marcas_n & {"noselect", "nonexistent"}:
        return True
    if marcas_n & MARCAS_EXCLUIDAS:
        return True
    niveles = nombre.split(delimitador) if delimitador else [nombre]
    return any(normalizar(n) in NOMBRES_EXCLUIDOS for n in niveles)


def parsear_list(lineas) -> list[dict]:
    """Respuesta de `LIST "" "*"` -> [{name, imap_name, delimiter, flags}] (name en UTF-8)."""
    carpetas = []
    for linea in _decode_lines(lineas):
        linea = linea.strip()
        if linea.upper().startswith("LIST "):
            linea = linea[5:]
        m = _RE_LIST.match(linea)
        if not m:
            continue
        marcas, delim, nombre = m.groups()
        nombre = nombre.strip()
        if nombre.startswith('"') and nombre.endswith('"') and len(nombre) >= 2:
            nombre = nombre[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        if not nombre:
            continue
        carpetas.append(
            {
                "name": _imap_utf7_decode(nombre),
                "imap_name": nombre,
                "delimiter": delim or ".",
                "flags": [f for f in marcas.split() if f],
            }
        )
    return carpetas


def a_indexar(carpetas: list[dict]) -> list[dict]:
    """Filtra las excluidas y ordena: Bandeja de entrada, Enviados y luego el resto."""
    vigentes = [
        c
        for c in carpetas
        if not excluida(c["name"], c.get("flags"), c.get("delimiter", "."))
    ]

    def orden(c):
        n = c["name"]
        if n.upper() == "INBOX":
            return (0, n)
        marcas = {f.lstrip("\\").lower() for f in c.get("flags") or ()}
        if "sent" in marcas or n.lower() in _NOMBRES_ENVIADOS:
            return (1, n)
        return (2, n.lower())

    return sorted(vigentes, key=orden)


def etiqueta(nombre: str, delimitador: str = ".") -> str:
    """Nombre legible para mostrar en las fuentes: «INBOX.SRI» -> «Bandeja de entrada / SRI»."""
    if not nombre:
        return ""
    niveles = nombre.split(delimitador) if delimitador else [nombre]
    salida = []
    for i, n in enumerate(niveles):
        if i == 0 and n.upper() == "INBOX":
            salida.append("Bandeja de entrada")
        elif i == 0 and n.lower() in _NOMBRES_ENVIADOS:
            salida.append("Enviados")
        elif i == 0 and n.lower() == "archive":
            salida.append("Archivo")
        else:
            salida.append(n)
    return " / ".join(salida)
