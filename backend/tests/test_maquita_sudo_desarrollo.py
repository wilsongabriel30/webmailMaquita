"""v1.11: forma exacta de las órdenes «para desarrolladores» en maquita-sudo y apertura del puerto de las bases en el
cortafuegos del proyecto (solo para los orígenes elegidos, nunca para todos)."""

import json
import os
import sys

import pytest

from tests.test_maquita_sudo_sitios_web import _no, _ok, b64

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = "example.org"
U = "u_example1234_lector"


def test_ordenes_permitidas():
    assert _ok("bases-usuarios", D) and _ok("waf", D) and _ok("ssh-claves", D)
    assert _ok("base-usuario-crear", D, "w_example1234", "lector", b64({"perfil": "lectura"}))
    assert _ok("base-usuario-crear", D, "x_example1234_00ff", "app", b64({"perfil": "todo"}))
    assert _ok("base-usuario-permisos", D, U, b64({"perfil": "escritura"}))
    assert _ok("base-usuario-clave", D, U) and _ok("base-usuario-borrar", D, U)
    assert _ok("base-usuario-remoto", D, U, b64(["192.0.2.10"]))
    assert _ok("base-usuario-remoto", D, U, b64(["172.16.0.0/12"]), "amplia")
    assert _ok("waf-guardar", D, b64({"modo": "detectar", "exclusiones": [{"regla": 942100}] * 50}))
    assert _ok("waf-bloqueos", D) and _ok("waf-bloqueos", D, "200")
    assert _ok("ssh-clave-agregar", D, "principal", b64("ssh-rsa " + "A" * 700 + " ana@example.org"))
    assert _ok("ssh-clave-borrar", D, "0a1b2c3d")


@pytest.mark.parametrize("args", [
    ("bases-usuarios", D, "x"), ("bases-usuarios", "EXAMPLE.org"),
    ("base-usuario-crear", D, "mysql", "lector", "e30"), ("base-usuario-crear", D, "w_example1234", "Lector", "e30"),
    ("base-usuario-crear", D, "w_example1234", "a'b", "e30"), ("base-usuario-crear", D, "w_example1234", "lector", "{}"),
    ("base-usuario-clave", D, "root"), ("base-usuario-clave", D, "u_example1234_lector'"),
    ("base-usuario-borrar", D, "u_example1234_l"),
    ("base-usuario-remoto", D, U, "W10", "todas"), ("base-usuario-remoto", D, U, "W10", "amplia", "x"),
    ("waf-guardar", D, "no es base64"), ("waf-bloqueos", D, "0"), ("waf-bloqueos", D, "1000"),
    ("ssh-clave-agregar", D, "root!", "eA"), ("ssh-clave-agregar", D, "principal", "a" * 8001),
    ("ssh-clave-borrar", D, "0a1b2c3"), ("ssh-clave-borrar", D, "../../etc"),
    ("waf", D, "\n"), ("ssh-claves", D + "\n"),
])
def test_formas_rechazadas(args):
    _no(*args)


def test_el_correo_no_puede_llamarlas():
    _no("bases-usuarios", D, usuario="www-data")


# --- Cortafuegos del proyecto ---


@pytest.fixture
def cortafuegos(tmp_path, monkeypatch):
    lib = os.path.join(RAIZ, "deploy", "cortafuegos", "lib")
    previos = {n: sys.modules.pop(n) for n in ("config", "reglas") if n in sys.modules}
    sys.path.insert(0, lib)
    try:
        import config
        import reglas
    finally:
        sys.path.remove(lib)
        for n in ("config", "reglas"):
            sys.modules.pop(n, None)
        sys.modules.update(previos)
    (tmp_path / "bases.d").mkdir()
    monkeypatch.setattr(config, "BASES_DIR", str(tmp_path / "bases.d"))
    monkeypatch.setattr(config, "APPS_DIR", str(tmp_path / "apps.d"))
    return config, reglas, tmp_path / "bases.d"


def test_puerto_de_las_bases_solo_para_sus_origenes(cortafuegos):
    config, reglas, carpeta = cortafuegos
    (carpeta / f"{D}.json").write_text(json.dumps({"dominio": D, "reglas": [
        {"puerto": 3306, "origenes": ["192.0.2.10/32", "2001:db8::/64"]}, {"puerto": 5432, "origenes": ["198.51.100.0/24"]}]}))
    v4 = reglas.texto(config.por_defecto(admin=["192.0.2.1"]))
    v6 = reglas.texto(config.por_defecto(admin=["192.0.2.1"]), v6=True)
    assert f'-A CORTAFUEGOS -s 192.0.2.10/32 -p tcp --dport 3306 -m comment --comment "bases {D}" -j ACCEPT' in v4
    assert f'-A CORTAFUEGOS -s 198.51.100.0/24 -p tcp --dport 5432 -m comment --comment "bases {D}" -j ACCEPT' in v4
    assert f'-A CORTAFUEGOS -s 2001:db8::/64 -p tcp --dport 3306 -m comment --comment "bases {D}" -j ACCEPT' in v6
    for texto in (v4, v6):
        assert not [l for l in texto.splitlines() if ("--dport 3306" in l or "--dport 5432" in l) and " -s " not in l]


@pytest.mark.parametrize("contenido", [
    {"dominio": D, "reglas": [{"puerto": 3306, "origenes": ["0.0.0.0/0"]}]},
    {"dominio": D, "reglas": [{"puerto": 3306, "origenes": ["::/0"]}]},
    {"dominio": D, "reglas": [{"puerto": 22, "origenes": ["192.0.2.10"]}]},
    {"dominio": D, "reglas": [{"puerto": 3306, "origenes": []}]},
    {"dominio": "no es un dominio", "reglas": [{"puerto": 3306, "origenes": ["192.0.2.10"]}]},
    {"dominio": D, "reglas": [{"puerto": 3306, "origenes": ["192.0.2.10; iptables -F"]}]},
])
def test_lo_que_abriria_de_mas_se_ignora(cortafuegos, contenido):
    config, reglas, carpeta = cortafuegos
    (carpeta / f"{D}.json").write_text(json.dumps(contenido))
    texto = reglas.texto(config.por_defecto(admin=["192.0.2.1"])) + reglas.texto(config.por_defecto(admin=["192.0.2.1"]), v6=True)
    assert "bases " not in texto
