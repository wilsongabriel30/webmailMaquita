#!/usr/bin/env python3
"""Publica (y verifica) el instalador de la app «Conectar Drive Maquita».

La flota se actualiza sola leyendo `drive-windows-version.json`: si ese archivo
y el `.exe` no cuadran, ~150 equipos se quedan sin actualizar o descargan algo
que no es. Por eso publicar es un solo paso, con respaldo y con verificación
contra la URL pública, en vez de copiar a mano.

    publicar-app-windows verificar
    publicar-app-windows publicar /ruta/ConectarDriveMaquita-Setup.exe 2.7.16 --notas "…"

Tras publicar comprueba la descarga real: tamaño y sha256 de lo que sirve
https://nube.example.org/static/ deben coincidir con lo declarado.

Cada archivo se escribe en un temporal de la misma carpeta y se pone en su sitio
con un renombrado (atómico). Escribir encima del mismo archivo hacía que nginx,
que guarda el descriptor y el tamaño hasta 60 s (`open_file_cache`), sirviera
durante ese minuto una mezcla del instalador viejo y el nuevo (R-52, 26/11/2026).
Con el renombrado, quien descarga recibe el viejo entero o el nuevo entero. El
json va al final, cuando los instaladores ya están en su sitio.
"""
import argparse
import datetime as dt
import grp
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time

ESTATICOS = '/home/sistemas/Maquita/interfaces/web/estaticos'
NOMBRE_EXE = 'ConectarDriveMaquita-Setup.exe'
NOMBRE_JSON = 'drive-windows-version.json'
URL_BASE = os.getenv('ALMACEN_URL_LINKS', 'https://nube.example.org').rstrip('/') + '/static'
MINIMO_BYTES = 50 * 1024 * 1024        # un Setup real ronda los 85-90 MB
# nginx puede seguir sirviendo el archivo anterior hasta 60 s tras el renombrado.
ESPERA_VERIFICAR_S = 90
PAUSA_VERIFICAR_S = 15


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for trozo in iter(lambda: f.read(1024 * 1024), b''):
            h.update(trozo)
    return h.hexdigest()


def _permisos(ruta):
    """644, dueño `sistemas` y grupo `www-data` (si existen y hay permiso)."""
    os.chmod(ruta, 0o644)
    try:
        os.chown(ruta, pwd.getpwnam('sistemas').pw_uid, grp.getgrnam('www-data').gr_gid)
    except (KeyError, PermissionError, OSError):
        pass


