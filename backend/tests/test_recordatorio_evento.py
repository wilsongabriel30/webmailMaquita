"""El recordatorio de un evento debe llevar el enlace de la reunión (27/10/2026).

Caso real: un buzón de ventas recibió «📅 Reunión … empieza a las 09:00» sin el enlace de
Google Meet, que estaba en el lugar y en la descripción del evento.
"""

from app.recordatorio_evento import contenido, enlace_reunion

DESCRIPCION_GOOGLE = (
    "-::~:~::~:~::-\n"
    "Unirse con Google Meet: https://meet.google.com/abc-defg-hij\n"
    "Más números de teléfono: https://tel.meet/abc-defg-hij?pin=1234567890&hs=7\n"
    "Más información sobre Meet: https://support.google.com/a/users/answer/9282720\n"
)


def test_enlace_desde_la_descripcion_de_google():
    assert (
        enlace_reunion("", DESCRIPCION_GOOGLE) == "https://meet.google.com/abc-defg-hij"
    )


def test_prefiere_videollamada_sobre_otros_enlaces():
    desc = (
        "Agenda: https://docs.ejemplo.com/a\nZoom: https://us02web.zoom.us/j/123?pwd=x."
    )
    assert enlace_reunion("", desc) == "https://us02web.zoom.us/j/123?pwd=x"


def test_sin_enlace():
    assert enlace_reunion("Sala de reuniones, Quito", "Traer informe") == ""


def test_contenido_lleva_enlace_y_horario():
    texto, html = contenido(
        "Reunión con proveedor",
        "09:00",
        "09:30",
        "https://meet.google.com/abc-defg-hij",
        DESCRIPCION_GOOGLE,
    )
    assert texto.splitlines()[0] == "📅 Reunión con proveedor empieza a las 09:00"
    assert "https://meet.google.com/abc-defg-hij" in texto
    assert "09:00–09:30" in texto
    assert 'href="https://meet.google.com/abc-defg-hij"' in html
    assert "Lugar:" not in texto  # el lugar es el mismo enlace: no se repite


def test_contenido_escapa_html_y_muestra_lugar_fisico():
    texto, html = contenido("<b>Comité</b>", "10:00", "", "Oficina <Quito>", "")
    assert "<b>" not in html and "&lt;b&gt;" in html
    assert "Lugar: Oficina <Quito>" in texto
    assert "Oficina &lt;Quito&gt;" in html


def test_aviso_de_pantalla_lleva_el_enlace_aparte():
    from datetime import datetime, timezone

    from app.reminders_scheduler import _contenido_evento

    fila = {
        "summary": "Reunión con proveedor",
        "location": "",
        "description": DESCRIPCION_GOOGLE,
    }
    inicio = datetime(2026, 10, 27, 14, 0, tzinfo=timezone.utc)
    texto, html, enlace = _contenido_evento(fila, inicio, None)
    assert enlace == "https://meet.google.com/abc-defg-hij"
    assert "09:00" in texto
