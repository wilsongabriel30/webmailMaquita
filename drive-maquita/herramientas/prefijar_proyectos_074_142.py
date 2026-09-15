"""Corrección 14/09/2026: las carpetas que YA tenían nombre no se renombran del todo;
solo se les antepone el orden del Excel. «074 Proy GO.15» → «074 GO15 GV Manos Unidas Guayas»."""
import json
import os
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import nucleo_archivos as nucleo            # noqa: E402
from seguridad_rutas import ruta_fisica     # noqa: E402

U = 14
D = '/unidades/13/08  Proyectos/2024 2025 2026 Proyectos e Ingresos'
REG = '/home/sistemas/almacen-maquita/registros/proyectos-074-142-20260914.json'
reg = json.load(open(REG, encoding='utf-8'))
hechas = []
for a in list(reg):
    if a['accion'] != 'renombrar' or a.get('corregido'):
        continue
    numero = a['a'].split()[0]
    nuevo = numero + ' ' + a['de']
    if os.path.isdir(ruta_fisica(U, D + '/' + nuevo)):
        print('[ya estaba]', nuevo)
    elif os.path.isdir(ruta_fisica(U, D + '/' + a['a'])):
        nucleo.renombrar(U, D + '/' + a['a'], nuevo)
        print(a['a'], ' → ', nuevo)
    else:
        print('[no está]', a['a'])
        continue
    a['corregido'] = True
    hechas.append({'accion': 'renombrar', 'de': a['a'], 'a': nuevo})
reg.extend(hechas)
json.dump(reg, open(REG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(hechas), 'corregidas')
