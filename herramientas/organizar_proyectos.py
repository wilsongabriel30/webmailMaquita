"""Unidad 13 / 08  Proyectos / 2024 2025 2026: carpetas por orden del Excel.

Regla (Wilson, 14/09/2026):
- La carpeta del código YA existe → se le antepone SOLO el número («074 GO15 GV Manos…»).
- No existe → se crea «NNN Proy CÓDIGO» y se le copia lo que haya del código en
  «2020..2023 Proyectos e Ingresos» (los orígenes no se tocan; nada se sobrescribe).
Uso: python3 organizar_proyectos.py plan.json DESDE HASTA [ejecutar]
"""
import json
import os
import re
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import nucleo_archivos as nucleo                      # noqa: E402
from seguridad_rutas import ruta_fisica               # noqa: E402
from copia_nombre_libre import nombre_libre           # noqa: E402

USUARIO = 14
BASE = '/unidades/13/08  Proyectos'
DESTINO = BASE + '/2024 2025 2026 Proyectos e Ingresos'
ORIGENES = [BASE + f'/{a} Proyectos e Ingresos' for a in (2020, 2021, 2022, 2023)]
plan = json.load(open(sys.argv[1], encoding='utf-8'))
desde, hasta = int(sys.argv[2]), int(sys.argv[3])
ejecutar = len(sys.argv) > 4 and sys.argv[4] == 'ejecutar'
REG = f'/home/sistemas/almacen-maquita/registros/proyectos-{desde:03d}-{hasta:03d}-20260914.json'


def norm(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())


def tokens_de(nombre):
    # Con y sin partir por el punto: «B.7» debe cruzar tanto con «B.7» como con «B7».
    crudos = nombre.replace('-', ' ').split()
    partidos = nombre.replace('.', '. ').replace('-', ' ').split()
    return [norm(t) for t in crudos + partidos]


def lleva_codigo(nombre, codigo):
    k = norm(codigo)
    t = tokens_de(nombre)
    return k in t or ('PROY' + k) in t or ('PORY' + k) in t


def actuales():
    fis = ruta_fisica(USUARIO, DESTINO)
    return sorted(n for n in os.listdir(fis) if os.path.isdir(os.path.join(fis, n)))


def fuentes_de(codigo):
    halladas = []
    for anio in ORIGENES:
        fis = ruta_fisica(USUARIO, anio)
        if not os.path.isdir(fis):
            continue
        for nombre in sorted(os.listdir(fis)):
            if os.path.isdir(os.path.join(fis, nombre)) and lleva_codigo(nombre, codigo):
                halladas.append(anio + '/' + nombre)
    return halladas


registro = []
for p in plan:
    o, cod = p['orden'], p['cod']
    if not (desde <= o <= hasta):
        continue
    pref = f'{o:03d}'
    candidatas = [n for n in actuales() if lleva_codigo(re.sub(r'^\d{3}\s+', '', n), cod)]
    ya = [n for n in candidatas if n.startswith(pref + ' ')]
    if ya:
        print(f'[ya está]   {ya[0]}')
        continue
    sin_numero = [n for n in candidatas if not re.match(r'^\d{3}\s', n)]
    otro_numero = [n for n in candidatas if re.match(r'^\d{3}\s', n)]
    if len(sin_numero) > 1:
        print(f'[DUDA]      {cod} cruza con varias: {sin_numero} — no se toca')
        continue
    if sin_numero:
        actual = sin_numero[0]
        # ¿El mismo nombre cruza con OTRO código del plan? (caso N12 / N.12)
        otros = [q['cod'] for q in plan if q['cod'] != cod and lleva_codigo(actual, q['cod'])]
        if otros:
            print(f'[DUDA]      «{actual}» cruza con {cod} y con {otros} — no se toca')
            continue
        nuevo = pref + ' ' + actual
        print(f'[prefijar]  {actual}  →  {nuevo}')
        if ejecutar:
            nucleo.renombrar(USUARIO, DESTINO + '/' + actual, nuevo)
            registro.append({'accion': 'renombrar', 'de': actual, 'a': nuevo})
        continue
    if otro_numero:
        print(f'[OJO]       {cod} (orden {pref}) ya tiene carpeta con otro número: {otro_numero} — no se toca')
        continue
    nuevo = f'{pref} Proy {cod}'
    fuentes = fuentes_de(cod)
    print(f'[crear]     {nuevo}' + (f'   ← copiar de: {fuentes}' if fuentes else ''))
    if not ejecutar:
        continue
    nucleo.crear_carpeta(USUARIO, DESTINO, nuevo)
    registro.append({'accion': 'crear', 'a': nuevo})
    for fuente in fuentes:
        fis = ruta_fisica(USUARIO, fuente)
        for hijo in sorted(os.listdir(fis)):
            destino_hijo = nombre_libre(USUARIO, DESTINO + '/' + nuevo + '/' + hijo)
            nucleo.copiar(USUARIO, fuente + '/' + hijo, destino_hijo)
            registro.append({'accion': 'copiar', 'de': fuente + '/' + hijo, 'a': destino_hijo})

if ejecutar:
    json.dump(registro, open(REG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\nRegistro para revertir: {REG} ({len(registro)} acciones)')
