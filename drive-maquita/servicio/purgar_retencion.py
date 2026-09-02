# -*- coding: utf-8 -*-
"""
Purga de la retención del Almacén Maquita.
Borra DEFINITIVAMENTE lo que superó la ventana de retención (90 días).
Pensado para un cron diario.

Uso (cron):  /home/sistemas/Maquita/venv/bin/python3 purgar_retencion.py
Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

import nucleo_archivos as nucleo

if __name__ == '__main__':
    purgados = nucleo.purgar_retencion()
    logging.info('Purga de retención: %d elemento(s) eliminados definitivamente', purgados)
