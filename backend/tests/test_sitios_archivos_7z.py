"""Descomprimir .7z y .rar con 7-Zip desde el administrador de archivos y «Subir y migrar» (deploy/sitios/lib/archivos_7z.py):
mismas reglas que los .zip (sin enlaces, sin contraseña, topes de elementos y de bytes, nada se escribe si algo falla), el
proceso 7z con RLIMIT_FSIZE y el aviso claro cuando el servidor no tiene el códec de RAR (7zip-rar, non-free).
Necesita el ejecutable 7z (paquete «7zip»); si no está, se omiten. Los .rar solo se pueden crear con software propietario:
se prueban con .7z, que pasa por el mismo código (7z reconoce el formato por el contenido, no por la extensión)."""

import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar_mas, sitio  # noqa: E402

m = cargar_mas("paquete", "aplicaciones", "migracion", "sitio", "apps.descargas", "apps.receta")
ErrorSitio = m["comun"].ErrorSitio
ordenes = m["archivos_ordenes"]
zipmod = m["archivos_zip"]
siete = m["archivos_7z"]
paquete = m["paquete"]

pytestmark = pytest.mark.skipif(not siete.disponible(), reason="sin 7z en este equipo")
D = "example.org"


@pytest.fixture
def meta(tmp_path, monkeypatch):
    datos = sitio(tmp_path, monkeypatch)
    monkeypatch.setattr(ordenes, "SUBIDAS", str(tmp_path / "subidas"))
    (tmp_path / "subidas").mkdir()
    (tmp_path / "fuera").mkdir()
    return datos


def _7z(destino, carpeta, *extra):
    """Crea `destino` (siempre en formato 7z, aunque se llame .rar) con el contenido de `carpeta` (rutas relativas a ella)."""
    subprocess.run([siete.EJECUTABLE, "a", "-t7z", "-bso0", "-bse0", *extra, "--", destino, "."], cwd=carpeta, check=True)


def _fuente(tmp_path, archivos):
    carpeta = tmp_path / "fuente"
    for nombre, datos in archivos:
        ruta = carpeta / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos if isinstance(datos, bytes) else datos.encode())
    return str(carpeta)


def test_descomprimir_7z(meta, tmp_path):
    fuente = _fuente(tmp_path, [("index.html", "<h1>Hola</h1>"), ("css/estilo.css", "body{}"), ("img/a.bin", b"\0" * 5000)])
    _7z(os.path.join(meta["publico"], "sitio.7z"), fuente)
    ordenes.carpeta(D, "extraido")
    r = ordenes.descomprimir(D, "sitio.7z", "extraido")
    assert r["archivos"] == 3
    salida = os.path.join(meta["publico"], "extraido")
    assert open(os.path.join(salida, "index.html")).read() == "<h1>Hola</h1>"
    assert os.path.getsize(os.path.join(salida, "img", "a.bin")) == 5000
    assert not [n for n in os.listdir(salida) if n.startswith(".descomprimiendo-")]  # la carpeta temporal se borra


def test_7z_con_enlace_rechazado(meta, tmp_path):
    fuente = _fuente(tmp_path, [("bien.txt", "ok")])
    os.symlink("/etc/passwd", os.path.join(fuente, "enlace"))
    _7z(os.path.join(meta["publico"], "enlace.7z"), fuente, "-snl")  # -snl guarda el enlace como enlace
    with pytest.raises(ErrorSitio, match="enlace"):
        ordenes.descomprimir(D, "enlace.7z", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "bien.txt"))  # nada se escribe


def test_7z_con_contrasena_rechazado(meta, tmp_path):
    fuente = _fuente(tmp_path, [("secreto.txt", "x")])
    _7z(os.path.join(meta["publico"], "cifrado.7z"), fuente, "-pclave123", "-mhe=on")
    with pytest.raises(ErrorSitio, match="contraseña|dañado"):
        ordenes.descomprimir(D, "cifrado.7z", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "secreto.txt"))


def test_7z_demasiados_elementos(meta, tmp_path, monkeypatch):
    monkeypatch.setattr(zipmod, "TOPE_ARCHIVOS", 2)
    fuente = _fuente(tmp_path, [("a.txt", "1"), ("b.txt", "2"), ("c.txt", "3")])
    _7z(os.path.join(meta["publico"], "muchos.7z"), fuente)
    with pytest.raises(ErrorSitio, match="elementos"):
        ordenes.descomprimir(D, "muchos.7z", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "a.txt"))


