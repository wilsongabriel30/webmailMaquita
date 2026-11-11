"""Guardar preferencias sin pisar las que no se envían (11/11/2026).

`PUT /api/settings` recibía el modelo completo: quien enviaba un solo campo (la cinta «Vista» envía
solo `reading_pane`) dejaba los demás en su valor por defecto y se perdían el nombre visible, la firma
antigua, los correos por página y hasta la respuesta automática activa.
"""

from __future__ import annotations

import re

CLAVES_VISTA = {
    "densidad": str,
    "lineas": int,
    "orden": str,
    "modo": str,
    "anchoLista": int,
    "anchoCarpetas": int,
    "pedirLectura": str,
}


def completar(body, fila) -> None:
    """Los campos que no llegaron en la petición conservan el valor guardado."""
    if not fila:
        return
    guardado = dict(fila)
    enviados = body.model_fields_set
    for campo in type(body).model_fields:
        if campo == "vista" or campo in enviados:
            continue
        if guardado.get(campo) is not None:
            setattr(body, campo, guardado[campo])


_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_CARPETAS_CON_COLOR = 500


def _colores(crudo) -> dict:
    """Colores de carpetas: {nombre de carpeta: «#rrggbb»}, acotado."""
    if not isinstance(crudo, dict):
        return {}
    colores = {}
    for carpeta, color in crudo.items():
        if (
            isinstance(carpeta, str)
            and 0 < len(carpeta) <= 255
            and isinstance(color, str)
            and _COLOR.match(color)
        ):
            colores[carpeta] = color.lower()
        if len(colores) >= MAX_CARPETAS_CON_COLOR:
            break
    # Vacío también se guarda: así «Sin color» en la última carpeta borra lo anterior al fusionar.
    return {"coloresCarpetas": colores}


_CLAVE_LOCAL = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
MAX_CLAVES_LOCALES = 60
MAX_VALOR_LOCAL = 20000


def _locales(crudo) -> dict:
    """Preferencias del navegador que siguen a la cuenta: {clave: texto}, acotado."""
    if not isinstance(crudo, dict):
        return {}
    locales = {}
    for clave, valor in crudo.items():
        if (
            isinstance(clave, str)
            and _CLAVE_LOCAL.match(clave)
            and isinstance(valor, str)
            and len(valor) <= MAX_VALOR_LOCAL
        ):
            locales[clave] = valor
        if len(locales) >= MAX_CLAVES_LOCALES:
            break
    return {"local": locales}


def limpiar_vista(vista) -> dict:
    """Solo las claves conocidas, con su tipo y un tamaño razonable."""
    limpia: dict = {}
    if not isinstance(vista, dict):
        return limpia
    for clave, tipo in CLAVES_VISTA.items():
        valor = vista.get(clave)
        if isinstance(valor, bool) or valor is None:
            continue
        if tipo is int and isinstance(valor, (int, float)) and 0 < valor < 5000:
            limpia[clave] = int(valor)
        elif tipo is str and isinstance(valor, str) and 0 < len(valor) <= 32:
            limpia[clave] = valor
    limpia.update(_colores(vista.get("coloresCarpetas")))
    limpia.update(_locales(vista.get("local")))
    return limpia
