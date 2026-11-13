"""Túnel de soporte de Flota: validación del catálogo (límites y valores por defecto) y claves ed25519."""

import pytest
from fastapi import HTTPException

from app.flota import catalogo, tunel_ajustes, tunel_claves, tunel_parametros

HOST_FUERA = "tuneles.example.org"
HOST_RED = "tuneles.interno.example"


@pytest.fixture(autouse=True)
def ajustes(monkeypatch):
    monkeypatch.setenv("FLOTA_TUNEL_HOST", HOST_FUERA)
    monkeypatch.setenv("FLOTA_TUNEL_HOST_INTERNO", HOST_RED)
    for nombre in (
        "FLOTA_TUNEL_PUERTO_SSH",
        "FLOTA_TUNEL_USUARIO",
        "FLOTA_TUNEL_BROKER",
    ):
        monkeypatch.delenv(nombre, raising=False)


def abrir(**parametros):
    return catalogo.validar("abrir_tunel_soporte", parametros, "CONFIRMO")


def test_los_dos_tipos_estan_en_el_catalogo_como_fase_1():
    tipos = {t["tipo"]: t for t in catalogo.para_panel()}
    for tipo in ("abrir_tunel_soporte", "cerrar_tunel_soporte"):
        assert (
            tipos[tipo]["fase"] == 1
            and tipos[tipo]["habilitado"]
            and tipos[tipo]["dedicada"]
        )
    assert "dedicada" not in tipos["ping"]


def test_valores_por_defecto():
    assert abrir() == {
        "host": HOST_FUERA,
        "puerto_ssh": 443,
        "usuario": "tunel",
        "puerto_remoto": None,
        "minutos": 30,
    }


def test_el_equipo_en_la_red_usa_la_direccion_interna():
    assert abrir(ubicacion="red")["host"] == HOST_RED
    assert abrir(host="otro.example.net", ubicacion="red")["host"] == "otro.example.net"
    with pytest.raises(HTTPException):
        abrir(ubicacion="luna")


def test_sin_direccion_configurada_hay_que_indicarla(monkeypatch):
    monkeypatch.delenv("FLOTA_TUNEL_HOST")
    with pytest.raises(HTTPException) as e:
        abrir()
    assert e.value.status_code == 400
    assert abrir(host="192.0.2.10")["host"] == "192.0.2.10"


@pytest.mark.parametrize(
    "host", ["con espacio", "-empieza.mal", "a;rm", "$(x)", "a" * 300]
)
def test_host_no_valido(host):
    with pytest.raises(HTTPException):
        abrir(host=host)


@pytest.mark.parametrize(
    "campo, malos, buenos",
    [
        (
            "puerto_remoto",
            [22000, 23000, 0, "abc", 22001.5, True],
            [22001, 22999, "22500"],
        ),
        ("minutos", [4, 241, -1, "x"], [5, 240, 15, "60"]),
        ("puerto_ssh", [0, 65536, "ssh"], [1, 22, 65535]),
    ],
)
def test_limites(campo, malos, buenos):
    for valor in malos:
        with pytest.raises(HTTPException) as e:
            abrir(**{campo: valor})
        assert e.value.status_code == 400
    for valor in buenos:
        assert abrir(**{campo: valor})[campo] == int(valor)


def test_usuario():
    assert abrir(usuario="tunel2")["usuario"] == "tunel2"
    for malo in ("Con Espacio", "root;id", "-o", "a" * 40):
        with pytest.raises(HTTPException):
            abrir(usuario=malo)


def test_abrir_exige_confirmo_y_cerrar_no_lleva_parametros():
    for confirmacion in ("", "confirmo", "SI"):
        with pytest.raises(HTTPException) as e:
            catalogo.validar("abrir_tunel_soporte", {}, confirmacion)
        assert e.value.status_code == 400 and "CONFIRMO" in e.value.detail
    assert (
        catalogo.validar("cerrar_tunel_soporte", {"host": "x", "clave": "y"}, "") == {}
    )


def test_la_clave_nunca_sale_entre_los_parametros_validados():
    privada, _, _ = tunel_claves.generar()
    assert "clave" not in abrir(clave=privada)


def test_validez_corta():
    assert tunel_parametros.validez({}) == tunel_ajustes.HORAS_VALIDEZ_DEF == 2
    assert tunel_parametros.validez({"horas_validez": 12}) == 12
    for mala in (0, 13, 72):
        with pytest.raises(HTTPException):
            tunel_parametros.validez({"horas_validez": mala})


def test_el_resto_del_catalogo_no_cambia(monkeypatch):
    assert catalogo.validar("ping", {"lo": "que sea"}, "") == {}
    monkeypatch.delenv("FLOTA_HARDWARE", raising=False)
    with pytest.raises(HTTPException) as e:
        catalogo.validar("camara", {"accion": "desactivar"}, "CONFIRMO")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        catalogo.validar("no_existe", {}, "")


def test_clave_pegada_a_mano():
    privada, publica, huella = tunel_claves.generar()
    assert privada.startswith(
        "-----BEGIN OPENSSH PRIVATE KEY-----"
    ) and publica.startswith("ssh-ed25519 ")
    assert huella.startswith("SHA256:") and len(huella) == 50
    assert tunel_claves.comprobar(privada.replace("\n", "\r\n") + "  \r\n") == (
        privada,
        huella,
    )
    assert tunel_claves.comprobar("") is None and tunel_claves.comprobar(None) is None


def test_clave_no_valida_y_el_error_no_la_repite():
    privada, _, _ = tunel_claves.generar()
    rota = privada.replace("\n", "\nZZZZ", 2)
    for mala in (
        "hola",
        publica_falsa := "ssh-ed25519 AAAA",
        privada[:80],
        rota,
        "x" * 5000,
    ):
        with pytest.raises(HTTPException) as e:
            tunel_claves.comprobar(mala)
        assert e.value.status_code == 400 and mala[:40] not in e.value.detail
    assert publica_falsa


def test_clave_que_no_es_ed25519():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    otra = (
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
        .decode()
    )
    with pytest.raises(HTTPException) as e:
        tunel_claves.comprobar(otra)
    assert "ed25519" in e.value.detail
