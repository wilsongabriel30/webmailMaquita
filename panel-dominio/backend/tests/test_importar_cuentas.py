"""Importar cuentas desde CSV en el portal: alcance, topes del dominio, bloques y lo que se audita.

La base es un doble en memoria: se comprueba también qué se le pregunta (de un dominio ajeno, nada).
"""

import asyncio
import json

import pytest
from fastapi import HTTPException

from app.importar import formato_csv, rutas
from app.validacion import exigir_clave_fuerte

ADMIN = {"id": 7, "username": "jefa@example.org", "dominios": ["example.org"]}
CLAVE = "Verde.Monte42"
HASH = "{SHA512-CRYPT}$6$sal$" + "h" * 86


class _Con:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def transaction(self):
        return self

    async def execute(self, q, *args):
        if "INSERT INTO mailbox" in q and args[0] in self.db.fallar:
            raise RuntimeError('duplicate key value violates unique constraint "mailbox_pkey"')
        self.db.escrito.append((q.split("(")[0].strip(), args))


class Db:
    def __init__(self, dominios=None, ocupadas=(), enrutados=(), sin_enrutamiento=False):
        self.dominios = {"example.org": {"active": True, "mailboxes": 0, "aliases": 0, "maxquota": 0,
                                         "cuentas": 0, "alias_usados": 0}} if dominios is None else dominios
        self.ocupadas, self.enrutados, self.sin_enrutamiento = set(ocupadas), set(enrutados), sin_enrutamiento
        self.preguntas, self.escrito, self.auditoria, self.fallar = [], [], [], set()

    async def fetch(self, q, lista):
        self.preguntas.append(list(lista))
        if "FROM domain d" in q:
            return [{"domain": d, **self.dominios[d]} for d in lista if d in self.dominios]
        if "enrutamiento_correo" in q:
            if self.sin_enrutamiento:
                raise RuntimeError("permission denied for table enrutamiento_correo")
            return [{"dominio": d} for d in lista if d in self.enrutados]
        return [{"d": d} for d in lista if d in self.ocupadas]

    async def execute(self, q, *args):
        assert "pd_auditoria" in q
        self.auditoria.append(args)

    def acquire(self):
        return _Con(self)


class _Peticion:
    def __init__(self, db, cuerpo):
        self.app = type("App", (), {"state": type("Estado", (), {"db": db})()})()
        self.headers = {"X-Real-IP": "192.0.2.10"}
        self.client = None
        self._cuerpo = cuerpo

    async def json(self):
        return self._cuerpo


def vista(db, csv, **extra):
    return asyncio.run(rutas.vista_previa(_Peticion(db, {"csv": csv, **extra}), ADMIN))


def aplicar(db, csv, monkeypatch):
    async def hash_falso(clave):
        return HASH
    monkeypatch.setattr(rutas, "hash_buzon", hash_falso)
    return asyncio.run(rutas.aplicar(_Peticion(db, {"csv": csv}), ADMIN))


def test_dominio_ajeno_no_se_consulta_en_la_base():
    db = Db()
    r = vista(db, "correo,nombre,alias\nana@example.com,Ana,\nluis@example.org,Luis,ventas@example.com\n")
    assert r["filas"][0]["errores"] == ["El dominio example.com no es uno de tus dominios"]
    assert "example.com no es uno de tus dominios" in r["filas"][1]["errores"][0]
    assert all("example.com" not in str(p) for p in db.preguntas)


def test_cuota_del_portal_y_tope_por_defecto():
    db = Db()
    r = vista(db, "correo,nombre,cuota_mb\na@example.org,A,\nb@example.org,B,6000\n")
    assert r["filas"][0]["cuota_mb"] == 5 * 1024 and r["filas"][0]["valida"]
    assert "Cuota excedida: el máximo del dominio es 5120 MB" in r["filas"][1]["errores"]


def test_dominio_enrutado_y_tabla_sin_permiso():
    assert "otro servidor" in vista(Db(enrutados={"example.org"}), "correo,nombre\na@example.org,A\n")["filas"][0]["errores"][0]
    assert vista(Db(sin_enrutamiento=True), "correo,nombre\na@example.org,A\n")["validas"] == 1


