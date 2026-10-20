"""La app Android se reconoce por su agente de usuario: la de Maquita y la genérica de cada organización."""

from types import SimpleNamespace

from app.auth.dispositivos_confianza import es_app


def _peticion(agente):
    return SimpleNamespace(headers={"user-agent": agente} if agente is not None else {})


def test_reconoce_la_app_de_maquita_y_la_generica():
    assert es_app(
        _peticion("Mozilla/5.0 (Linux; Android 14) Chrome/130 MaquitaMailApp/1.3.9")
    )
    assert es_app(
        _peticion("Mozilla/5.0 (Linux; Android 14) Chrome/130 CorreoApp/1.0.0")
    )


def test_un_navegador_no_es_la_app():
    assert not es_app(
        _peticion("Mozilla/5.0 (Windows NT 10.0) Chrome/130 Safari/537.36")
    )
    assert not es_app(_peticion(None))
