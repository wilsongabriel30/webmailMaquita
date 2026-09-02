# -*- coding: utf-8 -*-
"""
Vista «Compartido conmigo» del Almacén Maquita.
===============================================
Arma la lista que ve una persona en «Compartido conmigo» y traduce las rutas
que salen del núcleo para que el explorador siga navegando dentro del espacio
compartido (ver `permisos_compartidos.py`).

Antes esta vista solo sabía de archivos sueltos: al montarla se descartaba todo
lo que no fuera un archivo con tamaño, así que una CARPETA compartida no salía
nunca y la única forma de verla era el enlace público, en solo lectura.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import logging
import os

from almacen_bd import consultar
from permisos_compartidos import concesiones, ruta_compartida
from seguridad_rutas import RutaInvalida, ruta_fisica

log = logging.getLogger('almacen.compartidos')

# Campos de los items del contrato que llevan una ruta virtual y por tanto hay
# que reescribir cuando la respuesta sale del espacio compartido.
_CAMPOS_RUTA = ('ruta', 'ruta_completa', 'destino')


def reprefijar_item(item: dict, prefijo: str) -> dict:
    """Antepone el prefijo del espacio compartido a las rutas de UN item."""
    if not prefijo or not isinstance(item, dict):
        return item
    for campo in _CAMPOS_RUTA:
        valor = item.get(campo)
        if isinstance(valor, str) and valor.startswith('/'):
            item[campo] = prefijo + ('' if valor == '/' else valor)
    return item


def reprefijar(items, prefijo: str):
    """Igual que `reprefijar_item`, para una lista."""
    if not prefijo:
        return items
    for item in items or []:
        reprefijar_item(item, prefijo)
    return items


def migas(prefijo: str, ruta_efectiva: str, nombre_raiz: str) -> list:
    """Migas de pan del espacio compartido. La primera es «Compartido conmigo»
    para que se vea de dónde viene la carpeta y se pueda volver."""
    camino = [{'nombre': 'Compartido conmigo', 'ruta': '/compartidos'}]
    acumulada = ''
    partes = [p for p in (ruta_efectiva or '/').split('/') if p]
    for indice, parte in enumerate(partes):
        acumulada += '/' + parte
        camino.append({'nombre': parte if indice else (nombre_raiz or parte),
                       'ruta': prefijo + acumulada})
    return camino


def _nombres_de(ids) -> dict:
    """Nombre completo de cada propietario, en una sola consulta."""
    if not ids:
        return {}
    try:
        filas = consultar("""
            SELECT u.id, u.email,
                   COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id IN %s
        """, (tuple(ids),), nomina=True)
        return {f['id']: f for f in filas}
    except Exception as excepcion:
        log.warning('No se pudieron resolver los propietarios: %s', excepcion)
        return {}


def _es_hija(ruta: str, otra: str) -> bool:
    """¿`ruta` cuelga de `otra`? Se usa para no repetir en la lista una
    subcarpeta que ya se ve entrando en la carpeta de arriba."""
    return ruta != otra and ruta.startswith(otra.rstrip('/') + '/')


def listar_para(usuario_id: int) -> list:
    """Items de «Compartido conmigo» de esta persona, listos para el explorador.

    Solo se muestra el nivel MÁS ALTO de cada rama: si a alguien le comparten
    una carpeta y además tres subcarpetas suyas, en la lista aparece la carpeta,
    y las subcarpetas se ven entrando en ella — como en Drive.
    """
    todas = concesiones(usuario_id)
    if not todas:
        return []
    propietarios = _nombres_de({int(c['propietario_id']) for c in todas})
    rutas_por_dueno = {}
    for concesion in todas:
        rutas_por_dueno.setdefault(int(concesion['propietario_id']), []).append(concesion['ruta'])

    items = []
    for concesion in todas:
        dueno = int(concesion['propietario_id'])
        ruta = concesion['ruta']
        if any(_es_hija(ruta, otra) for otra in rutas_por_dueno[dueno]):
            continue   # ya se llega a ella entrando en la carpeta de arriba
        try:
            fisica = ruta_fisica(dueno, ruta)
        except RutaInvalida:
            continue
        if not os.path.exists(fisica):
            continue   # el dueño lo movió o lo borró: no se enseña un fantasma
        es_carpeta = os.path.isdir(fisica)
        info = os.stat(fisica)
        from nucleo_archivos import _id_estable, clasificar, tamano_humano
        from datetime import datetime, timezone
        nombre = ruta.rstrip('/').rsplit('/', 1)[-1] or 'Compartido'
        tipo, extension, mime, icono, es_editable = clasificar(nombre, es_carpeta)
        identificador = _id_estable(dueno, ruta)
        modificado = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat()
        persona = propietarios.get(dueno) or {}
        items.append({
            'id': identificador,
            'file_id': identificador,
            'folder_id': identificador if es_carpeta else None,
            'nombre': nombre,
            'nombre_archivo': nombre,
            # Ruta del ESPACIO COMPARTIDO: al abrirla, el explorador pide
            # /archivos?ruta=/compartido/<dueño>/... y entra de verdad dentro.
            'ruta': ruta_compartida(dueno, ruta),
            'ruta_completa': ruta_compartida(dueno, ruta),
            'ruta_original': ruta,
            'es_carpeta': es_carpeta,
            'tipo': tipo,
            'extension': extension,
            'mime_type': mime,
            'icono': icono,
            'color': None,
            'tamano_bytes': 0 if es_carpeta else info.st_size,
            'tamano_humano': '—' if es_carpeta else tamano_humano(info.st_size),
            'es_editable': es_editable,
            'puede_editar': bool(concesion.get('puede_editar')),
            'permite_descarga': bool(concesion.get('permite_descarga')),
            'es_compartido': True,
            'compartido_id': concesion['id'],
            'token': concesion.get('token'),
            'propietario_id': dueno,
            'propietario_nombre': persona.get('nombre') or f'Usuario {dueno}',
            'propietario_email': persona.get('email') or '',
            'modificado_at': modificado,
            'creado_at': concesion['creado_en'].isoformat() if concesion.get('creado_en') else modificado,
            'tiene_preview': tipo in ('imagen', 'video'),
        })
    return items
