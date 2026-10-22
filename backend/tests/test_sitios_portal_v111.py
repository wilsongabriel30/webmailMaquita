"""maquita-sitios-portal, v1.11: usuarios de bases, acceso remoto, cortafuegos de aplicaciones y claves SSH desde el
portal, y fichas de API (mqd_…) con su alcance. Mismo mundo de dobles que test_sitios_portal.py."""

import json

import pytest

from tests.test_sitios_portal import codigo, de_b64, mundo, pedir  # noqa: F401  (mundo es la fijación)

import bd  # noqa: E402
import fichas  # noqa: E402
import ordenes_desarrollo_portal as odv  # noqa: E402
import portal  # noqa: E402
import sesion  # noqa: E402
from errores import ErrorPortal  # noqa: E402

V111 = {"bases-usuarios", "base-usuario-crear", "base-usuario-permisos", "base-usuario-clave", "base-usuario-borrar",
        "base-usuario-remoto", "waf", "waf-guardar", "waf-bloqueos", "ssh-claves", "ssh-clave-agregar",
        "ssh-clave-borrar"}
USUARIO = "u_example1234_lector"
FICHA_API = "mqd_" + "a" * 40


@pytest.fixture
def sitio(mundo):  # noqa: F811
    mundo.sitio("example.org")
    return mundo


@pytest.fixture
def con_ficha(sitio, monkeypatch):
    """La petición llega con una ficha de API: la base la devuelve con el alcance que diga cada prueba."""
    fila = {"id": 7, "usuario": "ana", "activa": True, "cambiar_clave": False, "totp": True, "ficha_api": 3,
            "alcances": ["lectura"], "dominios": ["example.org"]}
    original = bd.consultar

    def consultar(sql, variables=None, tabla=None):
        if sql == fichas.SQL_FICHA:
            return fila
        if sql == sesion.SQL_SESION:
            raise AssertionError("una ficha de API no se busca como sesión")
        return original(sql, variables, tabla)

    monkeypatch.setattr(bd, "consultar", consultar)
    sitio.fila = fila
    return sitio


def pedir_ficha(orden, dominio=None, **args):
    return portal.atender({"ficha": FICHA_API, "orden": orden, "dominio": dominio, "args": args})


def codigo_ficha(orden, dominio=None, **args):
    with pytest.raises(ErrorPortal) as e:
        pedir_ficha(orden, dominio, **args)
    return e.value.codigo


def test_lista_exacta_de_v111():
    assert set(odv.ORDENES) == V111
    assert V111 <= set(portal.ORDENES)
    assert all(tipo == "sitio" for o, (tipo, _f) in portal.ORDENES.items() if o in V111)


def test_traduccion_de_cada_orden(sitio):
    pedir("base-usuario-crear", "example.org", base="w_example1234", sufijo="lector", permisos={"perfil": "lectura"})
    llamada = sitio.ayudante.ultima
    assert llamada[:5] == ["maquita-sitios", "base-usuario-crear", "example.org", "w_example1234", "lector"]
    assert json.loads(de_b64(llamada[5])) == {"perfil": "lectura"}
    pedir("base-usuario-permisos", "example.org", usuario=USUARIO, permisos={"perfil": "medida", "lista": ["SELECT"]})
    assert json.loads(de_b64(sitio.ayudante.ultima[4])) == {"perfil": "medida", "lista": ["SELECT"]}
    pedir("base-usuario-clave", "example.org", usuario=USUARIO)
    assert sitio.ayudante.ultima == ["maquita-sitios", "base-usuario-clave", "example.org", USUARIO]
    pedir("waf-guardar", "example.org", waf={"modo": "detectar", "paranoia": 2, "exclusiones": [{"regla": 942100}]})
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == {
        "modo": "detectar", "paranoia": 2, "exclusiones": [{"regla": 942100, "ruta": None}]}
    pedir("waf-bloqueos", "example.org", cuantos=20)
    assert sitio.ayudante.ultima == ["maquita-sitios", "waf-bloqueos", "example.org", "20"]
    pedir("ssh-clave-agregar", "example.org", cuenta="principal", clave="ssh-ed25519 AAAAC3Nza ana@example.org")
    assert de_b64(sitio.ayudante.ultima[4]) == "ssh-ed25519 AAAAC3Nza ana@example.org"


def test_remoto_nunca_lleva_amplia(sitio):
    pedir("base-usuario-remoto", "example.org", usuario=USUARIO, redes=["192.0.2.10", "198.51.100.0/24"])
    llamada = sitio.ayudante.ultima
    assert len(llamada) == 5 and "amplia" not in llamada
    assert json.loads(de_b64(llamada[4])) == ["192.0.2.10/32", "198.51.100.0/24"]


