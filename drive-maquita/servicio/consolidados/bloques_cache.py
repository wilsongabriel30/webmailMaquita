# -*- coding: utf-8 -*-
"""Caché de los bloques consolidados, fuente por fuente (11/09/2026).

Para que un consolidado ABIERTO se actualice en segundos cuando alguien
cambia una matriz, no se puede esperar a la consolidación completa (leer las
13 matrices, rellenar fórmulas y guardar el libro: dos minutos y medio). Aquí
se guarda, por consolidado y bloque, lo que aportó CADA fuente:

    <estado>/bloques/<consolidado>.json
    {"hoja": "ConsolidadoT",
     "bloques": {"G4": [{"archivo": <ruta física>, "hoja": ..., "rango": ...,
                         "filas": [[...], ...]}, ...]}}

- La consolidación completa la escribe al terminar.
- `consolidar_rapido.py` relee SOLO la matriz que cambió, sustituye sus
  fuentes y vuelve a guardar: segundos.
- La API «en vivo» lee de aquí el bloque apilado para el editor abierto.

Los valores se guardan como JSON: fechas como texto ISO, el resto tal cual.
"""
import datetime
import json
import os
import tempfile


def ruta_cache(estado_dir, archivo_consolidado):
    nombre = os.path.splitext(os.path.basename(archivo_consolidado))[0] + '.json'
    return os.path.join(estado_dir, 'bloques', nombre)


def _json(valor):
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.isoformat(sep=' ') if isinstance(valor, datetime.datetime) else valor.isoformat()
    return valor


def guardar(estado_dir, archivo_consolidado, hoja, bloques):
    """`bloques`: {celda: [ {archivo, hoja, rango, filas}, ... ]}. Escritura atómica."""
    ruta = ruta_cache(estado_dir, archivo_consolidado)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    try:
        os.chmod(os.path.dirname(ruta), 0o2775)   # root y sistemas escriben aquí
    except OSError:
        pass
    datos = {'hoja': hoja, 'bloques': {
        celda: [{'archivo': f['archivo'], 'hoja': f['hoja'], 'rango': f['rango'],
                 'filas': [[_json(c) for c in fila] for fila in f['filas']]}
                for f in fuentes]
        for celda, fuentes in bloques.items()}}
    fd, temporal = tempfile.mkstemp(dir=os.path.dirname(ruta), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as salida:
        json.dump(datos, salida, ensure_ascii=False)
    os.chmod(temporal, 0o664)
    os.replace(temporal, ruta)
    return ruta


def cargar(estado_dir, archivo_consolidado):
    try:
        with open(ruta_cache(estado_dir, archivo_consolidado), encoding='utf-8') as entrada:
            return json.load(entrada)
    except (OSError, ValueError):
        return None


def mtime(estado_dir, archivo_consolidado):
    try:
        return os.path.getmtime(ruta_cache(estado_dir, archivo_consolidado))
    except OSError:
        return 0


def apilar(fuentes):
    """Igual que `motor_consolidado.apilar`: concatena y rellena al ancho mayor."""
    matriz = [fila for f in fuentes for fila in f['filas']]
    if not matriz:
        return []
    ancho = max(len(fila) for fila in matriz)
    return [fila + [None] * (ancho - len(fila)) for fila in matriz]


def bloque_apilado(estado_dir, archivo_consolidado, celda):
    """El bloque completo (ya apilado) de una celda destino, o None si no hay caché."""
    datos = cargar(estado_dir, archivo_consolidado)
    if not datos or celda not in datos.get('bloques', {}):
        return None
    return apilar(datos['bloques'][celda])
