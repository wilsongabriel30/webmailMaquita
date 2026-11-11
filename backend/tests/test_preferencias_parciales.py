"""Guardar un campo de las preferencias no pisa los demás (caso de Gerencia de Agro, 11/11/2026)."""

from app.settings import preferencias_parciales as pp
from app.settings.routers.preferences import UserSettings


def test_un_solo_campo_conserva_lo_guardado():
    body = UserSettings(reading_pane="fullscreen")
    guardado = {
        "display_name": "Larry Vera",
        "signature_html": "<p>Firma</p>",
        "messages_per_page": 100,
        "reading_pane": "right",
        "block_remote_images": True,
        "confirm_delete": False,
        "auto_reply_enabled": True,
        "auto_reply_subject": "Fuera de la oficina",
        "auto_reply_body": "Vuelvo el lunes",
        "acuse_lectura": "siempre",
        "vista": "{}",
    }
    pp.completar(body, guardado)
    assert body.reading_pane == "fullscreen"  # lo enviado manda
    assert body.display_name == "Larry Vera"
    assert body.messages_per_page == 100
    assert (
        body.auto_reply_enabled is True
        and body.auto_reply_subject == "Fuera de la oficina"
    )
    assert body.block_remote_images is True and body.confirm_delete is False
    assert body.acuse_lectura == "siempre"


def test_sin_fila_guardada_quedan_los_valores_por_defecto():
    body = UserSettings(reading_pane="bottom")
    pp.completar(body, None)
    assert body.messages_per_page == 50 and body.reading_pane == "bottom"


def test_vista_solo_claves_conocidas():
    limpia = pp.limpiar_vista(
        {
            "densidad": "linea",
            "lineas": 2,
            "anchoCarpetas": 310.6,
            "anchoLista": 999999,
            "otra": "x",
            "modo": True,
        }
    )
    assert limpia == {"densidad": "linea", "lineas": 2, "anchoCarpetas": 310}
    assert pp.limpiar_vista("no es un dict") == {}
