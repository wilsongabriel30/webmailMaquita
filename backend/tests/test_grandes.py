"""Correos más grandes (liberar espacio desde el Drive): parseo del FETCH (UID RFC822.SIZE)."""

from app.mail.routers.grandes import CARPETAS, _tamanos


def test_tamanos_en_los_dos_ordenes():
    lineas = [
        "1 FETCH (UID 41 RFC822.SIZE 1200)",
        "2 FETCH (RFC822.SIZE 99000 UID 42)",
        "3 FETCH (FLAGS (\\Seen))",
        ")",
    ]
    assert _tamanos(lineas) == [(41, 1200), (42, 99000)]


def test_mayores_primero():
    pares = _tamanos(
        [
            "1 FETCH (UID 1 RFC822.SIZE 5)",
            "2 FETCH (UID 2 RFC822.SIZE 50)",
            "3 FETCH (UID 3 RFC822.SIZE 500)",
        ]
    )
    assert sorted(pares, key=lambda x: x[1], reverse=True)[:2] == [(3, 500), (2, 50)]


def test_carpetas_principales():
    assert "INBOX" in CARPETAS and "Sent" in CARPETAS and "Trash" in CARPETAS
