"""Los datos de la organización salen del entorno o de su fichero; el código solo trae ejemplos."""

import importlib

import pytest


@pytest.fixture
def org(monkeypatch, tmp_path):
    def cargar(contenido="", dominios="", **entorno):
        fichero = tmp_path / "organizacion.env"
        fichero.write_text(contenido, encoding="utf-8")
        lista = tmp_path / "dominios.txt"
        lista.write_text(dominios, encoding="utf-8")
        for clave in ("MAIL_DOMAIN", "PUBLIC_BASE_URL", "JITSI_BASE_URL", "KC_BASE", "ORG_DOMINIOS", "ORG_REDES",
                      "ORG_URL_CORREO", "ORG_CORREOS_AVISOS", "ORG_DOMINIO", "ORG_DOMINIOS_GRUPOS"):
            monkeypatch.delenv(clave, raising=False)
        monkeypatch.setenv("ORG_FICHERO", str(fichero))
        monkeypatch.setenv("ORG_FICHERO_DOMINIOS", str(lista))
        for clave, v in entorno.items():
            monkeypatch.setenv(clave, v)
        import app.organizacion as modulo
        return importlib.reload(modulo)
    return cargar


def test_sin_configurar_todo_es_de_ejemplo(org):
    o = org()
    assert o.dominio_principal() == "example.org"
    assert o.dominios_propios() == frozenset({"example.org"})
    assert o.url_correo() == "https://mail.example.org"
    assert o.redes_propias() == []
    assert o.correos_de_avisos() == ["postmaster@example.org"]
    assert o.remitente("ORG_REMITENTE_X", "Avisos", "avisos") == "Avisos <avisos@example.org>"


def test_lee_el_fichero_con_o_sin_comillas_y_lo_puede_leer_un_shell(org):
    o = org('# comentario\nORG_DOMINIOS="uno.example dos.example"\nexport ORG_REDES=192.0.2.0/24,198.51.100.0/24\n'
            "ORG_URL_CORREO='https://correo.uno.example/'\nORG_DOMINIO=uno.example\n")
    assert o.dominios_propios() == frozenset({"uno.example", "dos.example"})
    assert o.redes_propias() == ["192.0.2.0/24", "198.51.100.0/24"]
    assert o.url_correo() == "https://correo.uno.example"
    assert o.servidor(o.url_correo() + ":8443/x") == "correo.uno.example"


def test_el_entorno_manda_sobre_el_fichero(org):
    o = org("ORG_URL_CORREO=https://del-fichero.example\n", PUBLIC_BASE_URL="https://del-entorno.example")
    assert o.url_correo() == "https://del-entorno.example"


def test_se_suman_los_dominios_del_fichero_de_dominios(org):
    o = org("ORG_DOMINIOS=uno.example\n", dominios="# de la casa\nDos.Example\n\ntres.example\n", MAIL_DOMAIN="uno.example")
    assert o.dominios_propios() == frozenset({"uno.example", "dos.example", "tres.example"})


def test_una_lista_concreta_o_todos_los_propios(org):
    o = org("ORG_DOMINIOS=uno.example dos.example\nORG_DOMINIOS_GRUPOS=uno.example\nORG_DOMINIO=uno.example\n")
    assert o.dominios("ORG_DOMINIOS_GRUPOS") == frozenset({"uno.example"})
    assert o.dominios("ORG_DOMINIOS_QUE_NO_ESTA") == frozenset({"uno.example", "dos.example"})
