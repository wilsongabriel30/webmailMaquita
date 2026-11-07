"""Bienvenida tras una migración: a quién y cuándo se muestra (03/11/2026)."""

from datetime import datetime, timezone

from app.bienvenida import router as bienvenida
from app.config import get_settings


def _configurar(monkeypatch, dominios, desde):
    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "bienvenida_dominios", dominios)
    monkeypatch.setattr(ajustes, "bienvenida_desde", desde)


def test_apagada_sin_dominios(monkeypatch):
    _configurar(monkeypatch, "", "2026-11-04T16:00:00-05:00")
    assert not bienvenida.corresponde(
        "ana@example.org", datetime(2026, 11, 5, tzinfo=timezone.utc)
    )


def test_solo_dominios_configurados_y_despues_del_cambio(monkeypatch):
    _configurar(
        monkeypatch,
        "example.org, example.net",
        "2026-11-04T16:00:00-05:00",
    )
    antes = datetime(2026, 11, 4, 20, 59, tzinfo=timezone.utc)  # 15:59 en Ecuador
    despues = datetime(2026, 11, 4, 21, 0, tzinfo=timezone.utc)  # 16:00 en Ecuador
    assert not bienvenida.corresponde("ana@example.org", antes)
    assert bienvenida.corresponde("ana@example.org", despues)
    assert bienvenida.corresponde("Luis@Example.NET", despues)
    assert not bienvenida.corresponde("ana@otro.example", despues)


def test_fecha_invalida_no_muestra(monkeypatch):
    _configurar(monkeypatch, "example.org", "mañana")
    assert not bienvenida.corresponde(
        "ana@example.org", datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
