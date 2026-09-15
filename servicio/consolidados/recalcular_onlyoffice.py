#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recalcula las fórmulas de un .xlsx con el propio Document Server de OnlyOffice.

Por qué OnlyOffice y no LibreOffice. `openpyxl` escribe las fórmulas pero
descarta su resultado guardado, y los totales de cabecera de los consolidados
quedaban en blanco. LibreOffice sí los recuperaba, pero de paso convertía el
texto `#REF!` en la fórmula `=#ref!` (200 celdas) y perdía anchos de columna,
así que se descartó. El Document Server es el **mismo motor que genera los
xlsx** cuando alguien guarda desde el editor del Drive: lo que produzca aquí es
exactamente lo que produciría al guardar a mano.

Cómo. El Document Server no lee del disco: descarga el archivo por HTTP. Se
levanta un servidor efímero que sirve SOLO ese archivo, bajo una ruta con un
componente aleatorio, y se apaga en cuanto termina la conversión.

Nunca escribe sobre el original: devuelve un archivo nuevo.
"""
import http.server
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import uuid

import requests

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import api_onlyoffice as oo  # noqa: E402

TIEMPO_MAXIMO = 300
PUERTO_DESDE = 8400


def _puerto_libre():
    for puerto in range(PUERTO_DESDE, PUERTO_DESDE + 60):
        with socket.socket() as prueba:
            if prueba.connect_ex(('127.0.0.1', puerto)) != 0:
                return puerto
    raise RuntimeError('no hay puertos libres para el servidor temporal')


class _Servidor(threading.Thread):
    """Sirve un único archivo, en una única ruta, mientras dura la conversión."""

    def __init__(self, carpeta, puerto):
        super().__init__(daemon=True)
        self.puerto = puerto
        manejador = http.server.SimpleHTTPRequestHandler

        class Silencioso(manejador):
            def log_message(self, *_):
                pass

        self.httpd = http.server.ThreadingHTTPServer(
            ('0.0.0.0', puerto),
            lambda *args: Silencioso(*args, directory=carpeta))

    def run(self):
        self.httpd.serve_forever()

    def parar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _ip_local():
    """IP por la que el Document Server puede volver a hablarnos."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
        sonda.connect(('193.16.0.211', 80))
        return sonda.getsockname()[0]


def recalcular(ruta_origen, ruta_destino):
    """Calcula las fórmulas de `ruta_origen` y deja el resultado en `ruta_destino`.

    Devuelve (True, '') o (False, motivo). No lanza: si falla, quien llama debe
    poder seguir con el archivo sin recalcular.
    """
    carpeta = tempfile.mkdtemp(prefix='recalc-oo-')
    servidor = None
    try:
        nombre = '%s.xlsx' % uuid.uuid4().hex
        shutil.copy2(ruta_origen, os.path.join(carpeta, nombre))

        puerto = _puerto_libre()
        servidor = _Servidor(carpeta, puerto)
        servidor.start()
        time.sleep(0.3)

        url_archivo = 'http://%s:%d/%s' % (_ip_local(), puerto, nombre)
        peticion = {
            'async': False,
            'filetype': 'xlsx',
            'outputtype': 'xlsx',
            'key': uuid.uuid4().hex,
            'title': os.path.basename(ruta_origen),
            'url': url_archivo,
        }
        peticion['token'] = oo.firmar_jwt(peticion)
        cabeceras = {
            'Authorization': 'Bearer %s' % oo.firmar_jwt({'payload': peticion}),
            'Accept': 'application/json',
        }

        respuesta = requests.post('%s/ConvertService.ashx' % oo.url_interna_ds(),
                                  json=peticion, headers=cabeceras,
                                  timeout=TIEMPO_MAXIMO)
        respuesta.raise_for_status()
        datos = respuesta.json()

        if datos.get('error'):
            return False, 'el Document Server devolvió error %s' % datos['error']
        if not datos.get('endConvert') or not datos.get('fileUrl'):
            return False, 'conversión incompleta: %s' % str(datos)[:150]

        descarga = requests.get(datos['fileUrl'], timeout=TIEMPO_MAXIMO)
        descarga.raise_for_status()
        with open(ruta_destino, 'wb') as salida:
            salida.write(descarga.content)

        if os.path.getsize(ruta_destino) == 0:
            return False, 'el archivo recalculado salió vacío'
        return True, ''
    except Exception as excepcion:
        return False, str(excepcion)[:200]
    finally:
        if servidor:
            servidor.parar()
        shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit('uso: recalcular_onlyoffice.py <origen.xlsx> <destino.xlsx>')
    ok, motivo = recalcular(sys.argv[1], sys.argv[2])
    print('OK' if ok else 'FALLO: %s' % motivo)
    sys.exit(0 if ok else 1)
