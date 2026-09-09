# -*- coding: utf-8 -*-
"""Con la base caída no se acusa a nadie de bloquear (re-verificación de Andes).

Su prueba fue por el camino real: WebSocket con postgres parado. El texto decía «No puedes
chatear con esta persona» y el motivo era «bloqueo», que apunta a una decisión de personas que
nunca ocurrió.
"""
import pytest

from interfaces import motivos_contacto as m
from interfaces import relacion_chat as r


class SesionRota:
    """Una sesión de base que revienta, como cuando postgres no está."""

    def query(self, *a, **k):
        raise RuntimeError("connection refused")


def test_la_comprobacion_avisa_de_que_no_pudo_saber():
    with pytest.raises(r.NoConsultable):
        r.bloqueo_entre(SesionRota(), 1, 2)


def test_el_motivo_no_es_bloqueo_sino_no_consultable(monkeypatch):
    monkeypatch.setattr(r, "bloqueo_entre", lambda s, a, b: (_ for _ in ()).throw(r.NoConsultable("x")))
    import tenant_chat
    monkeypatch.setattr(tenant_chat, "primer_bloqueado", lambda *a, **k: None)
    ok, motivo = r.puede_contactar(object(), 1, 2)
    assert ok is False
    assert motivo == "bloqueo_no_consultable"


def test_el_texto_no_acusa_de_bloqueo_y_se_puede_reintentar():
    texto = m.mensaje("bloqueo_no_consultable")
    assert "no se pudo comprobar" in texto.lower()
    assert "no puedes chatear con esta persona" not in texto.lower()
    assert m.es_fallo_nuestro("bloqueo_no_consultable") is True


def test_un_bloqueo_de_verdad_sigue_diciendose_tal_cual():
    assert m.mensaje("bloqueo") == "No puedes chatear con esta persona."
    assert m.es_fallo_nuestro("bloqueo") is False
