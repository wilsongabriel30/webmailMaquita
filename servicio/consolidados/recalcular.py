#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calcula las fórmulas de un .xlsx para poder guardar sus resultados.

Por qué hace falta. `openpyxl` escribe las fórmulas pero deja su resultado
vacío, así que los totales aparecían en blanco: en los consolidados y también
en cualquier libro que reciba datos por un vínculo.

Quién calcula. El único motor de cálculo de la VM 101 es el LibreOffice que ya
vive dentro del contenedor `gotenberg` (instalado hace meses para convertir
documentos). **No interviene en la edición ni en el trabajo colaborativo**: eso
lo sigue haciendo OnlyOffice, igual que siempre. Aquí solo se usa como
calculadora, en el servidor, sobre una copia desechable que nadie ve.

Cómo se llega a él. El servicio web corre como `sistemas`, que no tiene acceso a
Docker a propósito (tenerlo equivale a ser root). Se pasa por
`/usr/local/bin/recalcular-hoja`, un guion de root que solo acepta dos rutas de
archivo bajo /tmp y las valida antes de nada.

Nunca escribe sobre el original: devuelve un archivo nuevo.
"""
import os
import shutil
import subprocess
import tempfile
import uuid

PUENTE = '/usr/local/bin/recalcular-hoja'
TIEMPO_MAXIMO = 320


def recalcular(ruta_origen, ruta_destino):
    """Calcula las fórmulas de `ruta_origen` y deja el resultado en `ruta_destino`.

    Devuelve (True, '') o (False, motivo). No lanza: si falla, quien llama debe
    poder seguir con el archivo sin los resultados.
    """
    if not os.path.exists(PUENTE):
        return False, 'falta %s (el puente al motor de cálculo)' % PUENTE

    # El puente solo admite rutas bajo /tmp con nombres sencillos: los nombres
    # reales del Drive llevan tildes, espacios y emojis.
    carpeta = tempfile.mkdtemp(prefix='calc-')
    marca = uuid.uuid4().hex[:12]
    entrada = os.path.join(carpeta, 'e-%s.xlsx' % marca)
    salida = os.path.join(carpeta, 's-%s.xlsx' % marca)
    try:
        shutil.copy2(ruta_origen, entrada)
        proceso = subprocess.run(['sudo', '-n', PUENTE, entrada, salida],
                                 capture_output=True, timeout=TIEMPO_MAXIMO)
        if proceso.returncode != 0:
            return False, (proceso.stderr or b'').decode('utf-8', 'ignore')[-180:]
        if not os.path.exists(salida) or os.path.getsize(salida) == 0:
            return False, 'el archivo calculado salió vacío'
        shutil.copy2(salida, ruta_destino)
        return True, ''
    except subprocess.TimeoutExpired:
        return False, 'la hoja tardó demasiado en calcularse'
    except Exception as excepcion:
        return False, str(excepcion)[:180]
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        sys.exit('uso: recalcular.py <origen.xlsx> <destino.xlsx>')
    ok, motivo = recalcular(sys.argv[1], sys.argv[2])
    print('OK' if ok else 'FALLO: %s' % motivo)
    sys.exit(0 if ok else 1)
