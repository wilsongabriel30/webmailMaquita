"""El Message-ID lleva el dominio de quien envía, no el del servidor."""

from app.mail.msgid import msgid_del_remitente


def test_usa_el_dominio_del_remitente():
    assert msgid_del_remitente("ana@cliente.example", "servidor.example").endswith("@cliente.example>")


def test_remitente_con_nombre_visible():
    mid = msgid_del_remitente('"Ana Pérez" <Ana@Cliente.Example>', "servidor.example")
    assert mid.endswith("@cliente.example>")


def test_sin_dominio_usa_el_del_servidor():
    for remitente in ("", "ana", None):
        assert msgid_del_remitente(remitente, "servidor.example").endswith("@servidor.example>")


def test_cada_mensaje_recibe_uno_distinto():
    assert msgid_del_remitente("a@x.example", "s.example") != msgid_del_remitente("a@x.example", "s.example")
