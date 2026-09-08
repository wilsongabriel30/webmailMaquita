# -*- coding: utf-8 -*-
"""N-28: el aviso llega a la persona, no solo a quien tiene la conversación abierta."""
from interfaces.websocket.aviso_personal import (  # noqa: E402
    RESUMEN_MAX, cuerpo_aviso, destinatarios, emitir, remitente_de,
)


class SocketFalso:
    def __init__(self):
        self.emitidos = []

    def emit(self, evento, datos, room=None):
        self.emitidos.append((evento, datos, room))


def participante(uid, activo=True, silenciado=False):
    return {"user_id": uid, "is_active": activo, "is_muted": silenciado}


# --- a quién se avisa ---------------------------------------------------------------------
def test_no_se_avisa_a_quien_escribe():
    gente = destinatarios([participante(1), participante(2)], remitente_id=1)
    assert gente == [2]


def test_el_remitente_puede_venir_como_texto():
    assert destinatarios([participante(1), participante(2)], remitente_id="1") == [2]


def test_silenciado_no_recibe_aviso():
    gente = destinatarios([participante(1), participante(2, silenciado=True)], remitente_id=1)
    assert gente == []


def test_quien_salio_de_la_conversacion_no_recibe():
    gente = destinatarios([participante(1), participante(3, activo=False)], remitente_id=1)
    assert gente == []


def test_grupo_avisa_a_todos_menos_al_que_escribe():
    gente = destinatarios([participante(i) for i in (1, 2, 3, 4)], remitente_id=3)
    assert gente == [1, 2, 4]


def test_sin_participantes_no_falla():
    assert destinatarios(None, remitente_id=1) == []
    assert destinatarios([], remitente_id=1) == []


# --- qué se manda -------------------------------------------------------------------------
def test_remitente_desde_cualquiera_de_los_formatos():
    assert remitente_de({"remitente_id": 7}) == 7
    assert remitente_de({"remitente": {"id": 8}}) == 8
    assert remitente_de({"sender_id": 9}) == 9
    assert remitente_de({}) is None


def test_el_resumen_se_recorta():
    largo = "x" * 500
    cuerpo = cuerpo_aviso(12, {"contenido": largo, "remitente": {"id": 3, "nombre": "ANA"}})
    assert len(cuerpo["content"]) == RESUMEN_MAX
    assert cuerpo["sender_name"] == "ANA"
    assert cuerpo["conversation_id"] == 12


def test_archivo_sin_texto_dice_algo_util():
    cuerpo = cuerpo_aviso(3, {"tipo": "file", "remitente": {"id": 1, "nombre": "LUIS"}})
    assert cuerpo["content"] == "Te ha enviado un archivo"


# --- emisión ------------------------------------------------------------------------------
def test_emite_a_la_sala_personal_de_cada_destinatario():
    s = SocketFalso()
    gente = emitir(s, 42, {"remitente_id": 1, "contenido": "hola"},
                   lambda cid: [participante(1), participante(2), participante(5)])
    assert gente == [2, 5]
    salas = sorted(r for _, _, r in s.emitidos)
    assert salas == ["user_2", "user_5"]
    assert all(ev == "aviso_chat" for ev, _, _ in s.emitidos)


def test_conversacion_a_solas_consigo_mismo_no_emite():
    s = SocketFalso()
    assert emitir(s, 1, {"remitente_id": 1}, lambda cid: [participante(1)]) == []
    assert s.emitidos == []


def test_si_falla_la_consulta_no_revienta_ni_emite():
    """La entrega del mensaje ya ocurrió: un aviso que falla no puede tumbarla."""
    s = SocketFalso()
    def revienta(cid):
        raise RuntimeError("base caída")
    vistos = []
    assert emitir(s, 1, {"remitente_id": 1}, revienta, registrar_error=vistos.append) == []
    assert s.emitidos == []
    assert len(vistos) == 1


def test_sin_socket_no_hace_nada():
    assert emitir(None, 1, {}, lambda cid: [participante(2)]) == []
