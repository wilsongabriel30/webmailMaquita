"""Importar cuentas desde CSV (v1.11): lectura del archivo, reglas fila a fila y CSV exportado.

El módulo vive en el panel general y en el portal de dominio (copia idéntica, sin dependencias):
se carga por ruta, como los guiones de deploy/. Solo dominios example.org / example.com.
"""

import filecmp
import importlib.util
import os

import pytest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERAL = os.path.join(RAIZ, "admin-panel", "backend", "app", "importar_cuentas", "formato_csv.py")
PORTAL = os.path.join(RAIZ, "panel-dominio", "backend", "app", "importar", "formato_csv.py")

_spec = importlib.util.spec_from_file_location("formato_csv_importar", GENERAL)
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)

MIB = 1024 * 1024
CLAVE = "Verde.Monte42"


def info(**extra):
    base = {"activo": True, "enrutado": False, "max_cuentas": 0, "cuentas": 0, "max_alias": 0, "alias": 0,
            "cuota_maxima": 2048 * MIB, "cuota_defecto": 1024 * MIB}
    return {**base, **extra}


def revisado(texto, dominios=None, ocupadas=(), pendientes=None):
    dominios = {"example.org": info()} if dominios is None else dominios
    return fc.revisar(fc.leer(texto), dominios, set(ocupadas), "El dominio {dominio} es ajeno", pendientes)


def test_las_dos_copias_son_identicas():
    assert filecmp.cmp(GENERAL, PORTAL, shallow=False), "panel general y portal deben llevar el mismo formato_csv.py"


# --- Lectura del archivo ---


def test_lee_coma_y_cabeceras_con_tildes_y_sinonimos():
    filas = fc.leer("﻿Correo,Nombre,Contraseña,Cuota MB,Alias\r\nAna@Example.org,Ana Pérez,%s,500,ventas@example.org;info@example.org\r\n" % CLAVE)
    assert filas == [{"fila": 2, "correo": "ana@example.org", "nombre": "Ana Pérez", "clave": CLAVE, "cuota_mb": 500,
                      "alias": ["ventas@example.org", "info@example.org"], "errores": []}]


def test_lee_punto_y_coma_como_excel_en_espanol():
    filas = fc.leer('correo;nombre;alias\nana@example.org;"Pérez; Ana";"a@example.org;b@example.org"\n')
    assert filas[0]["nombre"] == "Pérez; Ana"
    assert filas[0]["alias"] == ["a@example.org", "b@example.org"]
    assert filas[0]["clave"] is None and filas[0]["cuota_mb"] is None


def test_filas_vacias_se_saltan_y_el_numero_es_la_linea_del_archivo():
    filas = fc.leer("correo,nombre\n\nana@example.org,Ana\n,\nluis@example.org,Luis\n")
    assert [f["fila"] for f in filas] == [3, 5]


@pytest.mark.parametrize("texto, mensaje", [
    ("", "vacío"),
    ("correo,nombre,telefono\nana@example.org,Ana,1\n", "Columna desconocida"),
    ("correo,correo,nombre\n", "repetida"),
    ("correo,clave\nana@example.org,x\n", "obligatorias: nombre"),
    ("correo,nombre\n", "no tiene filas"),
    ('correo,nombre\nana@example.org,"Ana\n', "CSV válido"),
    ("correo,nombre\nana@example.org,Ana �\n", "UTF-8"),
])
def test_archivos_que_no_se_pueden_leer(texto, mensaje):
    with pytest.raises(fc.ErrorArchivo, match=mensaje):
        fc.leer(texto)


def test_limite_de_filas_y_de_tamano():
    fc.leer("correo,nombre\n" + "".join(f"u{i}@example.org,U\n" for i in range(fc.MAX_FILAS)))
    with pytest.raises(fc.ErrorArchivo, match="más de 2000 filas"):
        fc.leer("correo,nombre\n" + "".join(f"u{i}@example.org,U\n" for i in range(fc.MAX_FILAS + 1)))
    with pytest.raises(fc.ErrorArchivo, match="pesa más"):
        fc.leer("correo,nombre\nana@example.org," + "a" * fc.MAX_BYTES + "\n")


@pytest.mark.parametrize("linea, error", [
    (",Ana", "Falta el correo"),
    ("ana,Ana", "usuario@dominio"),
    ("ana..perez@example.org,Ana", "solo admite"),
    ("ana@localhost,Ana", "dominio no es válido"),
    ("ana@example.org,", "Falta el nombre"),
    ("ana@example.org,Ana,,diez", "número entero"),
    ("ana@example.org,Ana,,0", "mayor que cero"),
    ("ana@example.org,Ana,,,mal alias@", "no es válido"),
    ("ana@example.org,Ana,,,ana@example.org", "propio correo"),
    ("ana@example.org,Ana,,,,sobra", "más columnas"),
])
def test_errores_de_forma_por_fila(linea, error):
    filas = fc.leer("correo,nombre,clave,cuota_mb,alias\n" + linea + "\n")
    assert any(error in e for e in filas[0]["errores"]), filas[0]["errores"]


def test_nombre_sin_caracteres_de_control():
    assert fc.leer('correo,nombre\nana@example.org,"Ana\tPérez"\n')[0]["nombre"] == "Ana Pérez"


# --- Reglas contra el servidor ---


def test_fila_correcta_con_cuota_y_por_defecto():
    filas = revisado("correo,nombre,clave,cuota_mb\nana@example.org,Ana,%s,500\nluis@example.org,Luis,,\n" % CLAVE)
    assert [f["valida"] for f in filas] == [True, True]
    assert filas[0]["cuota"] == 500 * MIB and filas[1]["cuota"] == 1024 * MIB


