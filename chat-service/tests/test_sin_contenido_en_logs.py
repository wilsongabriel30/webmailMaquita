# -*- coding: utf-8 -*-
"""M-07 / F-10: ningún registro del chat puede llevar el contenido de un mensaje.
Falla si un print()/log en interfaces/websocket serializa el payload o el cuerpo."""
import os
import re

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "interfaces", "websocket")
PROHIBIDO = re.compile(
    r"(print|logger\.\w+|logging\.\w+)\([^\n]*\{(data|msg_data|msg_compact|mensaje_data|contenido|content|payload)\}"
)


def test_ningun_registro_lleva_el_contenido_del_mensaje():
    culpables = []
    for nombre in sorted(os.listdir(RAIZ)):
        if not nombre.endswith(".py"):
            continue
        with open(os.path.join(RAIZ, nombre), encoding="utf-8") as f:
            for n, linea in enumerate(f, 1):
                if PROHIBIDO.search(linea):
                    culpables.append(f"{nombre}:{n}")
    assert not culpables, culpables
