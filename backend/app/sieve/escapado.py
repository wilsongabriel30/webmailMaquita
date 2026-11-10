"""Cadenas entre comillas de Sieve: cómo se escriben y cómo se vuelven a leer.

En una cadena Sieve entre comillas (RFC 5228 §2.4.2) solo hay dos caracteres especiales:
la barra invertida y la comilla. `\\x` significa «x» para cualquier carácter, así que al
escribir hay que doblar la barra ANTES de escapar la comilla, y al leer basta con quitar
una barra a cada pareja `\\x`.

Hasta el 09/11/2026 solo se escapaba la comilla: un valor terminado en `\\` dejaba la
cadena sin cerrar (el script no compilaba y la persona recibía un 500) y el analizador no
entendía `\\"`, con lo que una regla con comillas desaparecía al releer y la respuesta
automática se apagaba sola. Este módulo es la única fuente de verdad para ambos sentidos.
"""

import re

# Caracteres que nunca van dentro de un valor: saltos de línea y controles (evitan que un
# valor «salte» fuera de su cadena o de su comentario e inyecte código Sieve).
_PELIGROSOS = re.compile(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]")

# Fragmento de expresión regular para una cadena Sieve entre comillas, con escapes.
# El grupo 1 es el contenido todavía escapado: pasarlo por `desescapar`.
CADENA = r'"((?:[^"\\]|\\.)*)"'

_ESCAPE = re.compile(r"\\(.)", re.DOTALL)


def sanear(valor: str) -> str:
    """Quita saltos de línea y caracteres de control; recorta espacios en los extremos."""
    return _PELIGROSOS.sub("", valor or "").strip()


def escapar(valor: str) -> str:
    """Prepara un valor para ir entre comillas en Sieve: `\\` → `\\\\` y `"` → `\\"`."""
    return sanear(valor).replace("\\", "\\\\").replace('"', '\\"')


def desescapar(texto: str) -> str:
    """Deshace `escapar`: cada pareja `\\x` vuelve a ser `x`."""
    return _ESCAPE.sub(r"\1", texto or "")
