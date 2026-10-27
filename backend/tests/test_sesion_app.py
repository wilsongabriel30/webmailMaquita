"""Sesiones de la app de escritorio (app/auth/sesion_app.py): reconocimiento y duraciones.

Pruebas unitarias sin base ni Redis: solo la regla de qué petición es de la app y qué
vencimientos le tocan a cada clase de sesión.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.auth import sesion_app
from app.config import get_settings

UA_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/155.0.0.0 Safari/537.36"
)
UA_APP = UA_NAVEGADOR + " Edg/155.0.0.0 MaquitaTeams/0.7.1"


def _peticion(**cabeceras):
    return SimpleNamespace(headers={k.lower(): v for k, v in cabeceras.items()})


def test_navegador_no_es_app():
    assert not sesion_app.es_app(_peticion(**{"user-agent": UA_NAVEGADOR}))
    assert not sesion_app.es_app(_peticion(**{"user-agent": "python-httpx/0.28.1"}))
    assert not sesion_app.es_app(None)


def test_user_agent_de_la_app():
    assert sesion_app.es_app(_peticion(**{"user-agent": UA_APP}))


def test_cabecera_propia_de_la_app():
    assert sesion_app.es_app(
        _peticion(**{"user-agent": UA_NAVEGADOR, "x-maquita-app": "0.7.2"})
    )


def test_login_nativo_sin_user_agent_es_app():
    # El HttpClient de .NET de la 0.7.1 no manda User-Agent; ningún navegador lo manda vacío.
    assert sesion_app.es_app(_peticion())
    assert sesion_app.es_app(_peticion(**{"user-agent": "   "}))


def test_parametros_sesion():
    assert sesion_app.parametros_sesion(_peticion(**{"user-agent": UA_NAVEGADOR})) == {}
    p = sesion_app.parametros_sesion(_peticion(**{"user-agent": UA_APP}))
    assert p["kind"] == sesion_app.KIND_APP
    esperado = datetime.now(timezone.utc) + timedelta(
        days=get_settings().app_sesion_dias
    )
    assert abs((p["abs_exp"] - esperado).total_seconds()) < 5


def test_duraciones_por_clase():
    s = get_settings()
    assert sesion_app.tope_access_seg("normal") == s.access_token_expire_minutes * 60
    assert sesion_app.tope_access_seg("app") == s.app_access_dias * 86400
    assert sesion_app.dias_refresh("normal") == s.refresh_token_expire_days
    assert sesion_app.dias_refresh("app") == s.app_sesion_dias
    # La app dura más que el navegador, nunca menos.
    assert sesion_app.tope_access_seg("app") > sesion_app.tope_access_seg("normal")
    assert sesion_app.dias_refresh("app") > sesion_app.dias_refresh("normal")
