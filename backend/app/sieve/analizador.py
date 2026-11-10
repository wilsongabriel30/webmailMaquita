"""Relee el script Sieve «webmail» y recupera las reglas y la respuesta automática.

Acepta lo que genera `generador.py` hoy y lo que generaron las versiones anteriores:
`header` y `address` en la condición, `fileinto` con o sin `:create`, `setflag` y `addflag`,
con o sin `stop;`, y cadenas con escapes (`\\"`, `\\\\`). Un script antiguo con
`header :is "From"` se relee como «De es exactamente» y, al guardarse de nuevo, el generador
lo escribe ya con `address`.
"""

import re

from app.sieve.escapado import CADENA, desescapar
from app.sieve.modelos import (
    FilterAction,
    FilterCondition,
    FilterRule,
    VacationSettings,
    bandera_canonica,
)

_VACACIONES = re.compile(
    r"vacation\s+:days\s+\d+\s+:subject\s+" + CADENA + r"\s+" + CADENA + r"\s*;",
    re.DOTALL,
)
_DESDE = re.compile(r'currentdate\s+:value\s+"ge"\s+"date"\s+' + CADENA)
_HASTA = re.compile(r'currentdate\s+:value\s+"le"\s+"date"\s+' + CADENA)

# Una regla: comentario con el nombre, condición de una línea, acción, `stop` opcional y cierre.
_REGLA = re.compile(
    r"#\s*filter\[\d+\]:[ \t]*(.*?)\n"
    r"if\s+(header|address)\s+(:contains|:is|:matches)\s+"
    + CADENA
    + r"\s+"
    + CADENA
    + r"\s*\{\s*\n"
    r"[ \t]+(.+?);[ \t]*\n"
    r"(?:[ \t]+stop;[ \t]*\n)?"
    r"\}",
    re.MULTILINE,
)
_FILEINTO = re.compile(r"fileinto\s+(?::create\s+)?" + CADENA)
_BANDERA = re.compile(r"(?:setflag|addflag)\s+" + CADENA)
_REDIRECT = re.compile(r"redirect\s+" + CADENA)

_OPERADOR = {":contains": "contains", ":is": "is", ":matches": "matches"}
_CAMPO = {"from": "from", "to": "to", "subject": "subject"}


def parse_vacation_from_script(script: str) -> VacationSettings:
    """La respuesta automática del script (apagada si no hay orden `vacation`)."""
    if not script:
        return VacationSettings(enabled=False)
    m = _VACACIONES.search(script)
    if not m:
        return VacationSettings(enabled=False)
    desde = _DESDE.search(script)
    hasta = _HASTA.search(script)
    return VacationSettings(
        enabled=True,
        subject=desescapar(m.group(1)),
        body=desescapar(m.group(2)),
        start_date=desescapar(desde.group(1)) if desde else None,
        end_date=desescapar(hasta.group(1)) if hasta else None,
    )


def _accion(linea: str) -> FilterAction | None:
    linea = linea.strip()
    if linea.startswith("fileinto"):
        m = _FILEINTO.match(linea)
        return FilterAction(type="move", value=desescapar(m.group(1)) if m else "INBOX")
    if linea.startswith(("setflag", "addflag")):
        m = _BANDERA.match(linea)
        return FilterAction(
            type="flag", value=bandera_canonica(desescapar(m.group(1)) if m else None)
        )
    if linea == "discard":
        return FilterAction(type="delete")
    if linea.startswith("redirect"):
        m = _REDIRECT.match(linea)
        return FilterAction(type="forward", value=desescapar(m.group(1)) if m else "")
    return None


def parse_filters_from_script(script: str) -> list[FilterRule]:
    """Las reglas de la persona, en el orden del script. Lo que no se entiende se omite."""
    if not script:
        return []
    reglas: list[FilterRule] = []
    for m in _REGLA.finditer(script):
        nombre, _test, comparador, encabezado, valor, linea_accion = m.groups()
        campo = _CAMPO.get(desescapar(encabezado).lower())
        if campo is None:
            continue
        accion = _accion(linea_accion)
        if accion is None:
            continue
        reglas.append(
            FilterRule(
                name=desescapar(nombre).strip(),
                condition=FilterCondition(
                    field=campo,
                    operator=_OPERADOR.get(comparador, "contains"),
                    value=desescapar(valor),
                ),
                action=accion,
            )
        )
    return reglas