@pytest.mark.parametrize("linea, ocupadas, error", [
    ("ana@example.com,Ana", (), "El dominio example.com es ajeno"),
    ("ana@example.org,Ana", ("ana@example.org",), "ya existe"),
    ("ana@example.org,Ana,corta", (), "al menos 10"),
    ("ana@example.org,Ana,sololetrasminusculas", (), "tres de"),
    ("anaperez@example.org,Ana,Anaperez.2026", (), "nombre de la cuenta"),
    ("ana@example.org,Ana,,4096", (), "Cuota excedida: el máximo del dominio es 2048 MB"),
    ("ana@example.org,Ana,,,ventas@example.org", ("ventas@example.org",), "El alias ventas@example.org ya existe"),
    ("ana@example.org,Ana,,,ventas@example.com", (), "dominio example.com es ajeno"),
])
def test_errores_contra_el_servidor(linea, ocupadas, error):
    f = revisado("correo,nombre,clave,cuota_mb,alias\n" + linea + "\n", ocupadas=ocupadas)[0]
    assert not f["valida"]
    assert any(error in e for e in f["errores"]), f["errores"]


def test_dominio_desactivado_o_enrutado():
    filas = revisado("correo,nombre\nana@example.org,Ana\nluis@example.com,Luis\n",
                     {"example.org": info(activo=False), "example.com": info(enrutado=True)})
    assert "desactivado" in filas[0]["errores"][0]
    assert "otro servidor" in filas[1]["errores"][0]


def test_repetidos_dentro_del_archivo():
    filas = revisado("correo,nombre,alias\nana@example.org,Ana,ventas@example.org\nana@example.org,Ana 2,\n"
                     "luis@example.org,Luis,ventas@example.org\nventas@example.org,Ventas,\n")
    assert filas[0]["valida"]
    assert "fila 2" in filas[1]["errores"][0]
    assert "ventas@example.org ya aparece en la fila 2" in filas[2]["errores"][0]
    assert "fila 2" in filas[3]["errores"][0]


def test_topes_de_cuentas_y_alias_del_dominio():
    filas = revisado("correo,nombre,alias\na@example.org,A,\nb@example.org,B,\nc@example.org,C,\n",
                     {"example.org": info(max_cuentas=4, cuentas=2)})
    assert [f["valida"] for f in filas] == [True, True, False]
    assert "límite de 4 cuentas" in filas[2]["errores"][0]
    filas = revisado("correo,nombre,alias\na@example.org,A,x@example.org;y@example.org\nb@example.org,B,z@example.org\n",
                     {"example.org": info(max_alias=3, alias=1)})
    assert [f["valida"] for f in filas] == [True, False]
    assert "límite de 3 alias" in filas[1]["errores"][0]


def test_una_fila_con_error_no_gasta_cupo():
    filas = revisado("correo,nombre,clave\na@example.org,A,mala\nb@example.org,B,\n",
                     {"example.org": info(max_cuentas=1)})
    assert [f["valida"] for f in filas] == [False, True]


def test_pendientes_de_bloques_anteriores_cuentan():
    filas = revisado("correo,nombre\na@example.org,A\n", {"example.org": info(max_cuentas=5, cuentas=3)},
                     pendientes={"cuentas": {"example.org": 2}})
    assert "límite de 5 cuentas" in filas[0]["errores"][0]


def test_la_vista_previa_no_devuelve_la_clave():
    f = revisado("correo,nombre,clave\nana@example.org,Ana,%s\n" % CLAVE)[0]
    mostrado = fc.para_mostrar(f)
    assert CLAVE not in repr(mostrado)
    assert mostrado["clave"] == "en el archivo" and mostrado["cuota_mb"] == 1024


# --- Contraseñas generadas ---


def test_claves_generadas_cumplen_la_politica_y_no_parecen_formulas():
    for _ in range(500):
        clave = fc.generar_clave("ana@example.org")
        assert fc.problema_clave(clave, "ana@example.org") is None
        assert clave[0].isalnum()
        assert fc.celda_segura(clave) == clave
    assert len({fc.generar_clave() for _ in range(50)}) == 50


# --- Exportación sin inyección de fórmulas ---


@pytest.mark.parametrize("valor, esperado", [
    ("=HYPERLINK(\"http://example.com\")", "'=HYPERLINK(\"http://example.com\")"),
    ("+1", "'+1"), ("-2+3", "'-2+3"), ("@SUM(A1)", "'@SUM(A1)"), ("\t=1", "'\t=1"), ("\r=1", "'\r=1"),
    ("  =1", "'  =1"), ("Ana Pérez", "Ana Pérez"), ("ana@example.org", "ana@example.org"), ("", ""), (None, ""), (12, "12"),
])
def test_celda_segura(valor, esperado):
    assert fc.celda_segura(valor) == esperado


def test_csv_exportados_escapan_y_no_incluyen_claves_dadas():
    filas = revisado("correo,nombre,clave\nana@example.org,=cmd|' /C calc'!A0,%s\nluis@example.org,Luis,\n" % CLAVE)
    filas[1]["clave_generada"] = "Abc.12345xyzWQ"
    informe = fc.informe_csv([{**fc.para_mostrar(f), "resultado": "creada"} for f in filas])
    assert informe.splitlines()[0] == "fila,correo,resultado,detalle"
    claves = fc.claves_csv(filas)
    assert claves.splitlines() == ["correo,nombre,clave", "luis@example.org,Luis,Abc.12345xyzWQ"]
    assert CLAVE not in claves
    assert fc.claves_csv(filas[:1]) is None
    exportado = fc.a_csv(["nombre"], [[filas[0]["nombre"]]])
    assert exportado.splitlines()[1] == "'=cmd|' /C calc'!A0"
