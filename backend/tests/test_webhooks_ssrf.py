"""F-05: los webhooks no pueden apuntar a la red interna, ni por DNS con varias direcciones,
ni por rebinding entre la validación y la conexión (la IP validada queda fijada)."""

import pytest

from app.webhooks import salida_segura as sg


def _resolver(mapa):
    def fake(host, puerto):
        if host not in mapa:
            raise sg.DestinoNoPermitido("Hostname no resolvible")
        return list(mapa[host])

    return fake


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://[::1]/hook",
        "https://10.1.2.3/hook",
        "https://192.168.1.10/hook",
        "https://172.16.5.5/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://usuario:clave@example.com/hook",
        "ftp://example.com/hook",
    ],
)
def test_destinos_prohibidos(monkeypatch, url):
    monkeypatch.setattr(sg, "resolver_todas", _resolver({"localhost": ["127.0.0.1"]}))
    with pytest.raises(sg.DestinoNoPermitido):
        sg.destino_validado(url)


def test_basta_con_que_una_direccion_sea_privada(monkeypatch):
    monkeypatch.setattr(
        sg, "resolver_todas", _resolver({"mixto.example": ["203.0.113.5", "10.0.0.7"]})
    )
    with pytest.raises(sg.DestinoNoPermitido):
        sg.destino_validado("https://mixto.example/hook")


def test_http_solo_en_desarrollo(monkeypatch):
    monkeypatch.setattr(
        sg, "resolver_todas", _resolver({"ok.example": ["203.0.113.5"]})
    )
    monkeypatch.setattr(sg, "_http_permitido", lambda: False)
    with pytest.raises(sg.DestinoNoPermitido):
        sg.destino_validado("http://ok.example/hook")
    monkeypatch.setattr(sg, "_http_permitido", lambda: True)
    assert sg.destino_validado("http://ok.example/hook").ip == "203.0.113.5"


def test_la_conexion_queda_fijada_a_la_ip_validada(monkeypatch):
    """Rebinding: la validación resolvió a una IP pública; aunque el DNS cambie después, la URL
    que se usa para conectar lleva esa IP y el nombre solo va en Host/SNI."""
    monkeypatch.setattr(
        sg, "resolver_todas", _resolver({"hook.example": ["203.0.113.9"]})
    )
    d = sg.destino_validado("https://hook.example:8443/ruta?x=1")
    assert d.url_fijada == "https://203.0.113.9:8443/ruta?x=1"
    assert d.host == "hook.example" and d.esquema == "https"
    monkeypatch.setattr(
        sg, "resolver_todas", _resolver({"hook.example": ["127.0.0.1"]})
    )
    assert d.url_fijada == "https://203.0.113.9:8443/ruta?x=1"  # no vuelve a resolver
