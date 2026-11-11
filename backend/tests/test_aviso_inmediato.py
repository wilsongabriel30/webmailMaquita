"""Aviso inmediato de correo nuevo: despertador del sondeo y punto interno solo local."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.websocket import aviso_entrega, despertador


async def test_esperar_respeta_el_tope_y_despierta_antes(monkeypatch):
    monkeypatch.setattr(despertador, "RETRASOS_S", (0.02, 0.05))
    assert await despertador.esperar("ana@x.test", 0.05) is False
    tarea = asyncio.create_task(despertador.esperar("ana@x.test", 5))
    await asyncio.sleep(0)
    despertador.despertar("ana@x.test")
    assert await asyncio.wait_for(tarea, 1) is True
    # La segunda vuelta (por si la entrega tardó) también llega.
    assert await despertador.esperar("ana@x.test", 1) is True
    despertador.olvidar("ana@x.test")
    despertador.despertar("nadie@x.test")  # sin sondeo en este proceso: no hace nada
    assert "nadie@x.test" not in despertador._eventos


def _peticion(host="127.0.0.1", cabeceras=None, publicados=None):
    class _Redis:
        async def publish(self, canal, _dato):
            publicados.append(canal)

    return SimpleNamespace(
        headers=cabeceras or {},
        client=SimpleNamespace(host=host),
        app=SimpleNamespace(state=SimpleNamespace(redis=_Redis())),
    )


async def test_solo_se_acepta_desde_la_propia_maquina():
    publicados = []
    cuerpo = aviso_entrega.EnCamino(
        destinatarios=["Ana@X.test", "ana@x.test", "no-es-correo", "luis@x.test"]
    )
    r = await aviso_entrega.correo_en_camino(cuerpo, _peticion(publicados=publicados))
    assert r == {"avisados": 2}
    assert sorted(publicados) == ["ws:poke:ana@x.test", "ws:poke:luis@x.test"]
    for mala in (
        _peticion(host="192.0.2.50", publicados=[]),
        _peticion(cabeceras={"x-real-ip": "198.51.100.7"}, publicados=[]),
    ):
        with pytest.raises(HTTPException) as e:
            await aviso_entrega.correo_en_camino(cuerpo, mala)
        assert e.value.status_code == 404
