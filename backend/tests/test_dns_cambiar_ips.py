"""zona.cambiar_ips: cada registro sigue a su función (correo o web) al cambiar las IP del servidor."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "dns", "lib"))
zona = pytest.importorskip("zona")

VIEJA, WEB, NS2 = "192.0.2.10", "198.51.100.20", "198.51.100.21"


def _registro(nombre, tipo, valor, sistema=True, prioridad=None):
    return {
        "id": f"{nombre}{tipo}",
        "nombre": nombre,
        "tipo": tipo,
        "valor": valor,
        "ttl": 3600,
        "prioridad": prioridad,
        "sistema": sistema,
    }


@pytest.fixture
def datos(tmp_path, monkeypatch):
    z = {
        "zona": "example.org",
        "serial": 1,
        "primario": "ns1.example.org.",
        "hostmaster": "hostmaster.example.org.",
        "registros": [
            _registro("@", "NS", "ns1.example.org."),
            _registro("ns1", "A", VIEJA),
            _registro("@", "NS", "ns3.example.org."),
            _registro("ns3", "A", VIEJA),
            _registro("@", "A", VIEJA),
            _registro("www", "A", VIEJA),
            _registro("mail", "A", VIEJA),
            _registro("@", "MX", "mail.example.org.", prioridad=10),
            _registro("@", "TXT", f"v=spf1 mx ip4:{VIEJA} -all"),
            _registro("otro", "A", "203.0.113.5", sistema=False),
        ],
    }
    (tmp_path / "example.org.json").write_text(json.dumps(z))
    monkeypatch.setattr(zona, "DATOS", str(tmp_path))
    # aplicar() (BIND) se sustituye por guardar la zona resultante; normalizar() deja el registro tal cual.
    monkeypatch.setattr(zona, "aplicar", lambda z: (tmp_path / "example.org.json").write_text(json.dumps(z)))
    monkeypatch.setattr(zona.R, "normalizar", lambda r, _z: dict(r))
    return tmp_path


def _cambiar(datos, srv):
    anterior = {
        "ip_correo": VIEJA,
        "ip_web": VIEJA,
        "ns": [{"nombre": "ns1", "ip": VIEJA}, {"nombre": "ns3", "ip": VIEJA}],
    }
    zona.cambiar_ips(anterior, srv)
    regs = json.loads((datos / "example.org.json").read_text())["registros"]
    return {(r["nombre"], r["tipo"]): r["valor"] for r in regs}


def test_cambiar_solo_la_web_no_mueve_el_correo_ni_el_spf(datos):
    v = _cambiar(
        datos, {"ip_correo": VIEJA, "ip_web": WEB, "ns": [{"nombre": "ns1", "ip": WEB}, {"nombre": "ns2", "ip": NS2}]}
    )
    assert v[("@", "A")] == WEB and v[("www", "A")] == WEB
    assert v[("mail", "A")] == VIEJA
    assert v[("@", "TXT")] == f"v=spf1 mx ip4:{VIEJA} -all"
    assert v[("ns1", "A")] == WEB and v[("ns2", "A")] == NS2 and ("ns3", "A") not in v
    assert v[("otro", "A")] == "203.0.113.5"


def test_cambiar_el_correo_mueve_mail_y_spf(datos):
    v = _cambiar(datos, {"ip_correo": WEB, "ip_web": WEB, "ns": [{"nombre": "ns1", "ip": WEB}]})
    assert v[("mail", "A")] == WEB and v[("@", "A")] == WEB
    assert v[("@", "TXT")] == f"v=spf1 mx ip4:{WEB} -all"
