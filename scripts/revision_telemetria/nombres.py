"""Traduce un correo a la persona que lo usa, para sugerir a quién preguntar."""
import json

from .config import ARCHIVO_NOMBRES, CUENTAS_PRUEBA

_NOMBRES = None


def _cargar():
    global _NOMBRES
    if _NOMBRES is None:
        try:
            with open(ARCHIVO_NOMBRES, encoding='utf-8') as f:
                _NOMBRES = json.load(f)
        except (OSError, ValueError):
            _NOMBRES = {}
    return _NOMBRES


def persona(correo):
    """'correo (Nombre Apellido)' o solo el correo si no se conoce."""
    if not correo:
        return '(sin usuario identificado)'
    nombre = _cargar().get(correo.lower())
    etiqueta = f'{correo} ({nombre})' if nombre else correo
    if correo.lower() in CUENTAS_PRUEBA:
        etiqueta += ' [cuenta de pruebas]'
    return etiqueta


def a_quien_preguntar(correo):
    if not correo:
        return 'No hay usuario asociado: revisar con el equipo de desarrollo del webmail.'
    nombre = _cargar().get(correo.lower())
    if nombre:
        return f'Preguntar a {nombre} ({correo}).'
    return f'Preguntar al usuario {correo} (nombre no registrado en nombres.json).'
