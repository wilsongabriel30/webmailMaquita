# -*- coding: utf-8 -*-
"""
Importar una pieza suelta de FARO sin arrastrar la aplicación entera.
=====================================================================

El problema, medido el 31-jul-2026: el subproceso del OCR tardaba **9,4 s** en
resolver 12 hojas, y solo ~4 s eran reconocer. Los otros **5,5 s eran el arranque**.
La culpa es de `modulos/__init__.py`, que importa TODOS los módulos de FARO —chat,
nómina, finanzas, tecnología, ODK…— en cuanto alguien escribe `import modulos`.
Al subproceso del OCR no le hace falta ni uno: solo quiere leer texto de un PDF.

Aquí se registran los paquetes del camino como **huecos**: módulos vacíos con su
`__path__` apuntando a la carpeta de verdad. Python encuentra igual los submódulos y
los `from ...dominio…` siguen resolviendo, pero **no se ejecuta ningún `__init__.py`
del camino**, que es donde estaba el gasto.

No sirve para todo: vale cuando se quiere una clase concreta de dentro (leer texto,
comprimir) y no la aplicación montada. Si el `__init__` de un paquete define algo que
el código usa de verdad, no se puede huecar y hay que importarlo normal.

Esto se usa **solo desde `conversor_cli.py`**, que es un proceso aparte y de usar y
tirar. Dentro de FARO en marcha no pinta nada: allí los `__init__` ya están hechos.

Autoría: Equipo de Tecnología Maquita — 2026-07-31
"""

import importlib
import os
import sys
import types

# Los paquetes del camino que solo son carpetas para el OCR: ninguno aporta nada que
# se use, y el primero cuesta 4,3 s. `modulos.pdf_editor.dominio` NO está aquí a
# propósito: sus excepciones y entidades sí se usan, así que se importa de verdad.
HUECOS = (
    'modulos',
    'modulos.pdf_editor',
    'modulos.pdf_editor.infraestructura',
    'modulos.pdf_editor.infraestructura.externos',
)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))


def _huecar(nombre):
    """Registra `nombre` como paquete vacío que apunta a su carpeta real."""
    if nombre in sys.modules:
        return                      # ya importado de verdad: no se toca
    carpeta = os.path.join(RAIZ, *nombre.split('.'))
    if not os.path.isdir(carpeta):
        raise ImportError('No existe la carpeta del paquete %s' % nombre)
    paquete = types.ModuleType(nombre)
    paquete.__path__ = [carpeta]
    paquete.__package__ = nombre
    sys.modules[nombre] = paquete
    padre, _, hijo = nombre.rpartition('.')
    if padre:
        setattr(sys.modules[padre], hijo, paquete)


def importar(ruta_modulo):
    """El módulo pedido, sin ejecutar los `__init__.py` del camino.

    Ejemplo: `importar('modulos.pdf_editor.infraestructura.externos.cliente_pymupdf')`.
    """
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)
    for nombre in HUECOS:
        if ruta_modulo.startswith(nombre + '.') or ruta_modulo == nombre:
            _huecar(nombre)
    return importlib.import_module(ruta_modulo)


def cliente_pdf():
    """Un `ClientePyMuPDF` listo, por la vía corta."""
    modulo = importar('modulos.pdf_editor.infraestructura.externos.cliente_pymupdf')
    return modulo.ClientePyMuPDF()