@pytest.mark.parametrize("red", ["0.0.0.0/0", "::/0", "172.16.0.0/12", "10.0.0.0/8", "2001:db8::/32", "todas",
                                 "192.0.2.1; DROP", 5, None])
def test_remoto_red_amplia_o_rara_sin_llamar(sitio, red):
    assert codigo("base-usuario-remoto", "example.org", usuario=USUARIO, redes=[red]) == 400
    assert sitio.ayudante.llamadas == []


def test_amplia_no_se_puede_colar_en_los_argumentos(sitio):
    pedir("base-usuario-remoto", "example.org", usuario=USUARIO, redes=["192.0.2.10"], amplia=True)
    assert "amplia" not in sitio.ayudante.ultima


@pytest.mark.parametrize("orden,args", [
    ("base-usuario-crear", {"base": "mysql", "sufijo": "lector", "permisos": {"perfil": "lectura"}}),
    ("base-usuario-crear", {"base": "w_example1234", "sufijo": "a'--", "permisos": {"perfil": "lectura"}}),
    ("base-usuario-crear", {"base": "w_example1234", "sufijo": "lector", "permisos": {"perfil": "root"}}),
    ("base-usuario-crear", {"base": "w_example1234", "sufijo": "lector",
                            "permisos": {"perfil": "medida", "lista": ["SELECT; DROP"]}}),
    ("base-usuario-borrar", {"usuario": "root"}), ("base-usuario-clave", {"usuario": "u_x_a'"}),
    ("waf-guardar", {"waf": {"modo": "x"}}), ("waf-guardar", {"waf": {"paranoia": 4}}),
    ("waf-guardar", {"waf": {"exclusiones": [{"regla": "942100"}]}}),
    ("waf-guardar", {"waf": {"exclusiones": [{"regla": 942100, "ruta": "/a\" allow"}]}}),
    ("waf-guardar", {"waf": {"nginx": "return 200;"}}), ("waf-bloqueos", {"cuantos": 0}),
    ("ssh-clave-agregar", {"cuenta": "../root", "clave": "ssh-ed25519 AAAA"}),
    ("ssh-clave-agregar", {"cuenta": "principal", "clave": "ssh-ed25519 AAAA\nssh-ed25519 BBBB"}),
    ("ssh-clave-borrar", {"id": "../x"}),
])
def test_argumentos_raros_sin_llamar(sitio, orden, args):
    assert codigo(orden, "example.org", **args) == 400
    assert sitio.ayudante.llamadas == []


def test_sitio_ajeno_no_encontrado(sitio):
    sitio.sitio("example.com")
    assert codigo("waf", "example.com") == 404
    assert codigo("bases-usuarios", "example.com") == 404
    assert sitio.ayudante.llamadas == []


# --- Fichas de API ---


def test_ficha_de_lectura_ve_pero_no_cambia(con_ficha):
    assert pedir_ficha("waf", "example.org")["ok"]
    assert pedir_ficha("bases-usuarios", "example.org")["ok"]
    assert codigo_ficha("waf-guardar", "example.org", waf={"modo": "apagado"}) == 403
    assert codigo_ficha("base-usuario-clave", "example.org", usuario=USUARIO) == 403
    assert codigo_ficha("base-entrar", "example.org", base="w_example1234", herramienta="adminer") == 403
    assert codigo_ficha("dns-agregar", "example.org") == 403
    assert [ll[1] for ll in con_ficha.ayudante.llamadas] == ["waf", "bases-usuarios"]


def test_ficha_con_alcance_de_sitios(con_ficha):
    con_ficha.fila["alcances"] = ["sitios"]
    assert pedir_ficha("waf-guardar", "example.org", waf={"modo": "detectar"})["ok"]
    assert codigo_ficha("dns-agregar", "example.org") == 403


def test_ficha_solo_dns_no_toca_sitios(con_ficha):
    con_ficha.fila["alcances"] = ["dns"]
    assert codigo_ficha("bases-usuarios", "example.org") == 403
    assert codigo_ficha("listar") == 403
    assert con_ficha.ayudante.llamadas == []


@pytest.mark.parametrize("cambio", [{"activa": False}, {"cambiar_clave": True}, {"totp": False}])
def test_ficha_de_cuenta_que_ya_no_puede(con_ficha, cambio):
    con_ficha.fila.update(cambio)
    assert codigo_ficha("waf", "example.org") == 403


def test_ficha_revocada_o_vencida(con_ficha, monkeypatch):
    monkeypatch.setattr(fichas, "buscar", lambda f: None)
    assert codigo_ficha("waf", "example.org") == 403


def test_ficha_sin_alcance_conocido(con_ficha):
    con_ficha.fila["alcances"] = ["todo"]
    assert codigo_ficha("waf", "example.org") == 403


def test_sesion_normal_sin_alcances_pasa(sitio):
    assert pedir("waf-guardar", "example.org", waf={"modo": "detectar"})["ok"]
