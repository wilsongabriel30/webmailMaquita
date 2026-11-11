"""Nombres de carpeta que la API acepta (caso «1․Dirección», 11/11/2026)."""

from app.mail.nombre_carpeta import nombre_valido
from app.mail.routers import messages


def test_acepta_tildes_signos_y_el_punto_especial():
    for nombre in (
        "INBOX",
        "INBOX.1․Dirección",
        "INBOX.12_ Planificación.Procesos - MC",
        "INBOX.¿Pendientes? (2026) #1 'ya'",
        "Virtual.Todo",
        "INBOX.Año/Ñandú & Cía, S.A. @casa",
    ):
        assert nombre_valido(nombre), nombre
        assert messages._validate_folder(nombre) == nombre


def test_rechaza_lo_peligroso_para_imap():
    for nombre in (
        "",
        "   ",
        'INBOX"x',
        "INBOX\\x",
        "INBOX\r\nA1 LOGOUT",
        "INBOX.*",
        "INBOX.%",
        "a{3}",
        "x" * 201,
        "a\x00b",
    ):
        assert not nombre_valido(nombre), repr(nombre)
