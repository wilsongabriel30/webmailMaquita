# -*- coding: utf-8 -*-
"""Guardar ANTES de entregar: que la descarga nunca traiga el archivo viejo.

El Document Server no escribe en disco mientras alguien edita: guarda su propia
copia en memoria y solo llama al `callback` (status 2) cuando se cierra el
último editor. Todo lo que el Drive entrega —descargar un archivo, un ZIP de
varios, un enlace compartido, convertir a PDF— sale del DISCO, así que si el
documento está abierto se entrega **la versión anterior**: el usuario escribe,
descarga y no ve lo que acaba de escribir.

La solución es la misma que usan Google y Nextcloud: pedirle al editor un
guardado forzado (`forcesave` del CommandService) y esperar a que su callback
deje el archivo en disco. Solo entonces se entrega.

Detalles que importan:
  - Solo se pide para los tipos que edita el Document Server; una foto o un
    vídeo se entregan igual de rápido que siempre.
  - Solo si la sala está marcada como ABIERTA (columna `abierto` de
    `onlyoffice_sesion`): un archivo que nadie tiene abierto no paga ni una
    petición al Document Server.
  - Nunca rompe la descarga: si el Document Server no contesta, si no hay nada
    que guardar o si tarda demasiado, se entrega lo que hay en disco, que es
    exactamente lo que pasaba antes de este módulo.

Documentación: 02-MODULOS/NUBE-MAQUITA/ (sesión del 04/09/2026).
"""

import logging
import os
import time

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.onlyoffice.guardado')

# Lo que el Document Server sabe editar: si no está aquí, no hay sala que pedir.
EXTENSIONES = {
    'docx', 'doc', 'odt', 'rtf', 'txt', 'dotx', 'docm',
    'xlsx', 'xls', 'ods', 'csv', 'xltx', 'xlsm',
    'pptx', 'ppt', 'odp', 'potx', 'ppsx',
}

# Cuánto se espera a que el callback deje el archivo en disco. Holgado para una
# hoja grande, pero acotado: pasado el plazo se entrega lo que hay.
ESPERA_MAXIMA = 15.0
PASO_ESPERA = 0.25


# ── estado de la sala ────────────────────────────────────────────────────
_columna_lista = False


def _asegurar_columna():
    """La columna `abierto` sobre la tabla de salas que ya existe."""
    global _columna_lista
    if _columna_lista:
        return
    ejecutar("ALTER TABLE onlyoffice_sesion "
             "ADD COLUMN IF NOT EXISTS abierto BOOLEAN NOT NULL DEFAULT FALSE")
    _columna_lista = True


def marcar_abierto(doc_base: str) -> None:
    """Alguien abrió el documento en el editor. Best-effort: si falla, lo peor
    que pasa es que la descarga no pida el guardado, como antes."""
    try:
        from api_onlyoffice import _asegurar_tabla_sesion
        _asegurar_tabla_sesion()
        _asegurar_columna()
        ejecutar("""
            INSERT INTO onlyoffice_sesion (doc_base, version, abierto)
            VALUES (%s, 1, TRUE)
            ON CONFLICT (doc_base) DO UPDATE SET abierto = TRUE
        """, (doc_base,))
    except Exception as excepcion:
        log.warning('no se pudo marcar la sala abierta (%s): %s', doc_base, excepcion)


def marcar_cerrado(doc_base: str) -> None:
    """Se cerró el último editor (callback 2 o 4): ya no hay nada que forzar."""
    try:
        _asegurar_columna()
        ejecutar("UPDATE onlyoffice_sesion SET abierto = FALSE WHERE doc_base = %s",
                 (doc_base,))
    except Exception as excepcion:
        log.warning('no se pudo marcar la sala cerrada (%s): %s', doc_base, excepcion)


def _sala_abierta(doc_base: str) -> bool:
    try:
        _asegurar_columna()
        filas = consultar("SELECT abierto FROM onlyoffice_sesion WHERE doc_base = %s",
                          (doc_base,))
        return bool(filas and filas[0]['abierto'])
    except Exception as excepcion:
        log.warning('no se pudo leer el estado de la sala (%s): %s', doc_base, excepcion)
        return False


