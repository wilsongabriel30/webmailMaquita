"""Administrador de archivos de los sitios: rutas siempre dentro de la carpeta pública, papelera, «zip slip»,
bombas de descompresión y enlaces simbólicos (deploy/sitios/lib/archivos*.py). Sin root."""

import io
import os
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar, sitio  # noqa: E402

m = cargar()
ErrorSitio = m["comun"].ErrorSitio
ordenes = m["archivos_ordenes"]
zipmod = m["archivos_zip"]


@pytest.fixture
def meta(tmp_path, monkeypatch):
    datos = sitio(tmp_path, monkeypatch)
    monkeypatch.setattr(ordenes, "SUBIDAS", str(tmp_path / "subidas"))
    (tmp_path / "subidas").mkdir()
    (tmp_path / "fuera").mkdir()
    (tmp_path / "fuera" / "secreto.txt").write_text("no debe verse")
    publico = datos["publico"]
    os.makedirs(os.path.join(publico, "css"))
    with open(os.path.join(publico, "index.html"), "w") as f:
        f.write("<h1>Hola</h1>")
    return datos


D = "example.org"


@pytest.mark.parametrize("ruta", ["../", "..", "css/../../fuera", "/etc/passwd", "/", "a\\..\\b", "x\x00y", "css/..", ""])
def test_recorrido_rechazado(meta, ruta):
    with pytest.raises(ErrorSitio):
        ordenes.listar(D, ruta)


def test_listar_raiz_y_carpeta(meta):
    r = ordenes.listar(D, ".")
    assert [e["nombre"] for e in r["entradas"]] == ["css", "index.html"]
    assert r["entradas"][0]["tipo"] == "carpeta"
    assert ordenes.listar(D, "css")["entradas"] == []


def test_enlace_que_sale_rechazado(meta, tmp_path):
    publico = meta["publico"]
    os.symlink(str(tmp_path / "fuera"), os.path.join(publico, "salida"))
    os.symlink(str(tmp_path / "fuera" / "secreto.txt"), os.path.join(publico, "secreto.txt"))
    # Listar o atravesar el enlace: rechazado.
    with pytest.raises(ErrorSitio):
        ordenes.listar(D, "salida")
    with pytest.raises(ErrorSitio):
        ordenes.listar(D, "salida/otra")
    with pytest.raises(ErrorSitio):
        ordenes.descargar(D, "secreto.txt")
    with pytest.raises(ErrorSitio):
        ordenes.carpeta(D, "salida/nueva")
    assert not os.path.exists(tmp_path / "fuera" / "nueva")
    # En el listado se marca como enlace que sale; borrarlo quita el enlace, no lo apuntado.
    entradas = {e["nombre"]: e for e in ordenes.listar(D, ".")["entradas"]}
    assert entradas["salida"]["tipo"] == "enlace" and entradas["salida"]["fuera"] is True
    ordenes.borrar(D, "salida")
    assert (tmp_path / "fuera" / "secreto.txt").exists()


def test_subir_descargar_y_no_pisar_sin_permiso(meta, tmp_path):
    subida = tmp_path / "subidas" / ("a" * 32 + ".subida")
    subida.write_bytes(b"contenido")
    r = ordenes.subir(D, "css/estilo.css", subida.name)
    assert r["bytes"] == 9 and not subida.exists()  # la subida se borra siempre
    subida.write_bytes(b"otro")
    with pytest.raises(ErrorSitio):
        ordenes.subir(D, "css/estilo.css", subida.name)
    subida.write_bytes(b"otro")
    ordenes.subir(D, "css/estilo.css", subida.name, reemplazar=True)
    d = ordenes.descargar(D, "css/estilo.css")
    assert (tmp_path / "subidas" / d["archivo"]).read_bytes() == b"otro"
    with pytest.raises(ErrorSitio):
        ordenes.subir(D, "css/x", "../../etc/passwd")


def test_subir_sobre_enlace_rechazado(meta, tmp_path):
    os.symlink(str(tmp_path / "fuera" / "secreto.txt"), os.path.join(meta["publico"], "pisar.txt"))
    subida = tmp_path / "subidas" / ("b" * 32 + ".subida")
    subida.write_bytes(b"x")
    with pytest.raises(ErrorSitio):
        ordenes.subir(D, "pisar.txt", subida.name, reemplazar=True)
    assert (tmp_path / "fuera" / "secreto.txt").read_text() == "no debe verse"


def test_mover_copiar_permisos(meta):
    ordenes.carpeta(D, "nueva")
    ordenes.copiar(D, "index.html", "nueva/copia.html")
    ordenes.mover(D, "nueva/copia.html", "nueva/movida.html")
    assert os.path.isfile(os.path.join(meta["publico"], "nueva", "movida.html"))
    with pytest.raises(ErrorSitio):
        ordenes.mover(D, "nueva", "nueva/dentro")
    with pytest.raises(ErrorSitio):
        ordenes.mover(D, "index.html", "../index.html")
    with pytest.raises(ErrorSitio):
        ordenes.mover(D, ".", "otra")
    ordenes.permisos(D, "index.html", "600")
    assert oct(os.stat(os.path.join(meta["publico"], "index.html")).st_mode)[-3:] == "600"
    with pytest.raises(ErrorSitio):
        ordenes.permisos(D, "index.html", "777")