def colocar(destino, origen=None, texto=None):
    """Deja `destino` con el contenido de `origen` (archivo) o de `texto`.

    Escribe en un temporal oculto de la misma carpeta (mismo disco, para que el
    renombrado sea atómico), le pone los permisos y lo renombra sobre `destino`.
    Si algo falla a medias, borra el temporal y `destino` queda como estaba.
    """
    carpeta = os.path.dirname(destino)
    fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=f'.{os.path.basename(destino)}.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            if origen is not None:
                with open(origen, 'rb') as o:
                    shutil.copyfileobj(o, f, 1024 * 1024)
            else:
                f.write(texto.encode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        if origen is not None:
            shutil.copystat(origen, tmp)
        _permisos(tmp)
        os.replace(tmp, destino)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _curl(url, salida=None):
    orden = ['curl', '-sk', '--max-time', '120', url]
    if salida:
        orden += ['-o', salida]
    return subprocess.run(orden, capture_output=True, text=not salida).stdout


def verificar():
    """Compara lo declarado, lo que hay en disco y lo que se descarga."""
    exe, js = os.path.join(ESTATICOS, NOMBRE_EXE), os.path.join(ESTATICOS, NOMBRE_JSON)
    if not (os.path.exists(exe) and os.path.exists(js)):
        sys.exit('Falta el .exe o el .json en ' + ESTATICOS)
    with open(js, encoding='utf-8') as f:
        declarado = json.load(f)
    en_disco = {'tamano': os.path.getsize(exe), 'sha256': sha256(exe)}

    tmp = '/tmp/verificar-setup-publicado.exe'
    _curl(declarado.get('url') or f'{URL_BASE}/{NOMBRE_EXE}', tmp)
    servido = {'tamano': os.path.getsize(tmp), 'sha256': sha256(tmp)} if os.path.exists(tmp) else {}
    json_servido = _curl(f'{URL_BASE}/{NOMBRE_JSON}')
    if os.path.exists(tmp):
        os.remove(tmp)

    print(f'declarado : v{declarado.get("version")} · {declarado.get("tamano")} bytes · {declarado.get("sha256")}')
    print(f'en disco  : {en_disco["tamano"]} bytes · {en_disco["sha256"]}')
    print(f'servido   : {servido.get("tamano")} bytes · {servido.get("sha256")}')
    ok = (declarado.get('tamano') == en_disco['tamano'] == servido.get('tamano')
          and declarado.get('sha256') == en_disco['sha256'] == servido.get('sha256')
          and declarado.get('version', '') in (json_servido or ''))
    print('RESULTADO :', 'TODO CUADRA' if ok else '⚠ NO CUADRA — revisar antes de avisar a la gente')
    return 0 if ok else 1


def publicar(origen, version, notas):
    if not os.path.isfile(origen):
        sys.exit(f'No existe {origen}')
    tamano = os.path.getsize(origen)
    if tamano < MINIMO_BYTES:
        sys.exit(f'{origen} pesa {tamano} bytes: demasiado poco para ser el instalador.')
    with open(origen, 'rb') as f:
        if f.read(2) != b'MZ':
            sys.exit(f'{origen} no parece un ejecutable de Windows.')

    exe, js = os.path.join(ESTATICOS, NOMBRE_EXE), os.path.join(ESTATICOS, NOMBRE_JSON)
    marca = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    for ruta in (exe, js):
        if os.path.exists(ruta):
            shutil.copy2(ruta, f'{ruta}.bak.{marca}')
            print(f'respaldo: {ruta}.bak.{marca}')

    # Copia CON LA VERSIÓN EN EL NOMBRE: quien la baja sabe qué está bajando, y
    # queda claro en Descargas cuál es cuál. El nombre fijo se mantiene porque
    # hay enlaces que apuntan a él; el json manda a la copia con versión.
    exe_ver = os.path.join(ESTATICOS, f'ConectarDriveMaquita-Setup-{version}.exe')
    # Si ya existe (se republica la misma versión, p. ej. firmada), también se respalda.
    if os.path.exists(exe_ver):
        shutil.copy2(exe_ver, f'{exe_ver}.bak.{marca}')
        print(f'respaldo: {exe_ver}.bak.{marca}')
    colocar(exe_ver, origen=origen)
    colocar(exe, origen=origen)
    huella = sha256(exe)
    if huella != sha256(exe_ver):
        sys.exit('Las dos copias del instalador no coinciden: el json NO se ha tocado. Revisar el disco.')
    datos = {
        'version': version,
        'url': f'{URL_BASE}/ConectarDriveMaquita-Setup-{version}.exe',
        'sha256': huella,
        'tamano': os.path.getsize(exe),
        'fecha': dt.date.today().isoformat(),
        'notas': notas,
    }
    # El json, el último: así nunca anuncia un instalador que aún no está en su sitio.
    colocar(js, texto=json.dumps(datos, ensure_ascii=False, indent=2))

    print(f'publicada v{version} ({datos["tamano"]} bytes, sha256 {huella})')
    print(f'con versión en el nombre: {os.path.basename(exe_ver)}')
    return verificar_con_espera()


def verificar_con_espera():
    """Tras publicar: nginx puede servir el archivo anterior (entero) hasta 60 s;
    se repite la verificación hasta que cuadre o pasen ESPERA_VERIFICAR_S."""
    limite = time.monotonic() + ESPERA_VERIFICAR_S
    intento = 1
    while True:
        print(f'--- verificación contra la URL pública (intento {intento}) ---')
        if verificar() == 0:
            return 0
        if time.monotonic() + PAUSA_VERIFICAR_S > limite:
            return 1
        print(f'(nginx puede tardar hasta 60 s en ver el archivo nuevo; reintento en {PAUSA_VERIFICAR_S} s)')
        time.sleep(PAUSA_VERIFICAR_S)
        intento += 1


def main():
    p = argparse.ArgumentParser(description='Publicar o verificar el instalador de Drive Maquita para Windows.')
    sub = p.add_subparsers(dest='comando', required=True)
    sub.add_parser('verificar', help='comprobar que lo declarado, lo del disco y lo que se descarga coinciden')
    pub = sub.add_parser('publicar', help='publicar un Setup nuevo')
    pub.add_argument('exe')
    pub.add_argument('version')
    pub.add_argument('--notas', default='', help='qué trae la versión, en lenguaje de usuario')
    a = p.parse_args()
    sys.exit(verificar() if a.comando == 'verificar' else publicar(a.exe, a.version, a.notas))


if __name__ == '__main__':
    main()
