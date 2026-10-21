"""Libreta de la organización de Z-Push: qué buzones entran y cómo se parte el nombre."""
import importlib.machinery
import importlib.util
import os

RUTA = os.path.join(os.path.dirname(__file__), "../../deploy/z-push/directorio/maquita-zpush-directorio")
_cargador = importlib.machinery.SourceFileLoader("maquita_zpush_directorio", RUTA)
_spec = importlib.util.spec_from_loader("maquita_zpush_directorio", _cargador)
gen = importlib.util.module_from_spec(_spec)
_cargador.exec_module(gen)


def test_agrupa_por_dominio_y_omite_direcciones_de_sistema():
    filas = [
        ["ana@example.org", "Ana María Pérez Gómez", "example.org"],
        ["noreply@example.org", "noreply", "example.org"],
        ["postmaster@example.org", "", "example.org"],
        ["info@example.org", "info", "example.org"],
        ["luis@example.com", "Luis Vera", "example.com"],
        ["raro@example.com", "Raro", "EXAMPLE..com"],
    ]
    d = gen.directorios(filas)
    assert sorted(d) == ["example.com", "example.org"]
    assert [p["correo"] for p in d["example.org"]] == ["ana@example.org", "info@example.org"]
    ana = d["example.org"][0]
    assert (ana["nombres"], ana["apellidos"]) == ("Ana María", "Pérez Gómez")
    assert d["example.org"][1]["nombre"] == ""  # «info» como nombre no ayuda
    assert d["example.com"][0]["apellidos"] == "Vera"


def test_no_publica_telefonos_ni_otros_datos():
    d = gen.directorios([["ana@example.org", "Ana Pérez", "example.org"]])
    assert set(d["example.org"][0]) == {"correo", "nombre", "nombres", "apellidos"}
