"""Volver de una rama de prueba al canal: historias separadas, contenido posterior (informe de Andes, 15/11/2026)."""

import importlib.util
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(RAIZ, "deploy", "actualizar", "lib", "version.py")
HUMO = os.path.join(RAIZ, "deploy", "pruebas-humo", "sesion_prueba.py")


@pytest.fixture
def v(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("version_actualizar_canal", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "DISPONIBLE", str(tmp_path / "disponible.json"))
    monkeypatch.setattr(m, "CONFIG", str(tmp_path / "config.json"))
    return m


def _repo(m, monkeypatch, contenidos, fechas):
    """contenidos: pares (ancestro, descendiente) que existen; fechas: commit -> segundos."""
    m.guardar_json(m.CONFIG, {"canal": "main", "automatico": False})

    def git(*args, tiempo=300):
        if args[0] == "rev-parse":
            return "canal"
        if args[0] == "show":
            return str(fechas[args[-1]])
        if args[0] == "log":
            return "un cambio"
        return ""

    monkeypatch.setattr(m, "git", git)
    monkeypatch.setattr(m, "actual", lambda: {"commit": "instalado", "version": "v1"})
    monkeypatch.setattr(m, "_avanza", lambda a, b: (a, b) in contenidos)


def test_historia_lineal_sigue_igual(v, monkeypatch):
    _repo(v, monkeypatch, {("instalado", "canal")}, {"instalado": 10, "canal": 20})
    d = v.buscar()
    assert d["nueva"] is True and d["cambio_de_canal"] is False


def test_de_rama_de_prueba_al_canal_se_ofrece(v, monkeypatch):
    _repo(v, monkeypatch, set(), {"instalado": 10, "canal": 20})
    d = v.buscar()
    assert d["nueva"] is True and d["cambio_de_canal"] is True


def test_nunca_se_vuelve_a_un_punto_anterior_de_la_misma_historia(v, monkeypatch):
    _repo(v, monkeypatch, {("canal", "instalado")}, {"instalado": 20, "canal": 10})
    d = v.buscar()
    assert d["nueva"] is False and d["cambio_de_canal"] is False


def test_historias_separadas_pero_canal_mas_viejo_no_se_ofrece(v, monkeypatch):
    _repo(v, monkeypatch, set(), {"instalado": 30, "canal": 20})
    assert v.buscar()["nueva"] is False


def test_la_sesion_de_pruebas_respeta_humo_conectar():
    codigo = open(HUMO, encoding="utf-8").read()
    assert "urllib.request.urlopen" not in codigo and "BASE +" not in codigo
    assert codigo.count("_pedir(") == 3
