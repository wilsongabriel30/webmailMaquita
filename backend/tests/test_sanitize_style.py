"""M-05 (cuarta revisión): el atributo style no puede cargar recursos ni ejecutar."""

from app.core.css import limpiar_estilo
from app.core.sanitize import sanitize_html


def test_background_image_url_no_sobrevive():
    html = '<p style="color: red; background-image: url(https://rastreador.example/px.gif)">hola</p>'
    limpio = sanitize_html(html)
    assert "url(" not in limpio and "rastreador" not in limpio
    assert "color: red" in limpio


def test_valores_peligrosos_se_descartan():
    assert limpiar_estilo("width: expression(alert(1))") is None
    assert limpiar_estilo("background: url(x)") is None
    assert limpiar_estilo("behavior: url(x.htc)") is None
    assert limpiar_estilo("position: fixed; color: blue") == "color: blue"
    assert limpiar_estilo("@import 'x.css'") is None


def test_propiedades_normales_se_conservan():
    assert limpiar_estilo("font-family: Arial; font-size: 12px; margin: 0 auto") == (
        "font-family: Arial; font-size: 12px; margin: 0 auto"
    )


def test_l04_atajo_font_fuera_pero_propiedades_sueltas_dentro():
    """L-04 (cuarta revisión): el atajo `font` no pasa; font-family/size/weight sí."""
    assert limpiar_estilo("font: 12px Arial; color: red") == "color: red"
    assert limpiar_estilo("font: caption") is None
    assert limpiar_estilo("font-family: Arial; font-weight: bold") == (
        "font-family: Arial; font-weight: bold"
    )
