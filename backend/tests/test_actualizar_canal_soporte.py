"""Canal de soporte largo «estable-X.Y» del actualizador firmado (deploy/actualizar/lib/version.py)."""

import importlib.util
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(RAIZ, "deploy", "actualizar", "lib", "version.py")


@pytest.fixture
def v(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("version_actualizar", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "DISPONIBLE", str(tmp_path / "disponible.json"))
    monkeypatch.setattr(m, "CONFIG", str(tmp_path / "config.json"))
    return m


ETIQUETAS = "v1.10.0 v1.11.0 v1.11.1 v1.11.10 v1.11.2 v1.12.0 v1.13.1 v2.0.0-rc"


def _repo_falso(m, monkeypatch, canal):
    m.guardar_json(m.CONFIG, {"canal": canal, "automatico": True})

    def git(*args, tiempo=300):
        if args[0] == "tag" and args[1] == "-l" and args[2] == "v*":
            return ETIQUETAS.replace(" ", "\n")
        if args[0] == "rev-list":
            return "commit-" + args[-1]
        if args[0] == "tag":
            return "notas"
        if args[0] == "log":
            return "cambio"
        return ""

    monkeypatch.setattr(m, "git", git)
    monkeypatch.setattr(m, "actual", lambda: {"commit": "instalado", "version": "v1.11.1"})
    monkeypatch.setattr(m, "_avanza", lambda a, b: True)
    monkeypatch.setattr(m, "firmada", lambda ref: True)


def test_canal_estable_toma_la_ultima(v, monkeypatch):
    _repo_falso(v, monkeypatch, "estable")
    assert v.buscar()["ref"] == "v1.13.1"


def test_canal_de_soporte_se_queda_en_su_serie(v, monkeypatch):
    _repo_falso(v, monkeypatch, "estable-1.11")
    d = v.buscar()
    assert d["ref"] == "v1.11.10"  # orden numérico, no alfabético; nunca salta a 1.12
    assert d["firmada"] is True


def test_canal_de_soporte_exige_firma(v, monkeypatch):
    _repo_falso(v, monkeypatch, "estable-1.11")
    v.buscar()
    monkeypatch.setattr(v, "firmada", lambda ref: False)
    with pytest.raises(v.ErrorActualizar):
        v.objetivo()


@pytest.mark.parametrize(
    "canal,valido",
    [
        ("estable", True),
        ("estable-1.11", True),
        ("main", True),
        ("estable-1", False),  # parece estable pero no lo es: nunca como rama sin firma
        ("estable-1.x", False),
        ("estable-", False),
        ("../x", False),
    ],
)
def test_validar_config(v, canal, valido):
    if valido:
        assert v.validar_config({"canal": canal})["canal"] == canal
    else:
        with pytest.raises(v.ErrorActualizar):
            v.validar_config({"canal": canal})


def test_canal_firmado(v):
    assert v.canal_firmado("estable") and v.canal_firmado("estable-2.0")
    assert not v.canal_firmado("main") and not v.canal_firmado("estable-1")


@pytest.mark.skipif(not shutil.which("bash"), reason="sin bash")
@pytest.mark.parametrize(
    "script",
    ["deploy/actualizar/publicar-version.sh", "deploy/escala/actualizar-sin-corte.sh"],
)
def test_sintaxis_de_los_scripts(script):
    r = subprocess.run(["bash", "-n", os.path.join(RAIZ, script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not shutil.which("bash"), reason="sin bash")
@pytest.mark.parametrize(
    "rama,version",
    [("estable/1.11", "v1.12.0"), ("estable/x", "v1.11.1"), ("otra", "v1.11.1")],
)
def test_publicar_rechaza_version_fuera_de_la_serie(rama, version):
    """Se comprueba antes de buscar la clave o tocar el repositorio."""
    r = subprocess.run(
        ["bash", os.path.join(RAIZ, "deploy/actualizar/publicar-version.sh"), version],
        capture_output=True,
        text=True,
        env={**os.environ, "RAMA": rama, "CLAVE_FIRMA": "/no/existe"},
    )
    assert r.returncode == 2, r.stdout + r.stderr
