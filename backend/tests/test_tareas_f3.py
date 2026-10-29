"""Tareas al estilo To Do, F3 (30/10/2026): repetición, búsqueda y adjuntos.

- La regla de repetición se valida y se guarda en forma canónica; la personalizada admite intervalo,
  unidad y días de la semana.
- La siguiente fecha respeta fin de mes, años bisiestos y los días laborables.
- La búsqueda trata %, _ y \\ como texto.
- Un adjunto vacío, de más de 25 MB o con extensión peligrosa se rechaza antes de tocar la base.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.tasks import adjuntos, repeticion, vistas
from app.tasks.schemas import CardCreate, CardUpdate


def _d(a, m, d):
    return datetime(a, m, d, tzinfo=timezone.utc)


def test_reglas_validas_y_canonicas():
    for r in repeticion.SIMPLES:
        assert repeticion.normalizar(r) == r
    assert repeticion.normalizar(" ") is None
    assert repeticion.normalizar(None) is None
    assert repeticion.normalizar("cada:2:semana:4,0,4") == "cada:2:semana:0,4"
    assert repeticion.normalizar("cada:3:mes") == "cada:3:mes"
    for mala in (
        "cada:0:dia",
        "cada:2:mes:1",
        "hourly",
        "cada:2:semana:7",
        "cada:1000:dia",
        "cada:x:dia",
    ):
        with pytest.raises(ValueError):
            repeticion.normalizar(mala)


def test_esquemas_validan_la_regla():
    assert CardUpdate(recurrence="cada:1:semana:2,1").recurrence == "cada:1:semana:1,2"
    assert CardUpdate(recurrence="").recurrence is None
    assert CardCreate(title="x", recurrence="weekly").recurrence == "weekly"
    with pytest.raises(ValidationError):
        CardUpdate(recurrence="nunca")


def test_siguiente_fecha():
    s = repeticion.siguiente
    assert s("daily", _d(2026, 10, 30)) == _d(2026, 10, 31)
    assert s("weekdays", _d(2026, 10, 30)) == _d(2026, 11, 2)  # viernes -> lunes
    assert s("weekly", _d(2026, 10, 30)) == _d(2026, 11, 6)
    assert s("monthly", _d(2026, 1, 31)) == _d(2026, 2, 28)
    assert s("yearly", _d(2028, 2, 29)) == _d(2029, 2, 28)
    assert s("monthly", _d(2026, 12, 15)) == _d(2027, 1, 15)
    assert s("cada:3:dia", _d(2026, 10, 30)) == _d(2026, 11, 2)
    assert s("cada:2:semana", _d(2026, 10, 30)) == _d(2026, 11, 13)
    assert s("cada:2:mes", _d(2026, 12, 31)) == _d(2027, 2, 28)
    assert s("cada:2:anio", _d(2026, 3, 1)) == _d(2028, 3, 1)
    # Lunes y jueves cada 2 semanas: del lunes 26/10 al jueves 29/10; del jueves al lunes de dentro de 2 semanas.
    assert s("cada:2:semana:0,3", _d(2026, 10, 26)) == _d(2026, 10, 29)
    assert s("cada:2:semana:0,3", _d(2026, 10, 29)) == _d(2026, 11, 9)
    assert s("cada:1:semana:0,3", _d(2026, 10, 29)) == _d(2026, 11, 2)


def test_busqueda_toma_comodines_como_texto():
    assert vistas._patron("50%_a\\b") == "%50\\%\\_a\\\\b%"


def test_nombre_de_archivo_sin_rutas_ni_controles():
    assert adjuntos.nombre_limpio("../../etc/passwd") == "passwd"
    assert adjuntos.nombre_limpio("C:\\Users\\x\\informe.pdf") == "informe.pdf"
    assert adjuntos.nombre_limpio("a\x00b\nc.txt") == "a_b_c.txt"
    assert adjuntos.nombre_limpio("  ") == "archivo"
    assert len(adjuntos.nombre_limpio("x" * 500 + ".pdf")) == 200


class _SinBase:
    def __getattr__(self, nombre):
        raise AssertionError("no debía tocar la base")


def _guardar(nombre, contenido):
    return asyncio.run(
        adjuntos.guardar(_SinBase(), "ana@x", "c1", nombre, "text/plain", contenido)
    )


def test_adjunto_vacio_o_grande_se_rechaza():
    with pytest.raises(adjuntos.Rechazado) as e:
        _guardar("a.txt", b"")
    assert e.value.status == 400
    with pytest.raises(adjuntos.Rechazado) as e:
        _guardar("a.txt", b"x" * (adjuntos.MAX_TAMANO + 1))
    assert e.value.status == 413


def test_extension_peligrosa_se_rechaza():
    with pytest.raises(HTTPException) as e:
        _guardar("factura.pdf.exe", b"MZ")
    assert e.value.status_code == 422
