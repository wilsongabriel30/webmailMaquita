"""R-04: un motor OBLIGATORIO caído nunca produce «clean» (PoC de cierre)."""

from app.safeattach import pipeline
from app.safeattach.analyzers.clamav import ClamAV


def _sin_docker(monkeypatch):
    # La detonación no aplica en las pruebas: se deja fuera del pipeline.
    monkeypatch.setattr(
        pipeline,
        "ANALYZERS",
        [a for a in pipeline.ANALYZERS if a.name != "docker_sandbox"],
    )


def test_clamav_que_lanza_excepcion_es_fallo_cerrado(monkeypatch):
    _sin_docker(monkeypatch)

    def caido(self, path, content, report):
        raise RuntimeError("clamd no responde (simulado)")

    monkeypatch.setattr(ClamAV, "analyze", caido)
    rep = pipeline.scan(b"hola", "nota.txt", "text/plain").to_dict()
    assert rep["result"] == "suspicious"
    assert rep["errors"] == ["clamav"]
    assert any(t["engine"] == "clamav" for t in rep["threats"])


def test_clamav_no_disponible_es_fallo_cerrado(monkeypatch):
    _sin_docker(monkeypatch)

    def no_disponible(self, path, content, report):
        report.engines["clamav"] = "no disponible"

    monkeypatch.setattr(ClamAV, "analyze", no_disponible)
    rep = pipeline.scan(b"hola", "nota.txt", "text/plain").to_dict()
    assert rep["result"] == "suspicious" and rep["errors"] == ["clamav"]


def test_clamav_sano_y_sin_hallazgos_es_limpio(monkeypatch):
    _sin_docker(monkeypatch)

    def sano(self, path, content, report):
        report.engines["clamav"] = "ok"

    monkeypatch.setattr(ClamAV, "analyze", sano)
    rep = pipeline.scan(b"hola", "nota.txt", "text/plain").to_dict()
    assert rep["result"] == "clean" and rep["errors"] == []
