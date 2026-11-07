"""Reglas traídas de Zimbra que el editor de reglas del webmail no sabe representar.

Al migrar desde Zimbra (04/11/2026) las reglas simples (una condición y una acción) pasaron al
formato normal del webmail y se ven y editan en Ajustes → Reglas. Las demás (varias condiciones
a la vez, copia CC, List-Id, cuerpo) viajan como Sieve estándar dentro de este bloque marcado,
al final del script activo del usuario, igual que el bloque de remitentes de confianza.

Como `_save_script` regenera el script entero desde vacaciones y reglas, debe volver a poner este
bloque; si no, editar cualquier regla borraría en silencio las reglas de Zimbra del usuario.
"""

import re

MARCA_INI = "# --- REGLAS TRAIDAS DE ZIMBRA (no se editan desde el webmail) ---"
MARCA_FIN = "# --- FIN REGLAS TRAIDAS DE ZIMBRA ---"

_REQUIRE = re.compile(r"^require\s*\[([^\]]*)\]\s*;", re.MULTILINE)
_EXTENSIONES = {"fileinto": "fileinto ", "imap4flags": "addflag ", "body": "body "}


def extraer(script: str) -> str:
    """El contenido del bloque (sin las marcas). Cadena vacía si no hay bloque."""
    if not script or MARCA_INI not in script:
        return ""
    return script.split(MARCA_INI, 1)[1].split(MARCA_FIN, 1)[0].strip("\n")


def quitar(script: str) -> str:
    if not script or MARCA_INI not in script:
        return script
    antes, resto = script.split(MARCA_INI, 1)
    despues = resto.split(MARCA_FIN, 1)[1] if MARCA_FIN in resto else ""
    return (antes.rstrip("\n") + "\n" + despues.lstrip("\n")).strip("\n") + "\n"


def _asegurar_require(script: str, contenido: str) -> str:
    """Declara en el `require` las extensiones que usa el bloque."""
    faltan = [e for e, uso in _EXTENSIONES.items() if uso in contenido]
    m = _REQUIRE.search(script)
    actuales = m.group(1) if m else ""
    faltan = [e for e in faltan if f'"{e}"' not in actuales]
    if not faltan:
        return script
    nuevas = ", ".join(f'"{e}"' for e in faltan)
    if not m:
        return f"require [{nuevas}];\n\n" + script.lstrip("\n")
    linea = (
        f"require [{actuales.strip()}, {nuevas}];"
        if actuales.strip()
        else f"require [{nuevas}];"
    )
    return script[: m.start()] + linea + script[m.end() :]


def aplicar(script: str, contenido: str) -> str:
    """El script con el bloque de Zimbra al final (después de las reglas del webmail)."""
    limpio = quitar(script or "")
    if not contenido.strip():
        return limpio
    limpio = _asegurar_require(limpio, contenido)
    return (
        limpio.rstrip("\n")
        + "\n\n"
        + MARCA_INI
        + "\n"
        + contenido.strip("\n")
        + "\n"
        + MARCA_FIN
        + "\n"
    )
