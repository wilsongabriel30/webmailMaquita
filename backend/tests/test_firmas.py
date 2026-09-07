"""Firmas: normalización automática (hallazgo de usuario del 07/09/2026, logos gigantes desde Zimbra).

Las dos firmas de `datos/` son la misma firma: la limpia y la que devolvió el editor de Zimbra
(entidades, `<br />`, `target`, comillas raras). Las imágenes remotas se sustituyen aquí por
imágenes generadas de tamaño grande: lo que se prueba es que salen del tamaño declarado.
"""

import io
import os

import pytest
from PIL import Image

from app.mail import firmas, firmas_imagenes

DATOS = os.path.join(os.path.dirname(__file__), "datos")

# Tamaño «real» de cada archivo remoto (mucho mayor que el declarado, como en el hallazgo).
TAMANOS = {"MAQUITAFIRMA1": (1206, 366), "WFTOFIRMA": (540, 200), "icon": (92, 92)}


def _png(ancho, alto, modo="RGBA"):
    salida = io.BytesIO()
    Image.new(
        modo, (ancho, alto), (10, 97, 161, 255) if modo == "RGBA" else (10, 97, 161)
    ).save(salida, "PNG")
    return salida.getvalue()


def _leer(nombre):
    with open(os.path.join(DATOS, nombre), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FIRMAS_DIR", str(tmp_path))
    descargas = []

    def falsa_descarga(url):
        descargas.append(url)
        for clave, (w, h) in TAMANOS.items():
            if clave in url:
                return _png(w, h)
        raise firmas_imagenes.ImagenRechazada("el servidor respondió 404")

    monkeypatch.setattr(firmas_imagenes, "descargar", falsa_descarga)
    return tmp_path, descargas


def _tamano_guardado(html, tmp_path, src_marca):
    import re

    for etiqueta in re.findall(r"<img[^>]*>", html):
        if f'alt="{src_marca}"' in etiqueta:
            m = re.search(r'src="/api/firmas/imagen/([0-9a-f]{32}\.png)"', etiqueta)
            assert m, etiqueta
            with Image.open(tmp_path / m.group(1)) as im:
                return im.size
    raise AssertionError(f"sin imagen con alt {src_marca}: {html}")


@pytest.mark.parametrize("fichero", ["firma_limpia.html", "firma_zimbra.html"])
def test_logo_sale_del_tamano_declarado(entorno, fichero):
    tmp_path, descargas = entorno
    r = firmas.normalizar_firma(_leer(fichero))
    assert 'width="201" height="61"' in r.html
    assert "width: 201px; height: 61px" in r.html
    assert _tamano_guardado(r.html, tmp_path, "Fundación Maquita") == (201, 61)
    assert _tamano_guardado(r.html, tmp_path, "WFTO") == (
        90,
        33,
    )  # sin height declarado: proporcional
    assert _tamano_guardado(r.html, tmp_path, "Facebook") == (23, 23)
    assert r.imagenes == 6 and len(descargas) == 6
    assert not r.avisos


def test_ninguna_url_externa_ni_data_sobrevive(entorno):
    r = firmas.normalizar_firma(_leer("firma_zimbra.html"))
    assert "<img" in r.html
    assert 'src="http' not in r.html and 'src="data:' not in r.html
    assert r.html.count('src="/api/firmas/imagen/') == 6
    assert "max-width: 100%; display: block" in r.html
    # Los enlaces sí siguen siendo externos: solo cambian las imágenes.
    assert 'href="https://maquita.com.ec/"' in r.html


def test_tablas_presentacion_y_ancho_fijo(entorno):
    r = firmas.normalizar_firma(
        '<table width="900"><tr><td style="margin:0 5px 0 0">x</td></tr></table>'
    )
    assert 'role="presentation"' in r.html
    assert 'width="600"' in r.html and "width: 600px; max-width: 100%" in r.html
    assert (
        'cellpadding="0"' in r.html
        and 'cellspacing="0"' in r.html
        and 'border="0"' in r.html
    )
    assert "padding: 0 5px 0 0" in r.html and "margin" not in r.html


def test_tabla_exterior_sin_ancho_lo_recibe_y_la_interior_no(entorno):
    r = firmas.normalizar_firma(
        "<table><tr><td><table><tr><td>a</td></tr></table></td></tr></table>"
    )
    assert r.html.count('width="600"') == 1


def test_mailto_incoherente_avisa(entorno):
    r = firmas.normalizar_firma(
        '<a href="mailto:otro@ejemplo.org">persona@ejemplo.org</a>'
    )
    assert (
        r.avisos
        and "otro@ejemplo.org" in r.avisos[0]
        and "persona@ejemplo.org" in r.avisos[0]
    )
    r2 = firmas.normalizar_firma(
        '<a href="mailto:otro@ejemplo.org">Escríbeme</a>',
        correo_usuario="yo@ejemplo.org",
    )
    assert r2.avisos and "no a tu dirección yo@ejemplo.org" in r2.avisos[0]
    r3 = firmas.normalizar_firma(
        '<a href="mailto:yo@ejemplo.org">yo@ejemplo.org</a>',
        correo_usuario="yo@ejemplo.org",
    )
    assert not r3.avisos


def test_plantilla_del_panel_conserva_marcadores(entorno):
    html = '<p>{{nombre}} – {{cargo}}</p><a href="mailto:{{email}}">{{email}}</a>'
    r = firmas.normalizar_firma(html)
    assert "{{nombre}}" in r.html and "mailto:{{email}}" in r.html and not r.avisos


def test_imagen_incrustada_pasa_a_archivo(entorno):
    import base64

    tmp_path, _ = entorno
    uri = "data:image/png;base64," + base64.b64encode(_png(800, 400)).decode()
    r = firmas.normalizar_firma(f'<img src="{uri}" width="200" alt="Logo">')
    assert "data:" not in r.html
    assert _tamano_guardado(r.html, tmp_path, "Logo") == (200, 100)


def test_imagen_que_falla_se_quita_y_se_avisa(entorno):
    r = firmas.normalizar_firma(
        '<p>Hola <img src="https://ejemplo.org/no-existe.png" width="100"> mundo</p>'
    )
    assert "<img" not in r.html and "Hola" in r.html and "mundo" in r.html
    assert r.avisos == [
        "Se quitó la imagen «https://ejemplo.org/no-existe.png»: el servidor respondió 404."
    ]


def test_red_interna_se_rechaza_sin_conectar(tmp_path, monkeypatch):
    monkeypatch.setenv("FIRMAS_DIR", str(tmp_path))
    for url in (
        "http://127.0.0.1/a.png",
        "http://10.0.0.5/a.png",
        "http://[::1]/a.png",
    ):
        with pytest.raises(firmas_imagenes.ImagenRechazada, match="red interna"):
            firmas_imagenes.descargar(url)


def test_no_se_amplia_y_el_maximo_es_600(entorno):
    tmp_path, _ = entorno
    chica = firmas_imagenes.guardar_redimensionada(_png(50, 20), 400)
    assert (chica.ancho, chica.alto) == (50, 20)
    grande = firmas_imagenes.guardar_redimensionada(_png(2000, 1000), 1500)
    assert (grande.ancho, grande.alto) == (600, 300)
    assert (tmp_path / grande.nombre).exists()


def test_mas_de_dos_mb_o_no_imagen_se_rechaza(entorno):
    with pytest.raises(firmas_imagenes.ImagenRechazada, match="2 MB"):
        firmas_imagenes.guardar_redimensionada(b"\x89" * (2 * 1024 * 1024 + 1), None)
    with pytest.raises(firmas_imagenes.ImagenRechazada, match="no es una imagen"):
        firmas_imagenes.guardar_redimensionada(b"<html>no soy png</html>", None)


def test_scripts_y_eventos_no_pasan(entorno):
    r = firmas.normalizar_firma(
        '<p onclick="x()">a</p><script>alert(1)</script><a href="javascript:1">b</a>'
    )
    assert (
        "script" not in r.html
        and "onclick" not in r.html
        and "javascript" not in r.html
    )


def test_idempotente(entorno):
    tmp_path, descargas = entorno
    primera = firmas.normalizar_firma(_leer("firma_zimbra.html"))
    n = len(descargas)
    segunda = firmas.normalizar_firma(primera.html)
    assert segunda.html == primera.html
    assert len(descargas) == n  # ya está en el servidor: no vuelve a descargar nada


def test_citado_solo_ajusta_tamano_sin_descargar(entorno):
    _, descargas = entorno
    html = '<blockquote><img src="https://otro.example/foto.jpg" width="1500"><img src="https://otro.example/b.png"></blockquote>'
    salida = firmas.normalizar_html_citado(html)
    assert "width: 1500px; max-width: 100%" in salida
    assert "height: auto; max-width: 100%" in salida
    assert 'src="https://otro.example/foto.jpg"' in salida and not descargas


def test_preparar_envio_firma_a_cid_y_citado_ajustado(entorno):
    tmp_path, _ = entorno
    firma = firmas.normalizar_firma(_leer("firma_limpia.html")).html
    cuerpo = (
        '<p>Hola</p><div class="email-signature">' + firma + "</div>"
        '<blockquote><img src="https://otro.example/foto.jpg" width="900"></blockquote>'
    )
    html, adjuntos, avisos = firmas.preparar_envio(cuerpo)
    assert not avisos
    # Seis imágenes en la firma, pero los cuatro iconos generados son idénticos: mismo contenido,
    # mismo archivo, un solo adjunto (el destinatario no recibe copias repetidas).
    assert len(adjuntos) == 3 and all(
        a["is_inline"] and a["content_type"] == "image/png" for a in adjuntos
    )
    assert html.count('src="cid:') == 6 and "/api/firmas/imagen/" not in html
    assert (
        "width: 900px; max-width: 100%" in html
    )  # el citado no se descarga, solo se acota
    with Image.open(io.BytesIO(adjuntos[0]["content"])) as im:
        assert im.width <= 600


def test_preparar_envio_sin_imagenes_no_toca_nada():
    html = "<p>Solo texto</p>"
    assert firmas.preparar_envio(html) == (html, [], [])
