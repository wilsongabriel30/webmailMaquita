"""«No es spam» deja al remitente en la lista de confianza del usuario."""

from app.mail.services.confianza_auto import fusionar, remitentes_de


def _msg(remitente: str) -> bytes:
    return f"From: {remitente}\nTo: yo@example.org\nSubject: x\n\ncuerpo\n".encode()


def test_extrae_el_remitente_sin_repetir():
    crudos = [_msg("Sofía <Sofia@Socio.Example>"), _msg("sofia@socio.example"), _msg("ventas@casa.example")]
    assert remitentes_de(crudos, "yo@example.org") == ["sofia@socio.example", "ventas@casa.example"]


def test_no_agrega_al_propio_usuario_ni_direcciones_rotas():
    crudos = [_msg("Yo <yo@example.org>"), _msg("sin-arroba"), _msg(""), b"basura sin cabeceras"]
    assert remitentes_de(crudos, "yo@example.org") == []


def test_fusion_respeta_el_maximo_y_no_duplica():
    assert fusionar(["b@x.example"], ["a@x.example", "b@x.example"], 200) == ["a@x.example", "b@x.example"]
    assert fusionar(["a@x.example", "b@x.example"], ["c@x.example"], 2) == ["a@x.example", "b@x.example"]
