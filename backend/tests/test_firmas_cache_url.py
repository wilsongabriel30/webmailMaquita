"""Imágenes externas de la firma al ENVIAR: no se descargan en cada correo (15/11/2026).

Antes cada envío bajaba de la web todas las imágenes de la firma. Se comprueba que al enviar se
recuerdan por dirección, que al vencer se vuelven a bajar, que con la web caída se usa la última
copia buena y que al GUARDAR la firma se sigue descargando siempre.
"""

import io

import pytest
from PIL import Image

from app.mail import firmas, firmas_cache_url, firmas_imagenes

FIRMA = (
    '<p>Hola</p><div class="email-signature">'
    '<img src="https://ejemplo.test/logo.png" alt="Logo" width="200">'
    '<img src="https://ejemplo.test/icono.png" alt="Icono" width="23" height="23">'
    "</div>"
)


def _png(ancho, alto):
    salida = io.BytesIO()
    Image.new("RGBA", (ancho, alto), (10, 97, 161, 255)).save(salida, "PNG")
    return salida.getvalue()


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FIRMAS_DIR", str(tmp_path))
    estado = {"descargas": [], "caida": False}

    def falsa_descarga(url):
        estado["descargas"].append(url)
        if estado["caida"]:
            raise firmas_imagenes.ImagenRechazada("no se pudo descargar")
        return _png(800, 200) if "logo" in url else _png(92, 92)

    monkeypatch.setattr(firmas_imagenes, "descargar", falsa_descarga)
    return estado


def test_al_enviar_se_descarga_una_sola_vez(entorno):
    html1, adjuntos1, avisos1 = firmas.preparar_envio(FIRMA)
    assert len(entorno["descargas"]) == 2 and len(adjuntos1) == 2 and not avisos1
    html2, adjuntos2, avisos2 = firmas.preparar_envio(FIRMA)
    assert len(entorno["descargas"]) == 2  # el segundo envío no baja nada
    assert html2 == html1 and not avisos2
    assert [a["cid"] for a in adjuntos2] == [a["cid"] for a in adjuntos1]
    assert "https://" not in html2 and "cid:" in html2


def test_vencida_se_vuelve_a_descargar(entorno, monkeypatch):
    firmas.preparar_envio(FIRMA)
    monkeypatch.setattr(firmas_cache_url, "VIGENCIA_S", 0)
    firmas.preparar_envio(FIRMA)
    assert len(entorno["descargas"]) == 4


def test_web_caida_usa_la_ultima_copia_buena(entorno, monkeypatch):
    html1, adjuntos1, _ = firmas.preparar_envio(FIRMA)
    monkeypatch.setattr(firmas_cache_url, "VIGENCIA_S", 0)
    entorno["caida"] = True
    html2, adjuntos2, avisos2 = firmas.preparar_envio(FIRMA)
    assert html2 == html1 and len(adjuntos2) == 2 and not avisos2


def test_web_caida_sin_copia_quita_la_imagen_y_avisa(entorno):
    entorno["caida"] = True
    html, adjuntos, avisos = firmas.preparar_envio(FIRMA)
    assert not adjuntos and len(avisos) == 2 and "<img" not in html


def test_al_guardar_la_firma_se_descarga_siempre(entorno):
    firmas.preparar_envio(FIRMA)
    antes = len(entorno["descargas"])
    firmas.normalizar_firma(FIRMA)
    assert len(entorno["descargas"]) == antes + 2


def test_un_indice_danado_equivale_a_no_tenerlo(entorno, tmp_path):
    firmas.preparar_envio(FIRMA)
    for fichero in (tmp_path / ".direcciones").iterdir():
        fichero.write_text("esto no es json", encoding="utf-8")
    firmas.preparar_envio(FIRMA)
    assert len(entorno["descargas"]) == 4
