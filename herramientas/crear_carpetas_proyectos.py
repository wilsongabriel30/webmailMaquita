"""Crea las carpetas de proyectos (solo nombres) a partir del plan del Excel.

Uso: python3 crear_carpetas_proyectos.py <usuario_id> <ruta_base> <plan.json>
Ejemplo demo: 14 "/demo pory" plan_proyectos.json
Las carpetas que ya existen se respetan (no se tocan ni se duplican).
"""
import json
import os
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import nucleo_archivos as nucleo          # noqa: E402
from seguridad_rutas import ruta_fisica   # noqa: E402

usuario = int(sys.argv[1])
base = sys.argv[2].rstrip('/')
plan = json.load(open(sys.argv[3], encoding='utf-8'))

creadas = existian = 0
for p in plan:
    anio_dir = f"{p['anio']} Proyectos e Ingresos"
    padre = f"{base}/{anio_dir}"
    if not os.path.isdir(ruta_fisica(usuario, padre)):
        nucleo.crear_carpeta(usuario, base, anio_dir)
    if os.path.isdir(ruta_fisica(usuario, f"{padre}/{p['nombre']}")):
        existian += 1
        continue
    nucleo.crear_carpeta(usuario, padre, p['nombre'])
    creadas += 1
print(f"creadas={creadas} ya_existian={existian}")