def test_papelera_y_recuperar(meta):
    r = ordenes.borrar(D, "index.html")
    assert not os.path.exists(os.path.join(meta["publico"], "index.html"))
    assert [e["ruta"] for e in ordenes.ver_papelera(D)["elementos"]] == ["index.html"]
    ordenes.recuperar(D, r["id"])
    assert os.path.isfile(os.path.join(meta["publico"], "index.html"))
    ordenes.borrar(D, "css")
    assert ordenes.vaciar(D)["vaciados"] == 1
    with pytest.raises(ErrorSitio):
        ordenes.borrar(D, ".")


def test_comprimir_y_descomprimir(meta):
    os.symlink("/etc/passwd", os.path.join(meta["publico"], "css", "enlace"))
    ordenes.comprimir(D, {"rutas": ["index.html", "css"], "destino": "todo.zip"})
    with zipfile.ZipFile(os.path.join(meta["publico"], "todo.zip")) as z:
        assert "css/enlace" not in z.namelist() and "index.html" in z.namelist()
    ordenes.carpeta(D, "extraido")
    r = ordenes.descomprimir(D, "todo.zip", "extraido")
    assert r["archivos"] == 1
    assert os.path.isfile(os.path.join(meta["publico"], "extraido", "index.html"))


def _zip(publico, nombre, miembros):
    with zipfile.ZipFile(os.path.join(publico, nombre), "w") as z:
        for n, datos in miembros:
            z.writestr(n, datos)


@pytest.mark.parametrize("malo", ["../fuera/x.txt", "/etc/cron.d/x", "a/../../x", "C:/x", "a\\..\\..\\x"])
def test_zip_slip_rechazado(meta, tmp_path, malo):
    _zip(meta["publico"], "malo.zip", [("bien.txt", "ok"), (malo, "mal")])
    with pytest.raises(ErrorSitio):
        ordenes.descomprimir(D, "malo.zip", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "bien.txt"))  # nada se escribe
    assert not os.path.exists(tmp_path / "fuera" / "x.txt")


def test_tar_con_enlace_rechazado(meta):
    ruta = os.path.join(meta["publico"], "enlace.tar.gz")
    with tarfile.open(ruta, "w:gz") as t:
        info = tarfile.TarInfo("salida")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc"
        t.addfile(info)
        datos = b"x"
        info = tarfile.TarInfo("salida/passwd")
        info.size = len(datos)
        t.addfile(info, io.BytesIO(datos))
    with pytest.raises(ErrorSitio):
        ordenes.descomprimir(D, "enlace.tar.gz", ".")
    assert not os.path.lexists(os.path.join(meta["publico"], "salida"))


def test_zip_con_enlace_rechazado(meta):
    ruta = os.path.join(meta["publico"], "enlace.zip")
    with zipfile.ZipFile(ruta, "w") as z:
        info = zipfile.ZipInfo("salida")
        info.external_attr = (0o120777 << 16)
        z.writestr(info, "/etc/passwd")
    with pytest.raises(ErrorSitio):
        ordenes.descomprimir(D, "enlace.zip", ".")


def test_bomba_rechazada(meta, monkeypatch):
    monkeypatch.setattr(zipmod, "TOPE_BYTES", 1024 * 1024)
    _zip(meta["publico"], "bomba.zip", [("ceros.bin", b"\0" * (2 * 1024 * 1024))])
    with pytest.raises(ErrorSitio, match="1 GB"):
        ordenes.descomprimir(D, "bomba.zip", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "ceros.bin"))


def test_bomba_que_miente_en_su_tamano(meta, monkeypatch):
    """Un .zip que declara menos de lo que ocupa: se corta al escribir y no queda el archivo a medias."""
    ruta = os.path.join(meta["publico"], "mentira.zip")
    _zip(meta["publico"], "mentira.zip", [("ceros.bin", b"\0" * 100000)])
    original = zipfile.ZipFile.infolist

    def infolist(self):
        lista = original(self)
        for i in lista:
            i.file_size = 10
        return lista

    monkeypatch.setattr(zipfile.ZipFile, "infolist", infolist)
    with pytest.raises(ErrorSitio):
        ordenes.descomprimir(D, "mentira.zip", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "ceros.bin"))
    assert os.path.exists(ruta)


def test_demasiados_archivos(meta, monkeypatch):
    monkeypatch.setattr(zipmod, "TOPE_ARCHIVOS", 5)
    _zip(meta["publico"], "muchos.zip", [(f"a{i}.txt", "x") for i in range(10)])
    with pytest.raises(ErrorSitio):
        ordenes.descomprimir(D, "muchos.zip", ".")
