# -*- coding: utf-8 -*-
"""N-25: de la ficha de nómina a la cuenta del chat.

Lo que se protege aquí es lo que rompió antes: devolver el id de NÓMINA como si fuera el del
chat (se habría escrito a otra persona) y filtrar por un estado escrito de otra forma (la lista
salía siempre vacía y nadie lo notaba).
"""
import os

os.environ.setdefault("DOMINIOS_EQUIVALENTES", "maquita.org,maquita.com.ec,fundacionmaquita.org")

from interfaces.api.directorio_nomina import (  # noqa: E402
    armar_lista, candidatos, correos_equivalentes, es_activo,
)


def ficha(id_nomina, correo, nombre="ANA PEREZ", estado="Activo"):
    return {"id": id_nomina, "email_institucional": correo, "nombre_completo": nombre,
            "estado": estado, "cargo": "Analista", "departamento": "Tecnología", "foto_url": None}


# --- estado -------------------------------------------------------------------------------
def test_estado_activo_en_cualquier_forma():
    for valor in ("Activo", "ACTIVO", " activo ", "AcTiVo"):
        assert es_activo(valor), valor


def test_estado_que_no_es_activo():
    for valor in ("Desvinculado", "", None, "Inactivo", "Activo temporal"):
        assert not es_activo(valor), valor


# --- correos ------------------------------------------------------------------------------
def test_correos_equivalentes_de_dominio_institucional():
    salida = correos_equivalentes("juan.perez@maquita.com.ec")
    assert salida[0] == "juan.perez@maquita.com.ec"
    assert "juan.perez@maquita.org" in salida
    assert "juan.perez@fundacionmaquita.org" in salida


def test_correo_externo_no_se_multiplica():
    assert correos_equivalentes("alguien@gmail.com") == ["alguien@gmail.com"]


def test_correo_invalido_no_produce_candidatos():
    assert correos_equivalentes("sin-arroba") == []
    assert correos_equivalentes("") == []
    assert correos_equivalentes(None) == []


def test_candidatos_sin_repetidos():
    filas = [ficha(1, "a@maquita.org"), ficha(2, "a@maquita.com.ec"), ficha(3, "b@gmail.com")]
    c = candidatos(filas)
    assert len(c) == len(set(c))
    assert "a@maquita.org" in c and "b@gmail.com" in c


# --- armado de la lista -------------------------------------------------------------------
def test_devuelve_el_id_de_la_cuenta_no_el_de_nomina():
    """El fallo que se corrige: 81 es de nómina, 14 es la cuenta con la que se chatea."""
    filas = [ficha(81, "juan.perez@maquita.com.ec")]
    cuentas = {"juan.perez@maquita.com.ec": {"id": 14, "nombre": "JUAN PEREZ"}}
    salida = armar_lista(filas, cuentas, usuario_actual=999, limite=30)
    assert len(salida) == 1
    assert salida[0]["id"] == 14
    assert salida[0]["trabajador_id"] == 81


def test_cuenta_en_dominio_equivalente():
    filas = [ficha(5, "ana.lopez@maquita.com.ec")]
    cuentas = {"ana.lopez@maquita.org": {"id": 77, "nombre": "ANA LOPEZ"}}
    salida = armar_lista(filas, cuentas, usuario_actual=1, limite=30)
    assert [p["id"] for p in salida] == [77]


def test_sin_cuenta_no_aparece():
    """Quien no tiene usuario no se puede atender: mostrarlo solo llevaría a un error."""
    filas = [ficha(6, "pasante@nomina.local")]
    assert armar_lista(filas, {}, usuario_actual=1, limite=30) == []


def test_no_aparece_uno_mismo():
    filas = [ficha(7, "yo@maquita.org")]
    cuentas = {"yo@maquita.org": {"id": 14, "nombre": "YO"}}
    assert armar_lista(filas, cuentas, usuario_actual=14, limite=30) == []
    assert armar_lista(filas, cuentas, usuario_actual="14", limite=30) == []


def test_desvinculado_fuera_aunque_tenga_cuenta():
    filas = [ficha(8, "ex@maquita.org", estado="Desvinculado")]
    cuentas = {"ex@maquita.org": {"id": 20, "nombre": "EX"}}
    assert armar_lista(filas, cuentas, usuario_actual=1, limite=30) == []


def test_una_sola_entrada_por_persona():
    """La misma persona en dos fichas (dos dominios) no debe salir dos veces."""
    filas = [ficha(9, "dos@maquita.org"), ficha(10, "dos@maquita.com.ec")]
    cuentas = {"dos@maquita.org": {"id": 33, "nombre": "DOS"},
               "dos@maquita.com.ec": {"id": 33, "nombre": "DOS"}}
    salida = armar_lista(filas, cuentas, usuario_actual=1, limite=30)
    assert [p["id"] for p in salida] == [33]


def test_respeta_el_limite():
    filas = [ficha(i, f"p{i}@maquita.org", nombre=f"P {i}") for i in range(1, 11)]
    cuentas = {f"p{i}@maquita.org": {"id": 100 + i, "nombre": f"P {i}"} for i in range(1, 11)}
    salida = armar_lista(filas, cuentas, usuario_actual=1, limite=4)
    assert len(salida) == 4


def test_nombre_de_reserva_si_nomina_no_lo_trae():
    filas = [ficha(11, "sinnombre@maquita.org", nombre="  ")]
    cuentas = {"sinnombre@maquita.org": {"id": 44, "nombre": "NOMBRE DE LA CUENTA"}}
    salida = armar_lista(filas, cuentas, usuario_actual=1, limite=5)
    assert salida[0]["name"] == "NOMBRE DE LA CUENTA"
