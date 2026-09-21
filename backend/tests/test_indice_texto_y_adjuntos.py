"""Cuentas con indice de texto y cabecera de descarga/vista previa de adjuntos."""

import importlib

from app.mail.routers.attachments import _content_disposition


def test_cuenta_indexada_lee_el_archivo_de_hechos(tmp_path, monkeypatch):
    hechos = tmp_path / "hechos.txt"
    hechos.write_text("Gerencia@MaquitaTurismo.com\n\notra@maquita.org\n")
    monkeypatch.setenv("FTS_HECHOS", str(hechos))
    import app.mail.services.indice_texto as m

    m = importlib.reload(m)
    assert m.cuenta_indexada("gerencia@maquitaturismo.com")
    assert not m.cuenta_indexada("nadie@maquita.org")
    assert not m.cuenta_indexada("")


def test_sin_archivo_de_hechos_nadie_esta_indexado(tmp_path, monkeypatch):
    monkeypatch.setenv("FTS_HECHOS", str(tmp_path / "no-existe.txt"))
    import app.mail.services.indice_texto as m

    m = importlib.reload(m)
    assert not m.cuenta_indexada("gerencia@maquitaturismo.com")


def test_cabecera_con_comilla_tipografica_cabe_en_latin1():
    # «Women’s Journey.pdf» daba 500 en la vista previa.
    cabecera = _content_disposition("MTWM26 – Women’s Journey.pdf", "inline")
    cabecera.encode("latin-1")
    assert cabecera.startswith("inline; ")
    assert "filename*=UTF-8" in cabecera


def test_cabecera_no_se_parte_con_saltos_de_linea():
    cabecera = _content_disposition("a\r\nX-Mala: 1.pdf")
    assert "\r" not in cabecera and "\n" not in cabecera


def test_capacidades_esta_montado_en_la_aplicacion():
    # El primer intento lo puso en un enrutador que nadie montaba y respondia 404.
    from app.main import app

    assert "/api/mail/search/capacidades" in {r.path for r in app.routes}
