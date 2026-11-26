# -*- coding: utf-8 -*-
"""Vigilante de guardados que OnlyOffice no pudo entregar al Drive (25/11/2026).

PROBLEMA QUE RESUELVE
    Cuando el Document Server cierra un documento y el Drive no acepta el
    guardado (callback con error, Drive caído, URL rechazada…), el servidor de
    documentos guarda el resultado final en su zona «forgotten» y no avisa a
    nadie. Entre el 13 y el 31/08/2026 quedaron así 193 guardados rechazados y
    el trabajo de, al menos, «Cuaderno de campo.docx» nunca llegó al Drive.

QUÉ HACE (cada 10 min, cron /etc/cron.d/almacen-vigilante-olvidados)
    1. Pide al CommandService la lista de documentos olvidados.
    2. Por cada clave que no conocía: descarga el archivo a
       /home/sistemas/almacen-maquita/rescate-onlyoffice-olvidados/<fecha>_<clave>/,
       identifica a qué archivo del Drive pertenece (sala de onlyoffice_sesion) y
       avisa a Tecnología por correo.
    3. NUNCA borra nada del Document Server ni del Drive. Recuperar es una
       decisión humana: comparar con el archivo vivo y restaurar a mano.

Si el Document Server no responde, lo anota y avisa (una vez cada 30 min).
"""
import datetime
import hashlib
import io
import json
import logging
import os
import sys

SERVICIO = '/home/sistemas/almacen-maquita/servicio'
sys.path.insert(0, SERVICIO)

import requests  # noqa: E402

from almacen_bd import consultar  # noqa: E402
from api_onlyoffice import firmar_jwt, url_interna_ds  # noqa: E402
import limites_editor  # noqa: E402

RESCATE = '/home/sistemas/almacen-maquita/rescate-onlyoffice-olvidados'
CONOCIDOS = os.path.join(RESCATE, 'claves-conocidas.txt')
MANIFIESTO = os.path.join(RESCATE, 'MANIFIESTO.tsv')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('vigilante-olvidados')


def _comando(cuerpo: dict) -> dict:
    cuerpo = dict(cuerpo)
    cuerpo['token'] = firmar_jwt(dict(cuerpo))
    respuesta = requests.post(
        url_interna_ds().rstrip('/') + '/coauthoring/CommandService.ashx',
        json=cuerpo, timeout=(5, 30),
        headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
    respuesta.raise_for_status()
    return respuesta.json() or {}


def _conocidas() -> set:
    try:
        with io.open(CONOCIDOS, encoding='utf-8') as archivo:
            return {linea.strip() for linea in archivo if linea.strip()}
    except FileNotFoundError:
        return set()


def _anotar_conocida(clave: str) -> None:
    with io.open(CONOCIDOS, 'a', encoding='utf-8') as archivo:
        archivo.write(clave + '\n')


def _sala_de(clave: str):
    """(doc_base, versión) cuya key es `clave`, o None (otros editores: PDF, correo)."""
    for fila in consultar('SELECT doc_base, version FROM onlyoffice_sesion'):
        for version in range(1, int(fila['version']) + 3):
            calculada = hashlib.sha1(f"{fila['doc_base']}:v{version}".encode()).hexdigest()[:20]
            if calculada == clave:
                return fila['doc_base'], version
    return None


def _rescatar(clave: str) -> None:
    datos = _comando({'c': 'getForgotten', 'key': clave})
    url = datos.get('url')
    if datos.get('error') != 0 or not url:
        raise RuntimeError(f'getForgotten sin URL: {datos}')
    nombre = os.path.basename(url.split('?', 1)[0]) or 'output'
    carpeta = os.path.join(RESCATE, datetime.date.today().strftime('%Y%m%d') + '_' + clave)
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, nombre)
    contenido = requests.get(url, timeout=(5, 300)).content
    with io.open(destino, 'wb') as archivo:
        archivo.write(contenido)
    sala = _sala_de(clave)
    huella = hashlib.sha256(contenido).hexdigest()
    with io.open(MANIFIESTO, 'a', encoding='utf-8') as archivo:
        archivo.write('\t'.join([datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), clave,
                                 sala[0] if sala else '(sin sala del Drive)',
                                 str(sala[1]) if sala else '-', str(len(contenido)), huella,
                                 destino]) + '\n')
    _anotar_conocida(clave)
    limites_editor.avisar_tecnologia(
        'Guardado de OnlyOffice NO entregado al Drive (rescatado)',
        f'Clave: {clave}\nArchivo del Drive: {sala[0] if sala else "no identificado (otro editor)"}\n'
        f'Copia rescatada: {destino} ({len(contenido)} bytes, sha256 {huella})\n'
        'Comparar con el archivo vivo y restaurar a mano si lleva trabajo que falta. '
        'No se ha borrado nada del Document Server.')
    log.info('rescatado %s -> %s (%s)', clave, destino, sala)


def main() -> int:
    os.makedirs(RESCATE, exist_ok=True)
    try:
        lista = _comando({'c': 'getForgottenList'})
    except Exception as excepcion:
        limites_editor.avisar_tecnologia('Vigilante de olvidados: el Document Server no responde',
                                         str(excepcion))
        return 1
    if lista.get('error') != 0:
        limites_editor.avisar_tecnologia('Vigilante de olvidados: respuesta inesperada', json.dumps(lista))
        return 1
    conocidas = _conocidas()
    nuevas = [clave for clave in lista.get('keys') or [] if clave not in conocidas]
    fallos = 0
    for clave in nuevas:
        try:
            _rescatar(clave)
        except Exception as excepcion:
            fallos += 1
            limites_editor.avisar_tecnologia('Vigilante de olvidados: no se pudo rescatar',
                                             f'{clave}: {excepcion}')
    log.info('olvidados=%d nuevos=%d fallos=%d', len(lista.get('keys') or []), len(nuevas), fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
