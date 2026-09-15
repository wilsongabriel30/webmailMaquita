"""Huella del archivo que conoce la sala de OnlyOffice (14/09/2026).

PROBLEMA QUE RESUELVE
    El Document Server guarda su propia copia de cada documento y la reconoce
    por la `key`. La key es estable por ruta (sala de co-edición) y solo cambia
    cuando se cierra una sesión de edición o alguien llama a `invalidar_cache`.
    Pero un archivo cambia por muchas vías que no pasan por el editor: subir
    otra versión con el mismo nombre, borrar y volver a subir, renombrar o mover
    otro archivo a esa ruta, restaurar una versión o la papelera, el disco
    WebDAV, la app de escritorio… En todos esos casos el editor seguía
    enseñando la copia anterior, y quien guardaba desde ella pisaba lo subido.
    Caso real: unidad 13 «08  Proyectos», «Ingresos proyectos.xlsx».

CÓMO
    Tras cada guardado del editor se anota la huella del archivo del disco
    (mtime en ns + tamaño + inodo). Al abrir, si la huella del disco ya no es la
    anotada, el archivo cambió por fuera: se sube la versión de la sala para
    que el Document Server lo descargue de nuevo. Una sola comprobación en la
    apertura cubre todas las vías de escritura, también las que se añadan.

    La primera vez que se ve una sala (sin huella anotada) solo se anota: no se
    renueva, para no partir en dos las salas que ya están abiertas.

No falla nunca hacia fuera: si algo va mal, el editor abre como antes.
"""

import logging
import os

from almacen_bd import consultar, ejecutar

log = logging.getLogger(__name__)

_columna_lista = False


def _asegurar_columna():
    global _columna_lista
    if _columna_lista:
        return
    ejecutar("ALTER TABLE onlyoffice_sesion ADD COLUMN IF NOT EXISTS huella TEXT")
    _columna_lista = True


def huella_de(fisica: str) -> str:
    estado = os.stat(fisica)
    return f'{estado.st_mtime_ns}:{estado.st_size}:{estado.st_ino}'


def registrar(doc_base: str, fisica: str) -> None:
    """Anota la huella actual del archivo como la que conoce la sala.
    Llamar justo después de que el editor guarde."""
    try:
        _asegurar_columna()
        ejecutar("""
            INSERT INTO onlyoffice_sesion (doc_base, version, huella) VALUES (%s, 1, %s)
            ON CONFLICT (doc_base) DO UPDATE SET huella = EXCLUDED.huella
        """, (doc_base, huella_de(fisica)))
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo registrar la huella de %s: %s', doc_base, excepcion)


def comprobar(doc_base: str, fisica: str) -> bool:
    """Antes de calcular la key: si el archivo cambió por fuera del editor,
    sube la versión de la sala. Devuelve True si la renovó."""
    try:
        _asegurar_columna()
        actual = huella_de(fisica)
        filas = consultar("SELECT huella FROM onlyoffice_sesion WHERE doc_base = %s",
                          (doc_base,))
        anotada = filas[0]['huella'] if filas else None
        if anotada == actual:
            return False
        if anotada is None:
            registrar(doc_base, fisica)
            return False
        ejecutar("""
            UPDATE onlyoffice_sesion
            SET version = version + 1, huella = %s, actualizado = NOW()
            WHERE doc_base = %s
        """, (actual, doc_base))
        log.info('OnlyOffice: archivo cambiado por fuera del editor, sala renovada (%s)', doc_base)
        return True
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo comprobar la huella de %s: %s', doc_base, excepcion)
        return False
