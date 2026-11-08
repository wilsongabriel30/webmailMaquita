"""Omisiones del índice (spam, servidor, publicidad), recientes del día y quitar al eliminar."""

import asyncio

from app.rag import eliminar, filtro_cabeceras, recientes, texto

CASA = {"example.org", "example.com"}


def _cab(de="Proveedor <ventas@tienda.com>", **extra):
    return {
        "de": de,
        "para": "x@example.org",
        "asunto": "Hola",
        "fecha": "2026-11-08",
        "extra": extra,
    }


def test_correo_normal_externo_se_indexa():
    assert filtro_cabeceras.motivo_omision(_cab(), CASA) is None


def test_marcado_como_spam_por_el_servidor_se_omite():
    assert (
        filtro_cabeceras.motivo_omision(_cab(**{"X-Spam-Flag": "YES"}), CASA) == "spam"
    )


def test_rebotes_y_automaticos_del_servidor_se_omiten():
    assert (
        filtro_cabeceras.motivo_omision(
            _cab(de="Mail Delivery System <MAILER-DAEMON@mx.ejemplo.com>"), CASA
        )
        == "servidor"
    )
    assert (
        filtro_cabeceras.motivo_omision(_cab(**{"Return-Path": "<>"}), CASA)
        == "servidor"
    )
    assert (
        filtro_cabeceras.motivo_omision(
            _cab(**{"Auto-Submitted": "auto-replied"}), CASA
        )
        == "servidor"
    )
    assert (
        filtro_cabeceras.motivo_omision(_cab(**{"Auto-Submitted": "no"}), CASA) is None
    )


def test_publicidad_masiva_se_omite_solo_con_baja_y_precedencia():
    assert (
        filtro_cabeceras.motivo_omision(
            _cab(**{"List-Unsubscribe": "<mailto:baja@x>", "Precedence": "bulk"}), CASA
        )
        == "publicidad"
    )
    # Una lista de distribución legítima sin Precedence bulk no se omite; ni un bulk sin enlace de baja.
    assert (
        filtro_cabeceras.motivo_omision(
            _cab(**{"List-Unsubscribe": "<mailto:baja@x>"}), CASA
        )
        is None
    )
    assert filtro_cabeceras.motivo_omision(_cab(**{"Precedence": "bulk"}), CASA) is None


def test_los_de_la_casa_nunca_se_omiten():
    cab = _cab(
        de='"Raíces Tareas" <tareas@example.org>',
        **{
            "X-Spam-Flag": "YES",
            "Auto-Submitted": "auto-generated",
            "Precedence": "bulk",
            "List-Unsubscribe": "<x>",
        }
    )
    assert filtro_cabeceras.motivo_omision(cab, CASA) is None


def test_cabeceras_traen_los_campos_extra():
    crudo = (
        b"From: Tienda <ventas@tienda.com>\r\nTo: x@example.org\r\nSubject: Oferta\r\nDate: Sun, 08 Nov 2026 10:00:00 -0500\r\n"
        b"X-Spam-Flag: YES\r\nPrecedence: bulk\r\nList-Unsubscribe: <mailto:baja@tienda.com>\r\n\r\n"
    )
    cab = texto.cabeceras(crudo)
    assert cab["extra"]["X-Spam-Flag"] == "YES"
    assert cab["extra"]["Precedence"] == "bulk"
    assert filtro_cabeceras.motivo_omision(cab, CASA) == "spam"


def test_recientes_solo_bandeja_y_enviados_y_uids_desde_uidnext():
    lista = [
        {"name": "INBOX", "imap_name": "INBOX", "delimiter": "."},
        {"name": "INBOX.Enviados", "imap_name": "INBOX.Enviados", "delimiter": "."},
        {"name": "INBOX.Proyectos", "imap_name": "INBOX.Proyectos", "delimiter": "."},
        {"name": "Sent", "imap_name": "Sent", "delimiter": "."},
    ]
    assert [c["name"] for c in recientes.carpetas_del_dia(lista)] == [
        "INBOX",
        "INBOX.Enviados",
        "Sent",
    ]
    assert recientes.uids_nuevos([5, 9, 12, 20], 10) == [20, 12]
    assert recientes.uids_nuevos([5, 9], None) == []


class _BD:
    def __init__(self):
        self.consultas = []

    async def execute(self, sql, *args):
        self.consultas.append((sql, args))
        return "DELETE 2"


def test_eliminar_quita_del_indice_solo_en_acciones_que_sacan_el_correo():
    bd = _BD()
    n = asyncio.run(eliminar.tras_accion(bd, "u@example.org", "INBOX", [7, 8], "move"))
    assert n == 2 and len(bd.consultas) == 2 and bd.consultas[0][1][2] == ["7", "8"]
    bd = _BD()
    assert (
        asyncio.run(
            eliminar.tras_accion(bd, "u@example.org", "INBOX", [7], "mark_read")
        )
        == 0
    )
    assert bd.consultas == []