def test_7z_bomba_declarada_rechazada(meta, tmp_path, monkeypatch):
    monkeypatch.setattr(zipmod, "TOPE_BYTES", 1024 * 1024)
    fuente = _fuente(tmp_path, [("ceros.bin", b"\0" * (2 * 1024 * 1024))])
    _7z(os.path.join(meta["publico"], "bomba.7z"), fuente)
    with pytest.raises(ErrorSitio, match="1 GB"):
        ordenes.descomprimir(D, "bomba.7z", ".")
    assert not os.path.exists(os.path.join(meta["publico"], "ceros.bin"))


def test_medir_y_extraer_a(tmp_path):
    fuente = _fuente(tmp_path, [("sitio/index.html", "<p>x</p>"), ("sitio/css/a.css", "a{}")])
    paquete = str(tmp_path / "paquete.7z")
    _7z(paquete, fuente)
    total, cuantos = siete.medir(paquete)
    assert total == len("<p>x</p>") + len("a{}") and cuantos == 4  # 2 carpetas + 2 archivos
    destino = str(tmp_path / "destino")
    nombres = siete.extraer_a(paquete, destino, lambda n: ".." not in n and not n.startswith("/"), 10 * 1024 * 1024, 1000)
    assert "sitio/index.html" in nombres
    assert open(os.path.join(destino, "sitio", "index.html")).read() == "<p>x</p>"
    with pytest.raises(ErrorSitio, match="elementos"):
        siete.extraer_a(paquete, str(tmp_path / "otro"), lambda n: True, 10 * 1024 * 1024, 1)


def test_extraer_a_rechaza_rutas_peligrosas(tmp_path):
    fuente = _fuente(tmp_path, [("bien.txt", "ok")])
    paquete = str(tmp_path / "p.7z")
    _7z(paquete, fuente)
    with pytest.raises(ErrorSitio, match="rutas"):
        siete.extraer_a(paquete, str(tmp_path / "d"), lambda n: False, 10 * 1024 * 1024, 1000)
    assert not os.path.exists(tmp_path / "d" / "bien.txt")


def test_sin_7z_mensaje_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(siete, "EJECUTABLE", None)
    with pytest.raises(ErrorSitio, match="7-Zip"):
        siete.listar(str(tmp_path / "x.7z"))


def test_es_7z():
    assert siete.es_7z("sitio.RAR") and siete.es_7z("a/b/c.7z") and not siete.es_7z("sitio.zip")
    assert siete.es_rar("Sitio.RAR") and not siete.es_rar("sitio.7z")
    assert shutil.which("7z") is None or siete.disponible()


# --- .rar: el paquete 7zip de Debian lista el formato pero el códec va aparte (7zip-rar, non-free) ---

INFORME_SIN_RAR = """7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03

Libs:
 0  /usr/lib/7zip/7z.so

Formats:
 0  ...F..................  Rar      rar r00       R a r ! 1A 07 00
 0  ...F..................  Rar5     rar r00       R a r ! 1A 07 01 00
 0  CK..........M.........  7z       7z            7 z BC AF 27 1C

Codecs:
 0  ED     40202 BZip2
 0  ED        21 LZMA2
"""
INFORME_CON_RAR = INFORME_SIN_RAR.replace("Codecs:\n", "Codecs:\n 1  .D     40301 Rar1\n 1  .D     40302 Rar2\n 1  .D     40305 Rar5\n")


def test_hay_codec_rar_se_lee_de_codecs_no_de_formats():
    assert not siete._hay_codec_rar(INFORME_SIN_RAR)  # «Formats» lista Rar aunque falte el códec
    assert siete._hay_codec_rar(INFORME_CON_RAR)
    assert siete._hay_codec_rar(INFORME_SIN_RAR.replace("Libs:\n", "Libs:\n 1  /usr/lib/7zip/Codecs/Rar.so\n"))
    assert siete._hay_codec_rar("") is False


def test_soporta_rar_pregunta_a_7z_una_sola_vez(monkeypatch):
    llamadas = []

    class R:
        stdout = INFORME_CON_RAR

    monkeypatch.setattr(siete, "_rar", None)
    monkeypatch.setattr(siete, "_correr", lambda args, tiempo, preparar=None: llamadas.append(args) or R())
    assert siete.soporta_rar() and siete.soporta_rar()
    assert llamadas == [["i"]]


def test_rar_sin_codec_dice_sin_soporte_no_danado(meta, tmp_path, monkeypatch):
    monkeypatch.setattr(siete, "_rar", False)
    fuente = _fuente(tmp_path, [("index.html", "<h1>Hola</h1>")])
    _7z(os.path.join(meta["publico"], "sitio.rar"), fuente)  # un .7z con nombre .rar: 7z lo abriría por el contenido
    with pytest.raises(ErrorSitio, match="no tiene soporte para .rar") as e:
        ordenes.descomprimir(D, "sitio.rar", ".")
    assert "dañado" not in str(e.value)
    assert not os.path.exists(os.path.join(meta["publico"], "index.html"))
    with pytest.raises(ErrorSitio, match="no tiene soporte para .rar"):  # también «Subir y migrar» (medir y extraer_a)
        siete.medir(os.path.join(meta["publico"], "sitio.rar"))
    with pytest.raises(ErrorSitio, match="no tiene soporte para .rar"):
        siete.extraer_a(os.path.join(meta["publico"], "sitio.rar"), str(tmp_path / "d"), lambda n: True, 1 << 20, 100)
    assert not os.path.exists(tmp_path / "d")


