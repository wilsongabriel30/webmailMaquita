"""N-4: el receptor de informes CSP filtra, acota, limita y deduplica."""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.security import csp_informes as ci

pytestmark = pytest.mark.asyncio

NEL = {
    "age": 11364,
    "type": "network-error",
    "body": {"elapsed_time": 15, "phase": "application"},
}
CSP_NUEVO = {
    "type": "csp-violation",
    "body": {
        "documentURL": "https://m/x",
        "effectiveDirective": "img-src",
        "blockedURL": "https://evil/p.gif",
    },
}
CSP_CLASICO = {
    "csp-report": {
        "document-uri": "https://m/y",
        "violated-directive": "script-src",
        "blocked-uri": "inline",
    }
}


def test_solo_las_violaciones_de_csp_cuentan():
    assert ci.extraer_violaciones(json.dumps([NEL, NEL]).encode()) == []
    v = ci.extraer_violaciones(json.dumps([NEL, CSP_NUEVO, CSP_CLASICO]).encode())
    assert (
        len(v) == 2
        and v[0]["blockedURL"] == "https://evil/p.gif"
        and v[1]["blocked-uri"] == "inline"
    )
    assert (
        ci.extraer_violaciones(b"no es json") == []
        and ci.extraer_violaciones(b"") == []
    )
    assert ci.huella(v[0]) != ci.huella(v[1]) and ci.huella(v[0]) == ci.huella(
        dict(v[0], disposition="x")
    )


class _Redis:
    def __init__(self):
        self.d = {}

    async def incr(self, k):
        self.d[k] = self.d.get(k, 0) + 1
        return self.d[k]

    async def expire(self, k, s):
        return True

    async def set(self, k, v, ex=None, nx=False):
        if nx and k in self.d:
            return None
        self.d[k] = v
        return True


def _app(redis):
    app = FastAPI()
    app.include_router(ci.router)
    app.state.redis = redis
    return app


async def test_flujo_completo(caplog):
    caplog.set_level("WARNING", logger="security.csp")
    r = _Redis()
    async with AsyncClient(
        transport=ASGITransport(app=_app(r)), base_url="http://t"
    ) as c:
        cab = {"content-type": "application/reports+json", "x-real-ip": "10.0.0.1"}
        # NEL: 200 y nada registrado
        assert (
            await c.post("/api/csp-report", content=json.dumps([NEL]), headers=cab)
        ).status_code == 200
        assert not [x for x in caplog.records if "CSP_VIOLACION" in x.message]
        # violación nueva: se registra una vez; repetida: no
        for _ in range(3):
            assert (
                await c.post(
                    "/api/csp-report", content=json.dumps([CSP_NUEVO]), headers=cab
                )
            ).status_code == 200
        assert len([x for x in caplog.records if "CSP_VIOLACION" in x.message]) == 1
        # cuerpo grande: 413; tipo raro: 400
        assert (
            await c.post(
                "/api/csp-report", content=b"x" * (ci.MAX_BYTES + 1), headers=cab
            )
        ).status_code == 413
        assert (
            await c.post(
                "/api/csp-report", content=b"{}", headers={"content-type": "text/plain"}
            )
        ).status_code == 400
        # límite por IP
        for _ in range(ci.INFORMES_POR_MINUTO):
            await c.post(
                "/api/csp-report", content=json.dumps([CSP_CLASICO]), headers=cab
            )
        assert (
            await c.post(
                "/api/csp-report", content=json.dumps([CSP_CLASICO]), headers=cab
            )
        ).status_code == 429
        # otra IP sigue pudiendo
        assert (
            await c.post(
                "/api/csp-report",
                content=json.dumps([CSP_CLASICO]),
                headers=dict(cab, **{"x-real-ip": "10.0.0.2"}),
            )
        ).status_code == 200
