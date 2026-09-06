# -*- coding: utf-8 -*-
"""A-13: los nombres de archivos y carpetas no admiten marcas de HTML ni control."""
import os
import sys

# la configuración exige la clave de sesión al importar; aquí no hay servicio
os.environ.setdefault("ALMACEN_CLAVE_SESION", "clave-de-pruebas-del-almacen-2026")  # gitleaks:allow

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
from seguridad_rutas import nombre_valido  # noqa: E402


def test_nombres_normales_pasan():
    for n in ("Informe 2026.pdf", "fotos", "año-nuevo (1).jpg", "ñandú & cía.txt", "a.b.c"):
        assert nombre_valido(n), n


def test_nombres_peligrosos_no_pasan():
    for n in ("<img src=x onerror=alert(1)>", "a<b", "x>y", 'co"mi"llas', "apos'trofe", "barra\\x",
              "con/barra", ".", "..", "", "   ", "tab\tulado", "nul\x00", "x" * 256):
        assert not nombre_valido(n), repr(n)
