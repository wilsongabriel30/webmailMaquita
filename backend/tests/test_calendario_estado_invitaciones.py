"""Aviso del calendario cuando una invitación no llega (28/10/2026).

Antecedente: invitaciones a correos externos que el destino rechazaba (dirección mal escrita,
IP bloqueada) sin que quien las enviaba se enterara. `estado_invitaciones` traduce el registro
de entregas (`mail_trace`) a «entregado», «rechazado» o «en_espera» con un motivo claro.
"""

import asyncio
import smtplib

from app.calendar import estado_invitaciones as ei


class _DB:
    def __init__(self, filas):
        self.filas, self.args = filas, None

    async def fetch(self, sql, *args):
        self.args = args
        return self.filas


def _fila(mid, dest, status, dsn=None):
    return {"message_id": mid, "destinatario": dest, "status": status, "dsn": dsn}


def test_message_id_lleva_el_dominio_del_remitente():
    mid = ei.nuevo_message_id("ana@example.org")
    assert mid.startswith("<") and mid.endswith("@example.org>")
    assert ".invitacion@" in mid
    assert ei.nuevo_message_id("ana@example.org") != mid


def test_explica_errores_de_envio():
    assert "sesión" in ei.explicar_error_envio(smtplib.SMTPAuthenticationError(535, b"x"))
    assert "destinatario" in ei.explicar_error_envio(smtplib.SMTPRecipientsRefused({}))
    assert "conectar" in ei.explicar_error_envio(ConnectionRefusedError())
    assert "no aceptó el envío" in ei.explicar_error_envio(smtplib.SMTPDataError(554, b"x"))


def test_traduce_el_registro_de_entregas():
    db = _DB([
        _fila("a@example.org", "x@gmail.com", "bounced", "5.1.1"),
        _fila("b@example.org", "y@hotmail.com", "bounced", "5.7.1"),
        _fila("c@example.org", "z@ejemplo.ec", "deferred", "4.4.1"),
        _fila("d@example.org", "w@ejemplo.ec", "sent", "2.0.0"),
        _fila("e@example.org", "v@ejemplo.ec", "otro"),
    ])
    r = asyncio.run(ei.consultar(db, "ana@example.org", ["<a@example.org>", " b@example.org ", "", "c@example.org"]))
    por_correo = {x["email"]: x for x in r}
    assert set(por_correo) == {"x@gmail.com", "y@hotmail.com", "z@ejemplo.ec", "w@ejemplo.ec"}
    assert por_correo["x@gmail.com"]["estado"] == "rechazado"
    assert "no existe" in por_correo["x@gmail.com"]["detalle"]
    assert "bloqueo" in por_correo["y@hotmail.com"]["detalle"]
    assert por_correo["z@ejemplo.ec"]["estado"] == "en_espera"
    assert por_correo["w@ejemplo.ec"]["estado"] == "entregado"
    assert "detalle" not in por_correo["w@ejemplo.ec"]
    assert por_correo["x@gmail.com"]["message_id"] == "<a@example.org>"
    # Busca sin los signos < >, solo del remitente y sin los saltos internos del filtro.
    ids, remitente, internos = db.args
    assert ids == ["a@example.org", "b@example.org", "c@example.org"]
    assert remitente == "ana@example.org"
    assert internos == ["maquita-filter%"]


def test_sin_ids_no_consulta():
    db = _DB([])
    assert asyncio.run(ei.consultar(db, "ana@example.org", ["", "  "])) == []
    assert db.args is None
