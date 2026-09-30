"""Monitor de coedición de «Ingresos proyectos Maquita.xlsx» (15/09/2026).
Cada 2 min anota: sala (key/versión/usuarios), archivo (mtime/tamaño),
callbacks y descargas del DS en los últimos 2 min, guardados lentos, avisos
de BD, tiempo de respuesta del DS y carga de VM 101.
Salida: registros/monitor-ingresos-proyectos.log (una línea por corrida).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
import api_onlyoffice as oo          # noqa: E402
import jwt                            # noqa: E402
from seguridad_rutas import ruta_fisica   # noqa: E402

RUTA = '/unidades/13/08  Proyectos/Ingresos proyectos Maquita.xlsx'
LOG = '/home/sistemas/almacen-maquita/registros/monitor-ingresos-proyectos.log'
NGX = '/var/log/nginx/maquita-access.log'
GUN = '/home/sistemas/Maquita/logs/gunicorn-error.log'
DS = oo.url_interna_ds()      # la dirección del servidor de documentos sale de la configuración
ahora = datetime.now()
desde = ahora - timedelta(minutes=2)
partes = [ahora.strftime('%H:%M:%S')]

# Sala
try:
    base = oo._base_documento(14, RUTA)
    v = oo._version_sesion(base)
    key = hashlib.sha1(f'{base}:v{v}'.encode()).hexdigest()[:20]
    c = {'c': 'info', 'key': key}
    req = urllib.request.Request(DS + '/coauthoring/CommandService.ashx',
                                 data=json.dumps(dict(c, token=jwt.encode(c, oo.secreto_ds(), algorithm='HS256'))).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.monotonic()
    r = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    ds_ms = int((time.monotonic() - t0) * 1000)
    partes.append(f"sala=v{v}/{key[:6]} usuarios={','.join(r.get('users') or []) or '-'} ds={ds_ms}ms")
except Exception as e:
    partes.append(f'sala=ERROR {str(e)[:60]}')

# Archivo
try:
    st = os.stat(ruta_fisica(14, RUTA))
    partes.append(f"archivo={datetime.fromtimestamp(st.st_mtime).strftime('%H:%M:%S')}/{st.st_size}")
except Exception as e:
    partes.append(f'archivo=ERROR {str(e)[:40]}')

# Nginx: callbacks/descargas del DS y peticiones del editor en 2 min
try:
    cb = dl = err5 = 0
    lentas = []
    tail = subprocess.run(['tail', '-n', '4000', NGX], capture_output=True, text=True).stdout.splitlines()
    for l in tail:
        m = re.search(r'\[(\d+/\w+/\d+:\d+:\d+:\d+)', l)
        if not m:
            continue
        try:
            t = datetime.strptime(m.group(1), '%d/%b/%Y:%H:%M:%S')
        except ValueError:
            continue
        if t < desde:
            continue
        if 'onlyoffice/callback' in l:
            cb += 1
        elif 'onlyoffice/download' in l:
            dl += 1
        if re.search(r'" 5\d\d ', l) and ('almacen' in l or 'onlyoffice' in l):
            err5 += 1
    partes.append(f'cb2m={cb} descargasDS={dl} http5xx={err5}')
except Exception as e:
    partes.append(f'nginx=ERROR {str(e)[:40]}')

# Gunicorn: guardados (con duración), avisos de BD, errores del almacén
try:
    tail = subprocess.run(['tail', '-n', '3000', GUN], capture_output=True, text=True).stdout.splitlines()
    guard, bd, errs = [], 0, 0
    for l in tail:
        m = re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', l)
        if not m:
            continue
        t = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
        if t < desde:
            continue
        g = re.search(r'OnlyOffice guardado ruta=(\S+).*status=(\d+) en ([\d.]+)s', l)
        if g and 'Ingresos proyectos' in l:
            guard.append(f"{g.group(3)}s")
        if 'Conexión muerta en el pool' in l:
            bd += 1
        if ' ERROR ' in l and ('almacen' in l or 'onlyoffice' in l.lower()):
            errs += 1
    partes.append(f"guardados={','.join(guard) or '-'} bdMuertas={bd} erroresAlm={errs}")
except Exception as e:
    partes.append(f'gunicorn=ERROR {str(e)[:40]}')

# Carga VM 101 y salud DS
try:
    partes.append('carga101=' + ','.join(f'{x:.2f}' for x in os.getloadavg()))
    t0 = time.monotonic()
    urllib.request.urlopen(DS + '/healthcheck', timeout=10).read()
    partes.append(f'dsHealth={int((time.monotonic() - t0) * 1000)}ms')
except Exception as e:
    partes.append(f'dsHealth=ERROR {str(e)[:40]}')

with open(LOG, 'a', encoding='utf-8') as f:
    f.write(' | '.join(partes) + '\n')
