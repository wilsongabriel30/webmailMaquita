"""«Programados»: fechas válidas y forma de la lista."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.mail.routers import programados as p


def test_fecha_futura_acepta_iso_con_zona_y_z():
    futura = datetime.now(timezone.utc) + timedelta(hours=2)
    assert p.fecha_futura(futura.isoformat()) == futura
    assert (
        abs(
            (
                p.fecha_futura(futura.strftime("%Y-%m-%dT%H:%M:%S.000Z")) - futura
            ).total_seconds()
        )
        < 1
    )


@pytest.mark.parametrize("mala", ["", "ayer", "2020-01-01T10:00:00Z"])
def test_fecha_futura_rechaza_pasadas_o_invalidas(mala):
    with pytest.raises(HTTPException) as e:
        p.fecha_futura(mala)
    assert e.value.status_code == 400


def test_resumen_convierte_listas_y_fechas():
    ahora = datetime(2026, 11, 11, 22, 0, tzinfo=timezone.utc)
    r = p._resumen(
        {
            "id": 4,
            "to_list": '["a@x.co"]',
            "cc_list": [],
            "bcc_list": None,
            "subject": None,
            "scheduled_at": ahora,
            "status": "pending",
            "created_at": None,
        }
    )
    assert (
        r["to"] == ["a@x.co"]
        and r["cc"] == []
        and r["bcc"] == []
        and r["subject"] == ""
    )
    assert r["scheduled_at"] == "2026-11-11T22:00:00+00:00" and r["created_at"] is None