def test_bloques_desplazamiento_y_pendientes():
    db = Db(dominios={"example.org": {"active": True, "mailboxes": 3, "aliases": 0, "maxquota": 0,
                                      "cuentas": 1, "alias_usados": 0}})
    r = vista(db, "correo,nombre\nc@example.org,C\n", desplazamiento=40, pendientes={"cuentas": {"example.org": 2}})
    assert r["filas"][0]["fila"] == 42
    assert "límite de 3 cuentas" in r["filas"][0]["errores"][0]
    r = vista(db, "correo,nombre\nc@example.org,C\n", pendientes={"cuentas": {"example.org": 1}})
    assert r["validas"] == 1 and r["ocupa"] == {"cuentas": {"example.org": 1}, "alias": {}}


@pytest.mark.parametrize("valor", [
    {"cuentas": {"example.com": 5}}, {"cuentas": {"example.org": True}}, {"cuentas": {"example.org": -1}},
    {"cuentas": {"example.org": "9"}}, {"cuentas": ["example.org"]}, "nada", None,
])
def test_pendientes_raros_se_descartan(valor):
    assert rutas._pendientes(valor, ADMIN) == {"cuentas": {}, "alias": {}}


def test_archivo_ilegible_da_400():
    with pytest.raises(HTTPException) as e:
        vista(Db(), "correo,apellido\n")
    assert e.value.status_code == 400 and "Columna desconocida" in e.value.detail


def test_aplicar_crea_las_validas_audita_sin_claves_y_entrega_las_generadas(monkeypatch):
    db = Db(ocupadas={"ya@example.org"})
    r = aplicar(db, "correo,nombre,clave,alias\nana@example.org,Ana,%s,ventas@example.org\n"
                    "luis@example.org,Luis,,\nya@example.org,Ya,,\nmal@example.org,Mal,corta,\n" % CLAVE, monkeypatch)
    assert (r["creadas"], r["omitidas"]) == (2, 2)
    assert [x["resultado"] for x in r["resultados"]] == ["creada", "creada", "omitida", "omitida"]
    insertados = [(tabla, args[0], args[1]) for tabla, args in db.escrito]
    assert ("INSERT INTO mailbox", "ana@example.org", HASH) in insertados
    assert ("INSERT INTO alias", "ventas@example.org", "ana@example.org") in insertados
    assert ("INSERT INTO alias", "luis@example.org", "example.org") in insertados  # su fila de entrega propia
    lineas = r["claves_csv"].splitlines()
    assert lineas[0] == "correo,nombre,clave" and len(lineas) == 2 and lineas[1].startswith("luis@example.org,Luis,")
    generada = lineas[1].split(",")[2]
    assert formato_csv.problema_clave(generada, "luis@example.org") is None
    texto = json.dumps(r) + json.dumps(db.auditoria)
    assert CLAVE not in texto and texto.count(generada) == 1  # solo en el CSV de contraseñas
    (admin_id, quien, accion, objetivo, detalles, ip), = db.auditoria
    assert (accion, objetivo, ip) == ("cuentas_importar", "2 cuentas", "192.0.2.10")
    assert json.loads(detalles)["creadas"] == ["ana@example.org", "luis@example.org"]


def test_aplicar_carrera_con_otra_alta(monkeypatch):
    db = Db()
    db.fallar = {"ana@example.org"}
    r = aplicar(db, "correo,nombre\nana@example.org,Ana\n", monkeypatch)
    assert r["creadas"] == 0 and r["resultados"][0]["errores"] == ["Ya existe (se creó mientras tanto)"]
    assert r["claves_csv"] is None


@pytest.mark.parametrize("clave", [
    "corta", "Sololetras", "sololetrasminusculas", "SOLOMAYUSCULAS99", "Verde.Monte42", "verde.monte42", "a" * 129,
    "Ab1" + "x" * 7, "Ana.Perez.2026x", "1234567890Ab", "Ñandú.Feliz7", "   espacios   A1",
])
def test_misma_politica_que_el_alta_manual(clave):
    try:
        exigir_clave_fuerte(clave, "anaperez@example.org")
        manual = None
    except HTTPException as e:
        manual = e.detail
    assert formato_csv.problema_clave(clave, "anaperez@example.org") == manual
