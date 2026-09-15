"""Unidad 13 / 08  Proyectos / 2024 2025 2026: carpetas 074..142 con «NNN Proy CÓDIGO».

- Si ya hay una carpeta del código → se RENOMBRA (se anota el nombre viejo para revertir).
- Si no hay → se CREA y se le COPIA el contenido de las carpetas del mismo código que
  haya en «2020..2023 Proyectos e Ingresos» (las de origen no se tocan).
Uso: python3 organizar_proyectos_74_142.py plan.json [ejecutar]
"""
import json
import os
import re
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import nucleo_archivos as nucleo                      # noqa: E402
from seguridad_rutas import ruta_fisica               # noqa: E402
from copia_nombre_libre import nombre_libre           # noqa: E402

USUARIO = 14                      # administrador de la unidad
BASE = '/unidades/13/08  Proyectos'
DESTINO = BASE + '/2024 2025 2026 Proyectos e Ingresos'
ORIGENES = [BASE + f'/{a} Proyectos e Ingresos' for a in (2020, 2021, 2022, 2023)]
NO_TOCAR = {'N12 Caritas Diputación de Bizkaia Napo'}   # cruza con dos códigos: se deja
ejecutar = len(sys.argv) > 2 and sys.argv[2] == 'ejecutar'
plan = json.load(open(sys.argv[1], encoding='utf-8'))


def norm(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())


def carpetas_con_codigo(codigo):
    """Carpetas de 2020-2023 cuyo nombre lleva el código como palabra."""
    k = norm(codigo)
    halladas = []
    for anio in ORIGENES:
        fis = ruta_fisica(USUARIO, anio)
        if not os.path.isdir(fis):
            continue
        for nombre in sorted(os.listdir(fis)):
            if not os.path.isdir(os.path.join(fis, nombre)):
                continue
            tokens = [norm(t) for t in nombre.replace('.', '. ').split()]
            if k in tokens or ('PROY' + k) in tokens:
                halladas.append(anio + '/' + nombre)
    return halladas


registro = []
for p in plan:
    nuevo = p['nuevo']
    actual = p['actual']
    ruta_nueva = DESTINO + '/' + nuevo
    if actual == nuevo:
        print(f'[ya está]  {nuevo}')
        continue
    if actual and actual not in NO_TOCAR:
        print(f'[renombrar] {actual}  →  {nuevo}')
        if ejecutar:
            nucleo.renombrar(USUARIO, DESTINO + '/' + actual, nuevo)
            registro.append({'accion': 'renombrar', 'de': actual, 'a': nuevo})
        continue
    fuentes = carpetas_con_codigo(p['cod'])
    print(f'[crear]     {nuevo}' + (f'   ← copiar de: {fuentes}' if fuentes else ''))
    if not ejecutar:
        continue
    if not os.path.isdir(ruta_fisica(USUARIO, ruta_nueva)):
        nucleo.crear_carpeta(USUARIO, DESTINO, nuevo)
        registro.append({'accion': 'crear', 'a': nuevo})
    for fuente in fuentes:
        fis = ruta_fisica(USUARIO, fuente)
        for hijo in sorted(os.listdir(fis)):
            destino_hijo = nombre_libre(USUARIO, ruta_nueva + '/' + hijo)
            nucleo.copiar(USUARIO, fuente + '/' + hijo, destino_hijo)
            registro.append({'accion': 'copiar', 'de': fuente + '/' + hijo, 'a': destino_hijo})

if ejecutar:
    salida = '/home/sistemas/almacen-maquita/registros/proyectos-074-142-20260914.json'
    json.dump(registro, open(salida, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\nRegistro para revertir: {salida} ({len(registro)} acciones)')
