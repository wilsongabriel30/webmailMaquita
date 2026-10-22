"""maquita-sitios-portal con sesiones de soporte del superadministrador: alcance de un solo dominio y,
en solo lectura, solo las órdenes que no modifican nada (la segunda barrera, por si el portal fallara)."""

import pytest

from tests.test_sitios_portal import Base, codigo, mundo, pedir  # noqa: F401  (mundo es la fijación)

import portal  # noqa: E402
import sesion  # noqa: E402


class BaseConSoporte(Base):
    def __init__(self, solo_lectura=True, tabla=True):
        super().__init__()
        self.admin = None  # la ficha no es de un administrador de dominio
        self.solo_lectura, self.tabla = solo_lectura, tabla

    def __call__(self, sql, variables=None, tabla=None):
        if sql == sesion.SQL_SOPORTE:
            if not self.tabla:
                raise sesion.bd.FaltaTabla(tabla)
            return {"id": 3, "superadmin": "admin", "dominio": "example.org", "solo_lectura": self.solo_lectura}
        return super().__call__(sql, variables, tabla)


@pytest.fixture
def soporte(mundo, monkeypatch):  # noqa: F811
    def poner(**kw):
        base = BaseConSoporte(**kw)
        monkeypatch.setattr(sesion.bd, "consultar", base)
        mundo.sitio("example.org")
        return mundo
    return poner


def test_la_sesion_de_soporte_alcanza_solo_su_dominio(soporte):
    m = soporte()
    admin = sesion.verificar("f" * 43)
    assert admin["dominios"] == ["example.org"] and admin["soporte"]["solo_lectura"] is True
    assert admin["usuario"] == "soporte:admin"
    m.sitio("example.com")
    assert codigo("revisar", "example.com") == 404


def test_solo_lectura_deja_leer(soporte):
    soporte()
    assert pedir("revisar", "example.org")["ok"]
    assert pedir("listar")["ok"]


@pytest.mark.parametrize("orden", ["crear", "app", "entrar", "clave-admin", "actualizar", "ssl", "ftp",
                                   "tareas-guardar", "base-crear", "base-entrar", "base-borrar", "php-version",
                                   "dns-agregar", "dns-borrar", "web-purgar", "ftp-cuenta-crear", "copia-crear",
                                   "copia-descargar", "archivos-borrar", "archivos-descargar", "archivos-vaciar"])
def test_solo_lectura_no_modifica_nada(soporte, orden):
    m = soporte()
    assert codigo(orden, "example.org") == 403
    assert m.ayudante.llamadas == []


def test_toda_orden_nueva_queda_prohibida_en_solo_lectura():
    # La lista de lectura es cerrada y solo nombra órdenes que existen.
    assert portal.ORDENES_LECTURA <= set(portal.ORDENES)
    for orden in ("crear", "app", "paquete", "dns-modificar", "archivos-subir", "copia-restaurar"):
        assert orden not in portal.ORDENES_LECTURA


def test_con_acciones_se_permite(soporte):
    m = soporte(solo_lectura=False)
    assert pedir("actualizar", "example.org")["ok"]
    assert m.ayudante.llamadas


def test_sin_tabla_de_soporte_la_ficha_no_vale(soporte):
    soporte(tabla=False)
    assert codigo("listar") == 403
