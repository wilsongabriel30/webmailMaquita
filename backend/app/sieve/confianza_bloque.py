"""Bloque «remitentes de confianza» dentro del filtro personal del usuario.

Su correo llega SIEMPRE a la Bandeja de entrada, aunque el antispam lo marque: el bloque hace
`fileinto "INBOX"; stop;`, y ese `stop` corta la cadena antes de que corra el filtro global
posterior (`after.sieve`), que es quien manda el spam a No deseado.

Antes esto era un script personal aparte que `before.sieve` incluia con
`include :optional :personal "confianza"`. Eso tumbaba la entrega: en Pigeonhole 2.4.1 el
include de un script personal que no existe revienta con segfault PESE al `:optional`, y solo 8
de los 279 buzones tenian ese script. Resultado: ~500 caidas de LMTP al dia y 43 correos
devueltos al remitente entre el 19 y el 21/09/2026. Por eso ahora el bloque viaja dentro del
propio script activo del usuario y no hay ningun `include`.

El bloque va delimitado por marcas para poder leerlo y regenerarlo sin tocar lo que el usuario
tenga de vacaciones o de reglas.
"""

import re

MARCA_INI = "# --- REMITENTES DE CONFIANZA (generado por Maquita; no editar a mano) ---"
MARCA_FIN = "# --- FIN REMITENTES DE CONFIANZA ---"

_DIRECCION = re.compile(r'if header :contains "from" "([^"]+)"')


def generar(direcciones: list[str]) -> str:
    """El bloque sieve para esas direcciones. Cadena vacia si no hay ninguna."""
    if not direcciones:
        return ""
    lineas = [MARCA_INI]
    for d in direcciones:
        segura = d.replace("\\", "").replace('"', "")
        lineas.append(
            f'if header :contains "from" "{segura}" {{ fileinto "INBOX"; stop; }}'
        )
    lineas.append(MARCA_FIN)
    return "\n".join(lineas)


def extraer(script: str) -> list[str]:
    """Las direcciones del bloque de un script. Lista vacia si no hay bloque."""
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


_REQUIRE = re.compile(r"^require\s*\[([^\]]*)\]\s*;", re.MULTILINE)


def _asegurar_fileinto(script: str) -> str:
    """El bloque usa `fileinto`, asi que el script tiene que declararlo en su `require`."""
    m = _REQUIRE.search(script)
    if not m:
        return 'require ["fileinto"];\n\n' + script.lstrip("\n")
    if '"fileinto"' in m.group(1):
        return script
    linea = f'require [{m.group(1).strip()}, "fileinto"];'
    return script[: m.start()] + linea + script[m.end() :]


def aplicar(script: str, direcciones: list[str]) -> str:
    """El script del usuario con su bloque de confianza al dia.

    Quita el bloque anterior (si lo habia) y pone el nuevo justo detras del `require`, antes de
    vacaciones y reglas: es lo primero que debe mirarse.
    """
    limpio = quitar(script or "")
    bloque = generar(direcciones)
    if not bloque:
        return limpio
    limpio = _asegurar_fileinto(limpio)
    m = _REQUIRE.search(limpio)
    corte = m.end() if m else 0
    cabeza = limpio[:corte].rstrip("\n")
    cola = limpio[corte:].lstrip("\n")
    partes = [cabeza, "", bloque]
    if cola:
        partes += ["", cola.rstrip("\n")]
    return "\n".join(partes) + "\n"