# ── guardado forzado ─────────────────────────────────────────────────────
def _pedir_forcesave(doc_key: str) -> int:
    """Pide el guardado al CommandService. Devuelve el código del Document
    Server: 0 = lo va a guardar · 4 = no hay cambios · el resto, problema."""
    import requests
    from api_onlyoffice import firmar_jwt, url_interna_ds

    cuerpo = {'c': 'forcesave', 'key': doc_key, 'userdata': 'descarga'}
    cuerpo['token'] = firmar_jwt(dict(cuerpo))
    respuesta = requests.post(
        url_interna_ds().rstrip('/') + '/coauthoring/CommandService.ashx',
        json=cuerpo, timeout=(3, 10),
        headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
    respuesta.raise_for_status()
    return int((respuesta.json() or {}).get('error', 5))


def _huella(fisica: str):
    try:
        estado = os.stat(fisica)
        return (estado.st_mtime_ns, estado.st_size)
    except OSError:
        return None


def guardar_si_esta_abierto(usuario: int, ruta: str, fisica: str,
                            espera: float = ESPERA_MAXIMA, forzar: bool = False) -> str:
    """Si el documento está abierto en el editor, pide el guardado y espera a
    que el archivo del disco cambie.

    `forzar=True`: pedirlo aunque la sala no conste como abierta. Lo usa la
    descarga que sale del PROPIO editor (editor-descarga-drive.js): ahí se sabe
    seguro que está abierto, y la marca de la BD podría haberse perdido.

    Devuelve, solo para registro y pruebas: 'no-aplica' (no es un documento del
    editor), 'sin-sesion', 'sin-cambios', 'guardado', 'tiempo' (se agotó la
    espera) o 'error'. NUNCA lanza: la descarga debe seguir pase lo que pase.
    """
    try:
        extension = ruta.rsplit('.', 1)[-1].lower() if '.' in ruta else ''
        if extension not in EXTENSIONES:
            return 'no-aplica'

        from api_onlyoffice import (_base_documento, _version_sesion,
                                    secreto_ds, url_interna_ds)
        if not (secreto_ds() and url_interna_ds()):
            return 'no-aplica'

        # La sala se nombra con la ruta NORMALIZADA, igual que al abrir el
        # editor; si no, la misma hoja daría dos salas distintas.
        from seguridad_rutas import normalizar_ruta_virtual
        ruta = normalizar_ruta_virtual(ruta)

        doc_base = _base_documento(usuario, ruta)
        if not forzar and not _sala_abierta(doc_base):
            return 'sin-sesion'

        import hashlib
        version = _version_sesion(doc_base)
        doc_key = hashlib.sha1(f'{doc_base}:v{version}'.encode()).hexdigest()[:20]

        antes = _huella(fisica)
        inicio = time.monotonic()
        codigo = _pedir_forcesave(doc_key)
        if codigo == 4:
            # El editor está abierto pero no hay nada nuevo que guardar.
            return 'sin-cambios'
        if codigo != 0:
            log.warning('forcesave devolvió error=%s (ruta=%s)', codigo, ruta)
            return 'error'

        # El guardado lo hace el callback: se espera a ver el archivo cambiado.
        limite = inicio + espera
        while time.monotonic() < limite:
            time.sleep(PASO_ESPERA)
            if _huella(fisica) != antes:
                log.info('descarga: guardado forzado de %s en %.1fs',
                         ruta, time.monotonic() - inicio)
                return 'guardado'
        log.warning('descarga: el guardado forzado de %s no llegó en %.0fs;'
                    ' se entrega el archivo del disco', ruta, espera)
        return 'tiempo'
    except Exception as excepcion:
        log.warning('descarga: no se pudo forzar el guardado de %s: %s', ruta, excepcion)
        return 'error'


def guardar_lote(usuario: int, pares, presupuesto: float = 45.0) -> dict:
    """Igual que `guardar_si_esta_abierto`, para varios archivos a la vez (ZIP).

    `pares` es [(ruta_virtual, ruta_fisica)]. Se respeta un presupuesto TOTAL de
    tiempo: un ZIP de cien archivos no puede tener a la persona esperando por
    los que alguien dejó abiertos. Lo que no entre en el presupuesto se entrega
    como estaba en disco, igual que antes de este módulo.
    """
    inicio = time.monotonic()
    resultados = {}
    for ruta, fisica in pares:
        extension = ruta.rsplit('.', 1)[-1].lower() if '.' in ruta else ''
        if extension not in EXTENSIONES:
            continue
        restante = presupuesto - (time.monotonic() - inicio)
        if restante <= 1.0:
            log.warning('ZIP: se agotó el presupuesto de guardado forzado;'
                        ' el resto se entrega del disco')
            break
        resultados[ruta] = guardar_si_esta_abierto(
            usuario, ruta, fisica, espera=min(ESPERA_MAXIMA, restante))
    return resultados
