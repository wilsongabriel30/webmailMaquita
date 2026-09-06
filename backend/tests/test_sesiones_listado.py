"""L-01 (cuarta revisión): listado de las sesiones propias a partir del estado sid/av."""

import pytest
from app.auth.sesiones import listar_sesiones

pytestmark = pytest.mark.asyncio


class _Redis:
    """Doble mínimo: conjuntos sids:{u} y hashes sess:{u}:{sid} (decode_responses=True)."""

    def __init__(self, conjuntos, hashes):
        self.conjuntos, self.hashes = conjuntos, hashes

    async def smembers(self, clave):
        return set(self.conjuntos.get(clave, set()))

    async def hgetall(self, clave):
        return dict(self.hashes.get(clave, {}))

    async def srem(self, clave, valor):
        self.conjuntos.get(clave, set()).discard(valor)


def _redis():
    return _Redis(
        {"sids:ana@example.com": {"s1", "s2", "muerta"}},
        {
            "sess:ana@example.com:s1": {
                "kind": "normal",
                "ua": "Mozilla/5.0 (X11; Linux) Firefox/130",
                "ip": "10.0.0.5",
                "creada": "1700000000",
                "abs_exp": "1700600000",
            },
            "sess:ana@example.com:s2": {
                "kind": "impersonate",
                "ua": "Maquita-App/2.1 Android",
                "ip": "10.0.0.9",
                "creada": "1700005000",
                "abs_exp": "1700008600",
            },
        },
    )


async def test_lista_marca_la_actual_y_retira_los_sids_muertos():
    r = _redis()
    sesiones = await listar_sesiones(r, "ana@example.com", sid_actual="s2")
    assert [s["sid"] for s in sesiones] == ["s2", "s1"]  # la actual primero
    assert sesiones[0]["actual"] is True and sesiones[1]["actual"] is False
    assert sesiones[0]["tipo"] == "impersonate" and sesiones[1]["ip"] == "10.0.0.5"
    assert sesiones[1]["creada"] == 1700000000 and sesiones[1]["vence"] == 1700600000
    assert "Firefox" in sesiones[1]["dispositivo"]
    # el sid sin estado (sesión cerrada o vencida) desaparece del índice
    assert r.conjuntos["sids:ana@example.com"] == {"s1", "s2"}


async def test_sin_sesiones_o_sin_redis():
    assert await listar_sesiones(_Redis({}, {}), "nadie@example.com") == []

    class _Roto(_Redis):
        async def smembers(self, clave):
            raise ConnectionError("redis caído")

    assert await listar_sesiones(_Roto({}, {}), "ana@example.com") == []
