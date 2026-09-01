# -*- coding: utf-8 -*-
"""
Escribir con la MISMA letra del documento cuando esa letra es una estándar.
===========================================================================
«los estilos de letra, tamaño y fuente tienen que quedar idénticos al editar» —
el usuario, 18-ago-2026.

Casi todo estaba bien: el cuerpo, el color, la negrita, la cursiva, la línea
base y la sangría se conservaban al reescribir. Fallaba **el nombre de la
letra**. Cuando el documento usa una de las catorce estándar del PDF
—Helvetica, Times, Courier…, que es lo normal en lo que sale de una impresora
virtual o de un digitalizado—, escribir con `TextWriter` **incrusta** el clon
que trae PyMuPDF, y el texto editado pasaba a llamarse `NimbusSans-Regular`
mientras el resto de la página seguía siendo `Helvetica`. Se ve casi igual
—Nimbus es el clon métrico de Helvetica— pero el documento acababa con dos
letras donde había una, y en otro visor eso puede notarse.

Aquí se escribe por el otro camino, `page.insert_text`, que usa la estándar
**tal cual**, sin incrustar nada: el texto nuevo queda con el mismo nombre de
fuente, el mismo cuerpo y el mismo color que el que ya estaba. Idéntico.

Solo se usa cuando se puede garantizar el resultado:

· la letra elegida es una de las catorce estándar (lo dice `estandar14`);
· no hay que simular la negrita (con la estándar se pide la negrita de verdad);
· y el texto se puede escribir con esa codificación —las estándar solo saben de
  Latin-1—; si lleva un símbolo raro, se vuelve al camino de siempre, que
  incrusta una fuente que sí lo tiene.

Autoría: Equipo de Tecnología Maquita — 2026-08-18
"""

import logging

import fitz

logger = logging.getLogger(__name__)


def _sirve(resolucion):
    """¿Esta resolución de letra se puede escribir con la estándar del PDF?"""
    if not resolucion:
        return None
    if resolucion.get('simula_negrita'):
        return None
    return resolucion.get('estandar14') or None


def se_puede(texto):
    """Las catorce estándar solo saben de Latin-1: fuera de ahí, no valen."""
    try:
        (texto or '').encode('latin-1')
        return True
    except (UnicodeEncodeError, AttributeError):
        return False


def escribir(pagina, punto, texto, resolucion, color):
    """Escribe el texto con la estándar del documento. Dice si pudo.

    Si devuelve False no ha tocado la página: quien llama sigue con su camino
    de siempre.
    """
    codigo = _sirve(resolucion)
    if not codigo or not texto or not se_puede(texto):
        return False
    try:
        pagina.insert_text(punto, texto, fontname=codigo,
                           fontsize=resolucion['tam'], color=color)
        return True
    except Exception:
        # Cualquier tropiezo: se deja escribir a quien llamó, como siempre.
        logger.debug('no se pudo escribir con la estándar %s', codigo, exc_info=True)
        return False
