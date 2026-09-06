"""Sanitizador del atributo `style` (M-05, cuarta revisión).

Los correos HTML dependen de estilos en línea, así que `style` no se puede quitar sin
romperlos; pero un `style` sin filtrar es un canal de fuga: `background-image: url(...)`
hace una petición saliente al abrir el mensaje (baliza de lectura y fuga de IP), y
`expression()`, `@import`, `behavior` o `position: fixed` permiten cosas peores.

Regla: solo declaraciones cuya propiedad esté en la lista blanca y cuyo valor no contenga
nada que cargue recursos ni ejecute. Lo demás se descarta declaración a declaración.
"""

import re

# [L-04] El atajo `font` se quitó de la lista: las propiedades sueltas bastan y el atajo
# admite sintaxis de sistema (`caption`, `menu`...) que el filtro no interpreta.
PROPIEDADES_PERMITIDAS = frozenset(
    {
        "color",
        "background-color",
        "background",
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "font-variant",
        "line-height",
        "letter-spacing",
        "word-spacing",
        "white-space",
        "word-break",
        "text-align",
        "text-decoration",
        "text-transform",
        "text-indent",
        "vertical-align",
        "direction",
        "unicode-bidi",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "border",
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "border-color",
        "border-style",
        "border-width",
        "border-radius",
        "border-collapse",
        "border-spacing",
        "outline",
        "width",
        "height",
        "max-width",
        "min-width",
        "max-height",
        "min-height",
        "display",
        "float",
        "clear",
        "overflow",
        "overflow-x",
        "overflow-y",
        "table-layout",
        "caption-side",
        "empty-cells",
        "list-style",
        "list-style-type",
        "list-style-position",
        "opacity",
        "box-sizing",
        "text-overflow",
    }
)

# Cualquier valor con esto se descarta entero: cargan recursos, ejecutan o sacan del flujo.
_PROHIBIDO = re.compile(
    r"url\s*\(|expression\s*\(|@import|behavior\s*:|javascript:|vbscript:|data:|"
    r"-moz-binding|\\|<|>|/\*|\*/|;",
    re.IGNORECASE,
)
_DISPLAY_PROHIBIDO = re.compile(r"^\s*(fixed|sticky)\s*$", re.IGNORECASE)


def limpiar_estilo(valor: str | None) -> str | None:
    """Devuelve el `style` filtrado, o None si no queda nada útil."""
    if not valor:
        return None
    salida = []
    for declaracion in str(valor).split(";"):
        if ":" not in declaracion:
            continue
        propiedad, contenido = declaracion.split(":", 1)
        propiedad = propiedad.strip().lower()
        contenido = contenido.strip()
        if propiedad not in PROPIEDADES_PERMITIDAS or not contenido:
            continue
        if _PROHIBIDO.search(contenido):
            continue
        if propiedad == "display" and _DISPLAY_PROHIBIDO.match(contenido):
            continue
        if len(contenido) > 200:
            continue
        salida.append(f"{propiedad}: {contenido}")
    return "; ".join(salida) if salida else None
