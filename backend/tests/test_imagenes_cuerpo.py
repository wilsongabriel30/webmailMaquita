"""Imágenes pegadas en el cuerpo: salen como partes inline con cid, no como data:."""

import base64
import io

from PIL import Image

from app.mail.imagenes_cuerpo import incrustar_imagenes_data


def _png() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_imagen_pegada_pasa_a_cid_y_conserva_tamano():
    html = f"<p><img src=\"data:image/png;base64,{_png()}\" width=\"300\"></p>"
    salida, adjuntos = incrustar_imagenes_data(html)
    assert "data:" not in salida and "cid:" in salida and "width=\"300\"" in salida
    assert len(adjuntos) == 1
    assert adjuntos[0]["is_inline"] and adjuntos[0]["content_type"] == "image/png"
    assert "cid:" + adjuntos[0]["cid"] in salida


def test_misma_imagen_dos_veces_un_solo_adjunto():
    img = f"<img src=\"data:image/png;base64,{_png()}\">"
    _, adjuntos = incrustar_imagenes_data(img + img)
    assert len(adjuntos) == 1


def test_tipos_no_permitidos_y_base64_roto_quedan_igual():
    svg = "<img src=\"data:image/svg+xml;base64,PHN2Zz4=\">"
    roto = "<img src=\"data:image/png;base64,@@@\">"
    assert incrustar_imagenes_data(svg) == (svg, [])
    assert incrustar_imagenes_data(roto) == (roto, [])


def test_sin_imagenes_no_toca_nada():
    assert incrustar_imagenes_data("<p>hola</p>") == ("<p>hola</p>", [])
