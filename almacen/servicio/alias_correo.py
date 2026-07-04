# -*- coding: utf-8 -*-
"""
Alias de correo del Almacén.
============================
Una misma persona puede tener VARIOS buzones (ej: usuario@dominio.org y
usuario@dominio.com.ec). Este módulo hace que todos apunten a UNA sola
identidad del Almacén: el correo CANÓNICO (el principal de la persona,
el que está en el directorio de usuarios).

Funciona igual en los dos modos de directorio:
- modo `nomina`: el alias se traduce al canónico ANTES de buscarlo en la
  columna email del directorio central.
- modo `local`: el alias se traduce al canónico ANTES de buscar/crear el
  usuario local → ambos buzones comparten el mismo almacén.

La tabla vive en la BD del Almacén (se crea sola). Se administra con los
endpoints /api/almacen/admin/alias-correo (solo administradores) o con SQL
directo. Resolución de UN solo nivel: el canónico de un alias no puede ser
a su vez un alias (se valida al crear).
"""
import logging
import re
import time

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.alias')

_CORREO_VALIDO = re.compile(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')

_TTL_CACHE_SEG = 60       # los cambios de alias aplican solos en <=1 min en todos los workers
_cache_alias: dict = {}   # alias -> (canonico, momento)


def asegurar_tabla_alias() -> None:
    """Crea la tabla de alias (idempotente; se llama al arrancar)."""
    ejecutar("""
        CREATE TABLE IF NOT EXISTS alias_correo (
            alias TEXT PRIMARY KEY,
            canonico TEXT NOT NULL,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)


def resolver_alias(correo: str) -> str:
    """Correo canónico de un buzón. Si no tiene alias registrado, devuelve el
    mismo correo. Un solo nivel de resolución, insensible a mayúsculas."""
    correo = (correo or '').strip().lower()
    en_cache = _cache_alias.get(correo)
    if en_cache and time.time() - en_cache[1] < _TTL_CACHE_SEG:
        return en_cache[0]
    filas = consultar('SELECT canonico FROM alias_correo WHERE LOWER(alias) = %s', (correo,))
    canonico = filas[0]['canonico'].strip().lower() if filas else correo
    _cache_alias[correo] = (canonico, time.time())
    return canonico


def listar_alias() -> list:
    filas = consultar('SELECT alias, canonico, creado_en FROM alias_correo ORDER BY canonico, alias')
    return [dict(f) for f in filas]


def crear_alias(alias: str, canonico: str) -> tuple:
    """Registra un alias. Devuelve (ok, mensaje). Valida formato, que no sea
    un auto-alias y que no se formen cadenas (el canónico no puede ser alias)."""
    alias = (alias or '').strip().lower()
    canonico = (canonico or '').strip().lower()
    if not _CORREO_VALIDO.match(alias) or not _CORREO_VALIDO.match(canonico):
        return False, 'Formato de correo inválido'
    if alias == canonico:
        return False, 'El alias y el canónico no pueden ser iguales'
    if consultar('SELECT 1 FROM alias_correo WHERE LOWER(alias) = %s', (canonico,)):
        return False, f'"{canonico}" ya es un alias de otro correo (no se permiten cadenas)'
    if consultar('SELECT 1 FROM alias_correo WHERE LOWER(canonico) = %s', (alias,)):
        return False, f'"{alias}" es el canónico de otros alias (no se permiten cadenas)'
    ejecutar("""
        INSERT INTO alias_correo (alias, canonico) VALUES (%s, %s)
        ON CONFLICT (alias) DO UPDATE SET canonico = EXCLUDED.canonico
    """, (alias, canonico))
    _cache_alias.clear()
    log.info('Alias registrado: %s -> %s', alias, canonico)
    return True, 'Alias registrado'


def eliminar_alias(alias: str) -> bool:
    alias = (alias or '').strip().lower()
    existe = consultar('SELECT 1 FROM alias_correo WHERE LOWER(alias) = %s', (alias,))
    if not existe:
        return False
    ejecutar('DELETE FROM alias_correo WHERE LOWER(alias) = %s', (alias,))
    _cache_alias.clear()
    log.info('Alias eliminado: %s', alias)
    return True