def test_rar_con_codec_sigue_el_mismo_camino_que_7z(meta, tmp_path, monkeypatch):
    monkeypatch.setattr(siete, "_rar", True)
    fuente = _fuente(tmp_path, [("index.html", "<h1>Hola</h1>")])
    _7z(os.path.join(meta["publico"], "sitio.rar"), fuente)
    ordenes.carpeta(D, "salida")
    assert ordenes.descomprimir(D, "sitio.rar", "salida")["archivos"] == 1
    assert open(os.path.join(meta["publico"], "salida", "index.html")).read() == "<h1>Hola</h1>"


# --- El proceso 7z no puede escribir ningún archivo por encima del tope (RLIMIT_FSIZE) ---

def test_limite_por_archivo_del_proceso_7z(tmp_path):
    fuente = _fuente(tmp_path, [("ceros.bin", b"\0" * (1024 * 1024))])
    paq = str(tmp_path / "grande.7z")
    _7z(paq, fuente)
    junto = tmp_path / "junto"
    junto.mkdir()
    with pytest.raises(ErrorSitio, match="infla"):
        with siete.extraido(paq, str(junto), 64 * 1024):
            pass
    assert os.listdir(junto) == []  # la carpeta temporal se borra
    with siete.extraido(paq, str(junto), 2 * 1024 * 1024) as abrir:  # con tope de sobra, sale igual que antes
        with abrir("ceros.bin") as f:
            assert len(f.read()) == 1024 * 1024


# --- Punta a punta: la subida llega con nombre al azar y extensión .7z y «Subir y migrar» la extrae en el sitio ---

def test_subir_y_extraer_paquete_7z_de_punta_a_punta(meta, tmp_path, monkeypatch):
    subidas = tmp_path / "subidas-sitios"
    subidas.mkdir()
    monkeypatch.setattr(paquete, "SUBIDAS", str(subidas))
    # Sin root ni nginx: permisos, vhost y recarga son dobles; la base no se pide.
    monkeypatch.setattr(m["apps.receta"], "permisos", lambda meta: None)
    monkeypatch.setattr(m["sitio"], "escribir_vhost", lambda meta: None)
    monkeypatch.setattr(m["sitio"], "recargar_nginx", lambda: None)
    fuente = _fuente(tmp_path, [("misitio/public/index.php", "<?php echo 1;"), ("misitio/public/css/a.css", "a{}"),
                                ("misitio/README.md", "hola")])
    nombre = "0123456789abcdef0123456789abcdef.7z"  # como lo deja el intermediario (32 hex + extensión real)
    _7z(str(subidas / nombre), fuente)
    assert paquete.RE_ARCHIVO.match(nombre)
    r = paquete.instalar(D, nombre, False)
    publico = meta["publico"]
    assert r["app"] == "paquete" and r["raiz_web"] == "public"  # la carpeta única de arriba se quita y se detecta public/
    assert open(os.path.join(publico, "public", "index.php")).read() == "<?php echo 1;"
    assert os.path.isfile(os.path.join(publico, "public", "css", "a.css")) and os.path.isfile(os.path.join(publico, "README.md"))
    assert not os.path.exists(subidas / nombre)  # la subida se borra al terminar
    guardado = m["comun"].leer_meta(D)
    assert guardado["app"] == "paquete" and guardado["paquete"]["raiz"] == "public" and len(guardado["paquete"]["suma"]) == 64


def test_subir_paquete_rar_sin_codec_deja_el_sitio_vacio(meta, tmp_path, monkeypatch):
    subidas = tmp_path / "subidas-sitios"
    subidas.mkdir()
    monkeypatch.setattr(paquete, "SUBIDAS", str(subidas))
    monkeypatch.setattr(siete, "_rar", False)
    nombre = "0123456789abcdef0123456789abcdef.rar"
    _7z(str(subidas / nombre), _fuente(tmp_path, [("index.html", "x")]))
    with pytest.raises(ErrorSitio, match="no tiene soporte para .rar"):
        paquete.instalar(D, nombre, False)
    assert os.listdir(meta["publico"]) == [] and not os.path.exists(subidas / nombre)
    assert not m["comun"].leer_meta(D).get("app")
