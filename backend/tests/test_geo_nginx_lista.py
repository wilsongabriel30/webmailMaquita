"""Lista de nginx para el filtro por país del 443, a partir de los conjuntos del cortafuegos."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "geo_nginx_lista", RAIZ / "deploy/tools/geo-nginx-lista.py"
)
lista = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lista)


def _conjunto(nombre, elementos):
    return json.dumps(
        {
            "nftables": [
                {"metainfo": {"version": "1"}},
                {"set": {"name": nombre, "elem": elementos}},
            ]
        }
    )


PAISES = _conjunto(
    "paises_permitidos",
    [
        {"prefix": {"addr": "10.0.0.0", "len": 8}},
        {"prefix": {"addr": "192.0.2.0", "len": 24}},
        {"prefix": {"addr": "198.51.100.0", "len": 24}},
        {"prefix": {"addr": "203.0.113.0", "len": 25}},
        "203.0.113.200",
        {"range": ["203.0.113.128", "203.0.113.191"]},
    ],
)
NUBE = _conjunto(
    "nube_microsoft",
    [
        {"prefix": {"addr": "192.0.2.0", "len": 24}},
        {"prefix": {"addr": "100.64.0.0", "len": 10}},
    ],
)


def test_convierte_prefijos_direcciones_y_rangos():
    texto = lista.lista_nginx(PAISES)
    assert (
        "10.0.0.0/8 1;" in texto
        and "203.0.113.200/32 1;" in texto
        and "203.0.113.128/26 1;" in texto
    )


def test_une_varios_conjuntos_seguidos_sin_repetir():
    texto = lista.lista_nginx(PAISES + "\n" + NUBE)
    assert texto.count("192.0.2.0/24 1;") == 1 and "100.64.0.0/10 1;" in texto


def test_orden_estable_por_direccion():
    redes = [
        l.split()[0]
        for l in lista.lista_nginx(PAISES).splitlines()
        if l.endswith(" 1;")
    ]
    assert redes == sorted(
        redes, key=lambda r: tuple(int(x) for x in r.split("/")[0].split("."))
    )


def test_sin_conjuntos_la_instalacion_no_filtra_y_se_deja_pasar_a_todos():
    import ipaddress

    abierta = lista.lista_nginx("")
    mitades = [
        ipaddress.ip_network(l.split()[0])
        for l in abierta.splitlines()
        if l.endswith(" 1;")
    ]
    # Dos mitades que juntas cubren todo IPv4; nunca la red completa, que nginx avisa como duplicada.
    assert len(mitades) == 2 and sum(m.num_addresses for m in mitades) == 2**32
    assert all(m.prefixlen == 1 for m in mitades)


def test_conjunto_casi_vacio_no_escribe_lista():
    with pytest.raises(ValueError):
        lista.lista_nginx(
            _conjunto("paises_permitidos", [{"prefix": {"addr": "10.0.0.0", "len": 8}}])
        )


def test_ignora_ipv6():
    texto = lista.lista_nginx(
        PAISES + _conjunto("otro", [{"prefix": {"addr": "2001:db8::", "len": 32}}])
    )
    assert "2001:db8" not in texto


def test_las_rutas_abiertas_son_solo_las_previstas():
    conf = (RAIZ / "deploy/webmail/nginx/filtro-pais.conf").read_text(encoding="utf-8")
    abiertas = [
        l.split()[0]
        for l in conf.split("map $uri $ruta_abierta")[1].split("}")[0].splitlines()
        if l.strip().endswith("1;")
    ]
    assert abiertas == ["~^/api/federacion/", "/api/safelink", "~^/\\.well-known/"]


def test_las_plantillas_del_443_llevan_el_filtro_y_mta_sts_no():
    for plantilla in ("webmail.conf", "autodiscover-dominios.conf"):
        texto = (RAIZ / "deploy/webmail/nginx" / plantilla).read_text(encoding="utf-8")
        assert "include snippets/filtro-pais.conf;" in texto, plantilla
    instalador = (RAIZ / "deploy/webmail/instalar.sh").read_text(encoding="utf-8")
    assert (
        "maquita-filtro-pais.conf" in instalador
        and "geo-nginx-rebuild.sh" in instalador
    )
