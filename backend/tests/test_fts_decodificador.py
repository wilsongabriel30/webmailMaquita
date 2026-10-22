"""Decodificador de adjuntos del índice de texto completo (deploy/dovecot/fts/decodificador).

Los archivos de ejemplo se generan aquí mismo: DOCX, XLSX, PPTX, ODT, RTF, HTML, ZIP, TAR, tar.gz y,
si las herramientas están instaladas, PDF y 7z. También las trampas: bomba ZIP, ZIP que miente sobre
su tamaño, demasiados niveles, demasiados archivos, entidades XML y ejecutables disfrazados.
"""

import io
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "deploy",
    "dovecot",
    "fts",
    "decodificador",
)
sys.path.insert(0, _DIR)

import decodificar as dec  # noqa: E402
import limites  # noqa: E402
import tipos  # noqa: E402


def _texto(datos, declarado="application/octet-stream", tmp=None, **cambios):
    lim = limites.Limites(**cambios)
    texto, avisos = dec.decodificar_bytes(datos, declarado, lim, str(tmp))
    return texto, avisos


def _zip(miembros, metodo=zipfile.ZIP_DEFLATED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", metodo) as z:
        for nombre, contenido in miembros.items():
            z.writestr(nombre, contenido)
    return b.getvalue()


def _docx(texto):
    return _zip(
        {
            "[Content_Types].xml": "<Types/>",
            "word/document.xml": '<w:document xmlns:w="urn:w"><w:body><w:p><w:r><w:t>'
            + texto
            + "</w:t></w:r></w:p></w:body></w:document>",
            "word/vbaProject.bin": b"Sub AutoOpen() Shell(\"calc\") End Sub",
            "docProps/core.xml": '<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc">'
            "<dc:title>Informe anual</dc:title><dc:creator>Tesorería</dc:creator></cp:coreProperties>",
        }
    )


def test_lista_de_formatos_para_dovecot():
    lista = tipos.lista_para_dovecot()
    assert "application/pdf pdf\n" in lista
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document docx" in lista
    assert "application/x-7z-compressed 7z" in lista
    assert lista.endswith("\n\n")  # Dovecot espera una línea vacía al final de la lista
    for linea in lista.strip().splitlines():
        assert len(linea.split(" ")) >= 2


def test_docx_texto_y_metadatos_sin_macros(tmp_path):
    texto, _ = _texto(_docx("Factura número 123 de Riobamba"), tmp=tmp_path)
    assert "Factura número 123 de Riobamba" in texto
    assert "Informe anual" in texto and "Tesorería" in texto
    assert "AutoOpen" not in texto  # el VBA ni se lee


def test_xlsx_cadenas_y_numeros_sin_indices(tmp_path):
    datos = _zip(
        {
            "[Content_Types].xml": "<Types/>",
            "xl/sharedStrings.xml": '<sst xmlns="urn:s"><si><t>Presupuesto Cayambe</t></si></sst>',
            "xl/worksheets/sheet1.xml": '<worksheet xmlns="urn:s"><sheetData><row>'
            '<c t="s"><v>0</v></c><c><v>98765</v></c></row></sheetData></worksheet>',
        }
    )
    texto, _ = _texto(datos, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tmp_path)
    assert "Presupuesto Cayambe" in texto
    assert "98765" in texto
    assert "\n0\n" not in f"\n{texto}\n"  # el índice de la cadena compartida no es texto


def test_pptx_y_odt(tmp_path):
    pptx = _zip(
        {
            "[Content_Types].xml": "<Types/>",
            "ppt/slides/slide1.xml": '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><a:t>Cosecha de cacao</a:t></p:sld>',
        }
    )
    assert "Cosecha de cacao" in _texto(pptx, tmp=tmp_path)[0]
    odt = _zip(
        {
            "mimetype": "application/vnd.oasis.opendocument.text",
            "content.xml": '<office:document-content xmlns:office="urn:o" xmlns:text="urn:t"><office:body>'
            "<text:p>Acta de la <text:span>asamblea</text:span> general</text:p></office:body>"
            "</office:document-content>",
        }
    )
    assert "Acta de la asamblea general" in _texto(odt, "application/vnd.oasis.opendocument.text", tmp_path)[0]


def test_rtf_con_tildes_y_unicode(tmp_path):
    rtf = rb"{\rtf1\ansi{\fonttbl{\f0 Arial;}}{\*\generator X;}Se\'f1or Mu\u241?oz\par Reuni\'f3n}"
    texto, _ = _texto(rtf, "application/rtf", tmp_path)
    assert "Señor Muñoz" in texto and "Reunión" in texto
    assert "Arial" not in texto and "generator" not in texto


def test_html_sin_scripts(tmp_path):
    html = b"<html><head><title>Boletin</title><script>alert('x')</script></head><body><p>Feria &amp; mercado</p></body></html>"
    texto, _ = _texto(html, "text/html", tmp_path)
    assert "Feria & mercado" in texto and "Boletin" in texto
    assert "alert" not in texto


def test_zip_anidado_y_tar_gz(tmp_path):
    interior = _zip({"notas.txt": "clave de búsqueda interior"})
    exterior = _zip({"carpeta/interior.zip": interior, "otro.docx": _docx("contrato firmado")})
    texto, _ = _texto(exterior, "application/zip", tmp_path)
    assert "clave de búsqueda interior" in texto
    assert "contrato firmado" in texto
    assert "carpeta/interior.zip" in texto  # los nombres de archivo también se buscan

    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as tf:
        contenido = b"inventario de bodega"
        info = tarfile.TarInfo("datos/inventario.csv")
        info.size = len(contenido)
        tf.addfile(info, io.BytesIO(contenido))
        enlace = tarfile.TarInfo("enlace")
        enlace.type = tarfile.SYMTYPE
        enlace.linkname = "/etc/shadow"
        tf.addfile(enlace)
    texto, _ = _texto(b.getvalue(), "application/gzip", tmp_path)
    assert "inventario de bodega" in texto
    assert "root:" not in texto


def test_bomba_zip_rechazada(tmp_path):
    # 50 MB de ceros caben en unos 50 KB: la proporción delata la bomba.
    bomba = _zip({"ceros.txt": b"\0" * (50 * 1024 * 1024)})
    assert len(bomba) < 200 * 1024
    texto, avisos = _texto(bomba, "application/zip", tmp_path)
    assert "\0" not in texto
    assert any("bomba" in a for a in avisos)


def test_bomba_que_esquiva_la_proporcion_choca_con_el_presupuesto(tmp_path):
    # Muchos miembros «razonables» que en total pasan del máximo descomprimido.
    miembros = {f"parte{i}.txt": os.urandom(256 * 1024).hex() for i in range(8)}
    texto, avisos = _texto(_zip(miembros), "application/zip", tmp_path, max_descomprimido=1024 * 1024)
    assert any("límite de bytes descomprimidos" in a or "demasiado grande" in a for a in avisos)
    assert len(texto) < 2 * 1024 * 1024


def test_zip_que_miente_sobre_su_tamano(tmp_path):
    datos = bytearray(_zip({"a.txt": b"A" * 100000}))
    # El tamaño descomprimido declarado (cabecera local y directorio central) pasa a 10 bytes.
    for firma, desplazamiento in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        i = datos.find(firma)
        datos[i + desplazamiento : i + desplazamiento + 4] = (10).to_bytes(4, "little")
    texto, avisos = _texto(bytes(datos), "application/zip", tmp_path, max_ratio=100000)
    assert "A" * 1000 not in texto
    assert avisos


def test_profundidad_maxima(tmp_path):
    datos = _zip({"fondo.txt": "tesoro escondido"})
    for i in range(5):
        datos = _zip({f"nivel{i}.zip": datos})
    texto, avisos = _texto(datos, "application/zip", tmp_path, max_profundidad=3)
    assert "tesoro escondido" not in texto
    assert any("niveles" in a for a in avisos)
    texto, _ = _texto(datos, "application/zip", tmp_path, max_profundidad=5)
    assert "tesoro escondido" not in texto  # 6 niveles: tampoco con el tope duro
    poco = _zip({"n.zip": _zip({"fondo.txt": "tesoro escondido"})})
    assert "tesoro escondido" in _texto(poco, "application/zip", tmp_path)[0]


def test_demasiados_miembros(tmp_path):
    datos = _zip({f"f{i}.txt": "x" for i in range(50)})
    _, avisos = _texto(datos, "application/zip", tmp_path, max_miembros=10)
    assert any("demasiados archivos" in a for a in avisos)


def test_entidades_xml_descartadas(tmp_path):
    risa = (
        '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "jajaja"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        '<w:document xmlns:w="urn:w"><w:p><w:t>&b;</w:t></w:p></w:document>'
    )
    datos = _zip({"[Content_Types].xml": "<Types/>", "word/document.xml": risa})
    texto, _ = _texto(datos, tmp=tmp_path)
    assert "jajaja" not in texto


def test_el_contenido_manda_sobre_el_tipo_declarado(tmp_path):
    # Un «PDF» que es un DOCX se lee como DOCX; un ejecutable disfrazado no se abre.
    assert "disfrazado" in _texto(_docx("disfrazado"), "application/pdf", tmp_path)[0]
    assert _texto(b"MZ\x90\x00" + b"\0" * 100, "application/pdf", tmp_path)[0] == ""
    assert tipos.decidir("application/zip", b"\x7fELF\x02\x01") is None


def test_limite_de_texto(tmp_path):
    texto, avisos = _texto(_docx("palabra " * 5000), tmp=tmp_path, max_texto=1000)
    assert len(texto) <= 1000
    assert any("máximo de texto" in a for a in avisos)


def test_configuracion_con_topes(tmp_path):
    conf = tmp_path / "decodificador.conf"
    conf.write_text("MAX_ENTRADA_MB=99999\nOCR=1\nMAX_PROFUNDIDAD=2\nrm -rf /\nMAX_MIEMBROS=abc\n")
    lim = limites.cargar(str(conf))
    assert lim.max_entrada == 200 * limites.MB  # tope duro
    assert lim.ocr == 1 and lim.max_profundidad == 2
    assert lim.max_miembros == limites.Limites().max_miembros
    assert limites.cargar(str(tmp_path / "no-existe")).ocr == 0


def test_entrada_demasiado_grande_y_sin_argumentos(tmp_path, monkeypatch):
    conf = tmp_path / "c.conf"
    conf.write_text("MAX_ENTRADA_MB=1\n")
    entorno = dict(os.environ, MAQUITA_FTS_CONF=str(conf), TMPDIR=str(tmp_path))
    programa = os.path.join(_DIR, "decodificar.py")
    r = subprocess.run([sys.executable, "-I", programa], capture_output=True, env=entorno, timeout=30, check=False)
    assert r.returncode == 0 and b"application/pdf pdf" in r.stdout
    r = subprocess.run(
        [sys.executable, "-I", programa, "application/zip"],
        input=b"PK\x03\x04" + b"\0" * (2 * 1024 * 1024),
        capture_output=True,
        env=entorno,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0 and r.stdout == b"" and b"MB" in r.stderr
    r = subprocess.run(
        [sys.executable, "-I", programa, "application/octet-stream"],
        input=_docx("por la tubería"),
        capture_output=True,
        env=entorno,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0 and "por la tubería" in r.stdout.decode()


_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 100]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 10 50 Td (Acta de entrega) Tj ET\nendstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="sin poppler-utils")
def test_pdf_con_pdftotext(tmp_path):
    texto, _ = _texto(_PDF, "application/pdf", tmp_path)
    assert "Acta de entrega" in texto
    # Un PDF dentro de un ZIP también.
    assert "Acta de entrega" in _texto(_zip({"acta.pdf": _PDF}), "application/zip", tmp_path)[0]


@pytest.mark.skipif(not shutil.which("7z"), reason="sin 7zip")
def test_siete_z(tmp_path):
    (tmp_path / "dentro.txt").write_text("informe de siete zip")
    archivo = tmp_path / "a.7z"
    subprocess.run(["7z", "a", "-bd", str(archivo), str(tmp_path / "dentro.txt")], capture_output=True, check=True)
    texto, _ = _texto(archivo.read_bytes(), "application/x-7z-compressed", tmp_path)
    assert "informe de siete zip" in texto


@pytest.mark.skipif(not shutil.which("exiftool"), reason="sin exiftool")
def test_exif_de_imagen(tmp_path):
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
    ruta = tmp_path / "f.png"
    ruta.write_bytes(png)
    subprocess.run(["exiftool", "-q", "-overwrite_original", "-Title=Minga comunitaria", str(ruta)], check=True)
    texto, _ = _texto(ruta.read_bytes(), "image/png", tmp_path)
    assert "Minga comunitaria" in texto
