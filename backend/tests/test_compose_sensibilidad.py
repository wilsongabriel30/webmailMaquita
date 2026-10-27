"""El envío con etiqueta de sensibilidad no debe rechazarse por validación (27/10/2026).

ComposeRequest usa extra="forbid" y no declaraba `sensitivity`: todo correo con etiqueta
(Confidencial, Restringida, etc.) respondía 400 «Solicitud inválida».
"""

import pytest
from app.mail import sensitivity
from app.mail.schemas.messages import ComposeRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    "etiqueta", ["Publica", "Interna", "Confidencial", "Restringida"]
)
def test_compose_acepta_etiqueta(etiqueta):
    r = ComposeRequest(to=["alguien@gmail.com"], subject="Prueba", sensitivity=etiqueta)
    assert r.sensitivity == etiqueta


def test_compose_sin_etiqueta_sigue_funcionando():
    assert ComposeRequest(to=["alguien@gmail.com"], subject="Prueba").sensitivity == ""


def test_compose_rechaza_etiqueta_desmedida():
    with pytest.raises(ValidationError):
        ComposeRequest(to=["alguien@gmail.com"], subject="Prueba", sensitivity="x" * 21)


def test_confidencial_y_restringida_bloquean_externos():
    assert sensitivity.blocks_external("Confidencial")
    assert sensitivity.blocks_external("Restringida")
    assert not sensitivity.blocks_external("Interna")
