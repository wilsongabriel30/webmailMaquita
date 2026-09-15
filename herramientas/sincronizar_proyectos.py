"""Unidad 13 / 08  Proyectos: llevar a las carpetas CREADAS el 14/09/2026 lo que se
haya subido después en las carpetas de origen (2020..2023 Proyectos e Ingresos).

Solo se copia lo que falta (misma ruta relativa) en la carpeta nueva; nada se
sobrescribe ni se borra. Los orígenes no se tocan.
Uso: python3 sincronizar_proyectos.py [ejecutar]
"""
import json
import os
import re
import sys
import glob
from datetime import datetime

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import nucleo_archivos as nucleo                      # noqa: E402
from seguridad_rutas import ruta_fisica               # noqa: E402

USUARIO = 14
BASE = '/unidades/13/08  Proyectos'
DESTINO = BASE + '/2024 2025 2026 Proyectos e Ingresos'
ANIOS = sys.argv[2].split(',') if len(sys.argv) > 2 else ['2020', '2021', '2022', '2023']
ORIGENES = [BASE + f'/{a} Proyectos e Ingresos' for a in ANIOS]
ejecutar = len(sys.argv) > 1 and sys.argv[1] == 'ejecutar'
HOY = datetime.now().strftime('%Y%m%d-%H%M')
REG = f'/home/sistemas/almacen-maquita/registros/proyectos-sincronizar-{HOY}.json'


def norm(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())


def tokens_de(nombre):
    crudos = nombre.replace('-', ' ').split()
    partidos = nombre.replace('.', '. ').replace('-', ' ').split()
    return [norm(t) for t in crudos + partidos]


def lleva_codigo(nombre, codigo):
    k = norm(codigo)
    t = tokens_de(nombre)
    return k in t or ('PROY' + k) in t or ('PORY' + k) in t


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


# Carpetas creadas por nosotros: «NNN Proy CÓDIGO» → hoy «NNN CÓDIGO» (sin Proy).
creadas = {}
for f in glob.glob('/home/sistemas/almacen-maquita/registros/proyectos-0*-20260914.json'):
    for a in json.load(open(f, encoding='utf-8')):
        if a['accion'] == 'crear':
            m = re.match(r'^(\d{3}) Proy (.+)$', a['a'])
            creadas[m.group(1)] = m.group(2)

fis_dest = ruta_fisica(USUARIO, DESTINO)
actuales = {n[:3]: n for n in os.listdir(fis_dest) if re.match(r'^\d{3} ', n)}

registro, faltantes, cambiados, total_nuevos = [], [], [], 0
for num, cod in sorted(creadas.items()):
    carpeta = actuales.get(num)
    if not carpeta:
        print(f'[OJO] no existe ya la carpeta {num} ({cod})')
        continue
    for fuente in fuentes_de(cod):
        fis_src = ruta_fisica(USUARIO, fuente)
        for raiz, dirs, archivos in os.walk(fis_src):
            rel_dir = os.path.relpath(raiz, fis_src)
            rel_dir = '' if rel_dir == '.' else rel_dir
            for nombre in sorted(archivos):
                rel = os.path.join(rel_dir, nombre) if rel_dir else nombre
                src = os.path.join(raiz, nombre)
                dst = os.path.join(fis_dest, carpeta, rel)
                if os.path.exists(dst):
                    if os.path.getsize(dst) != os.path.getsize(src) and os.path.getmtime(src) > os.path.getmtime(dst):
                        cambiados.append((carpeta, rel, fuente))
                    continue
                total_nuevos += 1
                print(f'[copiar] {fuente}/{rel}  →  {carpeta}/{rel}')
                if ejecutar:
                    v_src = fuente + '/' + rel.replace(os.sep, '/')
                    v_dst = DESTINO + '/' + carpeta + '/' + rel.replace(os.sep, '/')
                    nucleo.copiar(USUARIO, v_src, v_dst)
                    registro.append({'accion': 'copiar', 'de': v_src, 'a': v_dst})

print(f'\nArchivos nuevos por copiar: {total_nuevos}')
if cambiados:
    print('\nArchivos que EXISTEN en la nueva pero el origen cambió después (no se tocan):')
    for c in cambiados:
        print('  ', c)
if ejecutar and registro:
    json.dump(registro, open(REG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Registro para revertir: {REG} ({len(registro)} acciones)')
