"""Bloque «remitentes bloqueados» dentro del filtro personal del usuario.

Es el opuesto del bloque de remitentes de confianza: el correo de estas direcciones va SIEMPRE a
No deseado, aunque el antispam lo deje pasar. Lo llena «Marcar como spam» (05/11/2026): en Zimbra
marcar un boletín como spam no servía y el siguiente volvía a la bandeja; aquí la decisión de la
persona se queda. «No es spam» quita la dirección del bloque.

Va justo detrás del `require`, antes de vacaciones y reglas, para que a un remitente bloqueado no
le conteste la respuesta automática. Viaja dentro del script activo (sin `include`: en
Pigeonhole 2.4.1 el include de un script personal reventaba LMTP, ver confianza_bloque).
"""

import re

MARCA_INI = "# --- REMITENTES BLOQUEADOS (generado por Maquita; no editar a mano) ---"
MARCA_FIN = "# --- FIN REMITENTES BLOQUEADOS ---"
MAXIMO = 500

_DIRECCION = re.compile(r'if address :is "from" "([^"]+)"')
_REQUIRE = re.compile(r"^require\s*\[([^\]]*)\]\s*;", re.MULTILINE)


def generar(direcciones: list[str]) -> str:
    """El bloque sieve para esas direcciones. Cadena vacía si no hay ninguna."""
    if not direcciones:
        return ""
    lineas = [MARCA_INI]
    for d in direcciones:
        segura = d.replace("\\", "").replace('"', "")
        lineas.append(
            f'if address :is "from" "{segura}" {{ fileinto :create "Junk"; stop; }}'
        )
    lineas.append(MARCA_FIN)
    return "\n".join(lineas)


def extraer(script: str) -> list[str]:
    """Las direcciones del bloque de un script. Lista vacía si no hay bloque."""
    if not script or MARCA_INI not in script:
        return []
    trozo = script.split(MARCA_INI, 1)[1].split(MARCA_FIN, 1)[0]
    return sorted({m.group(1).lower() for m in _DIRECCION.finditer(trozo)})


def quitar(script: str) -> str:
    """El script sin el bloque, para poder regenerarlo desde cero."""
    if not script or MARCA_INI not in script:
        return script
    antes, resto = script.split(MARCA_INI, 1)
    despues = resto.split(MARCA_FIN, 1)[1] if MARCA_FIN in resto else ""
    return (antes.rstrip("\n") + "\n" + despues.lstrip("\n")).strip("\n") + "\n"


def _asegurar_require(script: str) -> str:
    """El bloque usa `fileinto :create`: el script debe declarar fileinto y mailbox."""
    m = _REQUIRE.search(script)
    actuales = m.group(1) if m else ""
    faltan = [e for e in ("fileinto", "mailbox") if f'"{e}"' not in actuales]
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


def aplicar(script: str, direcciones: list[str]) -> str:
    """El script del usuario con su bloque de bloqueados al día, justo detrás del `require`."""
    limpio = quitar(script or "")
    bloque = generar(direcciones)
    if not bloque:
        return limpio
    limpio = _asegurar_require(limpio)
    m = _REQUIRE.search(limpio)
    corte = m.end() if m else 0
    cabeza = limpio[:corte].rstrip("\n")
    cola = limpio[corte:].lstrip("\n")
    partes = [cabeza, "", bloque]
    if cola:
        partes += ["", cola.rstrip("\n")]
    return "\n".join(partes) + "\n"
