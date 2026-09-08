# -*- coding: utf-8 -*-
"""El motivo que se cuenta a la persona tiene que ser el de verdad."""
from interfaces import motivos_contacto as m


def test_bloqueo_dice_lo_que_es():
    assert m.mensaje("bloqueo") == "No puedes chatear con esta persona."
    assert m.es_fallo_nuestro("bloqueo") is False


def test_no_poder_comprobar_no_se_disfraza_de_bloqueo():
    """El caso que reportó Andes: con la base caída se acusaba a la persona."""
    texto = m.mensaje("tenant_no_consultable")
    assert "no se pudo comprobar" in texto.lower()
    assert "no puedes chatear con esta persona" not in texto.lower()
    assert m.es_fallo_nuestro("tenant_no_consultable") is True


def test_otra_organizacion_y_uno_mismo():
    assert "otra organización" in m.mensaje("otra_organizacion")
    assert "contigo" in m.mensaje("mismo_usuario")


def test_motivo_desconocido_no_inventa_culpables():
    for valor in ("", None, "loquesea"):
        texto = m.mensaje(valor)
        assert texto == "No se pudo empezar la conversación."
        assert m.es_fallo_nuestro(valor) is False
