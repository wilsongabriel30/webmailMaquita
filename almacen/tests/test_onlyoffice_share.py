# -*- coding: utf-8 -*-
"""F-07: las capacidades de OnlyOffice de un enlace público mueren con el enlace."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import capacidad_enlace as cap  # noqa: E402

AHORA = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def _share(**cambios):
    base = {"id": 7, "version": 3, "puede_editar": True, "expira_en": None}
    base.update(cambios)
    return base


def test_ligadura_lleva_id_y_version():
    assert cap.ligadura(_share()) == {"s": 7, "sv": 3}
    assert cap.ligadura({"id": 7, "version": None}) == {"s": 7, "sv": 1}
    assert cap.nace_de_enlace({"s": 7}) and not cap.nace_de_enlace({"u": 1})


def test_share_vigente_descarga_y_callback():
    datos = cap.ligadura(_share())
    assert cap.vigente(_share(), datos, "descarga", AHORA)
    assert cap.vigente(_share(), datos, "callback", AHORA)


def test_share_borrado_vencido_o_con_otra_version_no_vale():
    datos = cap.ligadura(_share())
    assert not cap.vigente(None, datos, "descarga", AHORA)
    assert not cap.vigente(_share(expira_en=AHORA - timedelta(minutes=1)), datos, "descarga", AHORA)
    assert cap.vigente(_share(expira_en=AHORA + timedelta(minutes=1)), datos, "descarga", AHORA)
    assert not cap.vigente(_share(version=4), datos, "descarga", AHORA)
    assert not cap.vigente(_share(), {"u": 1}, "descarga", AHORA)  # sin sv → no vale


def test_quitar_la_edicion_mata_el_callback_pero_no_la_lectura():
    datos = cap.ligadura(_share())
    solo_lectura = _share(puede_editar=False)
    assert cap.vigente(solo_lectura, datos, "descarga", AHORA)
    assert not cap.vigente(solo_lectura, datos, "callback", AHORA)


def test_descarga_publica_dura_minutos():
    assert cap.MINUTOS_DESCARGA_PUBLICA <= 60
