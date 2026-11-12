"""Asuntos sin marcas de «SPAM» ajenas ni caracteres dañados (12/11/2026).

Algunos servidores marcan el asunto de lo que consideran dudoso: «[===SPAM===]», «***SPAM***»,
«[SPAM]»… La marca se queda pegada al asunto y vuelve en cada respuesta, aunque la conversación sea
legítima: quien la recibe cree que NUESTRO servidor la considera spam. Nuestro antispam no marca
asuntos (lo dudoso va a «No deseado»), así que una marca así nunca dice nada útil a quien lee: se quita.

También se quitan los «�» que traen algunos boletines cuando su propio sistema daña un emoji.
"""

from __future__ import annotations

import re

# Marcas entre corchetes, llaves o asteriscos; con o sin adornos. Solo cuando la marca ES la etiqueta
# completa: «[SPAM]» sí, «Campaña antispam» no.
_MARCA = re.compile(r"""(?ix)
    (?: \[ \s* [=*\-_#!]* \s* (?:suspected\s+|posible\s+|possible\s+|probable\s+)? (?:spam|junk|correo\s+no\s+deseado) \?? \s* [=*\-_#!]* \s* \]
      | \{ \s* (?:spam|junk) \?? \s* \}
      | \*{2,} \s* (?:spam|junk) \s* \*{2,}
      | ={2,} \s* (?:spam|junk) \s* ={2,}
      | \(\s* spam \s*\) (?=\s|$)
    ) \s* :? \s*
    """)


def limpiar(asunto: str) -> str:
    if not asunto:
        return asunto
    limpio = _MARCA.sub("", asunto)
    limpio = re.sub(r"�+", "", limpio)
    limpio = re.sub(r"[ \t]{2,}", " ", limpio).strip()
    return limpio or asunto.strip()
