"""Guardar preferencias sin pisar las que no se envían (11/11/2026).

`PUT /api/settings` recibía el modelo completo: quien enviaba un solo campo (la cinta «Vista» envía
solo `reading_pane`) dejaba los demás en su valor por defecto y se perdían el nombre visible, la firma
antigua, los correos por página y hasta la respuesta automática activa.
"""

from __future__ import annotations

CLAVES_VISTA = {
    "densidad": str,
    "lineas": int,
    "orden": str,
    "modo": str,
    "anchoLista": int,
    "anchoCarpetas": int,
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
    return limpia
