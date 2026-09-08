# -*- coding: utf-8 -*-
"""N-29: el primer mensaje de una conversación recién creada no puede perderse, y la
comprobación de acceso sigue siendo estricta para quien no participa."""
from interfaces.websocket.participacion import es_participante  # noqa: E402


def ve(resultado):
    return lambda cid, uid: resultado


def base(resultado):
    return lambda cid, uid: resultado


def revienta(*_a, **_k):
    raise RuntimeError("base caída")


def test_el_servicio_lo_ve():
    assert es_participante(58, 189, ve({"id": 58}), base(False)) is True


def test_no_consulta_la_base_si_el_servicio_ya_lo_vio():
    llamadas = []

    def base_espia(cid, uid):
        llamadas.append((cid, uid))
        return False

    assert es_participante(58, 189, ve({"id": 58}), base_espia) is True
    assert llamadas == []


def test_conversacion_recien_creada_la_confirma_la_base():
    """El caso real: el servicio aún no la ve y la base sí. El mensaje debe salir."""
    assert es_participante(58, 189, ve(None), base(True)) is True


def test_quien_no_participa_sigue_sin_entrar():
    assert es_participante(58, 999, ve(None), base(False)) is False


def test_si_el_servicio_revienta_manda_la_base():
    assert es_participante(58, 189, revienta, base(True)) is True
    assert es_participante(58, 999, revienta, base(False)) is False


def test_si_la_base_revienta_la_respuesta_es_no():
    """Fallo cerrado: sin poder confirmar, no se deja escribir."""
    assert es_participante(58, 189, ve(None), revienta) is False


def test_se_puede_registrar_lo_que_pasa():
    apuntes = []
    es_participante(58, 189, ve(None), base(True), registrar=lambda que, e: apuntes.append(que))
    assert "recien_creada" in apuntes

    apuntes.clear()
    es_participante(58, 189, revienta, base(True), registrar=lambda que, e: apuntes.append(que))
    assert "servicio" in apuntes
