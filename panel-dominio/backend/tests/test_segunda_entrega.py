"""Segundo factor, imágenes de marca, destinos y veredicto DNS."""

import asyncio

import pyotp
import pytest
from fastapi import HTTPException

from app import destinos, totp
from app.dns import juzgar, leer, sin_veredicto
from app.imagenes import formato_de, medidas
from app.reenvios import _partes

SECRETO = pyotp.random_base32()
AHORA = 1_900_000_000.0
PASO = int(AHORA // 30)


def codigo(paso):
    return pyotp.TOTP(SECRETO).at(paso * 30)


def test_codigo_correcto_y_vecinos():
    assert totp.comprobar(SECRETO, codigo(PASO), 0, AHORA) == PASO
    assert totp.comprobar(SECRETO, codigo(PASO - 1), 0, AHORA) == PASO - 1
    assert totp.comprobar(SECRETO, codigo(PASO + 1), 0, AHORA) == PASO + 1


def test_codigo_viejo_o_inventado_no_vale():
    assert totp.comprobar(SECRETO, codigo(PASO - 3), 0, AHORA) is None
    assert totp.comprobar(SECRETO, "000000" if codigo(PASO) != "000000" else "111111", 0, AHORA) is None
    assert totp.comprobar(SECRETO, "", 0, AHORA) is None
    assert totp.comprobar(SECRETO, "12345", 0, AHORA) is None
    assert totp.comprobar("", codigo(PASO), 0, AHORA) is None


def test_un_codigo_no_se_usa_dos_veces():
    usado = totp.comprobar(SECRETO, codigo(PASO), 0, AHORA)
    assert totp.comprobar(SECRETO, codigo(PASO), usado, AHORA) is None
    assert totp.comprobar(SECRETO, codigo(PASO - 1), usado, AHORA) is None


def test_codigo_con_espacios_se_acepta():
    c = codigo(PASO)
    assert totp.comprobar(SECRETO, c[:3] + " " + c[3:], 0, AHORA) == PASO


def test_qr_es_una_imagen_svg():
    assert totp.codigo_qr("otpauth://totp/x?secret=ABC").startswith("data:image/svg+xml;base64,")


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (200).to_bytes(4, "big") + (80).to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"


def test_formatos_reconocidos_por_contenido():
    assert formato_de(PNG) == "png"
    assert formato_de(b"\xff\xd8\xff\xe0" + b"0" * 20) == "jpeg"
    assert formato_de(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert formato_de(b"\x00\x00\x01\x00" + b"\x00" * 20) == "ico"
    assert medidas(PNG, "png") == (200, 80)


@pytest.mark.parametrize("malo", [
    b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
    b"<?xml version='1.0'?><svg/>", b"<html><script>1</script></html>", b"GIF89a" + b"0" * 20,
    b"MZ\x90\x00", b"%PDF-1.7", b"", b"PNG",
])
def test_lo_que_no_es_imagen_admitida_se_rechaza(malo):
    assert formato_de(malo) is None


class _Db:
    def __init__(self, existentes):
        self.existentes = existentes

    async def fetch(self, _q, lista):
        return [{"address": d} for d in lista if d in self.existentes]


ADMIN = {"dominios": ["uno.example"]}


def _validar(valor, existentes=("ana@uno.example",), salvo=""):
    return asyncio.run(destinos.validar(_Db(existentes), ADMIN, valor, salvo=salvo))


def test_destino_propio_debe_existir():
    assert _validar("ana@uno.example") == (["ana@uno.example"], [])
    with pytest.raises(HTTPException):
        _validar("nadie@uno.example")


def test_destino_externo_se_acepta_y_se_marca():
    lista, externos = _validar("ana@uno.example, socio@otra.example")
    assert lista == ["ana@uno.example", "socio@otra.example"]
    assert externos == ["socio@otra.example"]


def test_la_propia_direccion_no_cuenta_como_destino():
    assert _validar("ana@uno.example", salvo="ana@uno.example") == ([], [])


def test_reenvio_se_descompone():
    assert _partes("a@x.example", "a@x.example,b@y.example") == {"cuenta": "a@x.example", "conserva_copia": True, "destinos": ["b@y.example"]}
    assert _partes("a@x.example", "b@y.example")["conserva_copia"] is False


def test_veredicto_dns():
    bien = juzgar(["10 mail.uno.example."], ["v=spf1 mx -all", "otra cosa"], ["v=DMARC1; p=quarantine"], {"default": ["v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A"]})
    assert all(bien[k]["bien"] for k in ("mx", "spf", "dkim", "dmarc"))
    mal = juzgar([], ["v=spf1 a", "v=spf1 b"], [], {"default": ["v=DKIM1; p="]})
    assert not any(mal[k]["bien"] for k in ("mx", "spf", "dkim", "dmarc"))


def test_lee_respuestas_de_dns_sobre_https():
    mx = {"Status": 0, "Answer": [{"type": 15, "data": "10 mail.uno.example."}, {"type": 46, "data": "firma"}]}
    assert leer(mx, "MX") == (0, ["10 mail.uno.example."])
    txt = {"Status": 0, "Answer": [{"type": 16, "data": '"v=DKIM1; k=rsa; p=MIIB" "IjANBgkq"'}, {"type": 5, "data": "alias."}]}
    assert leer(txt, "TXT") == (0, ["v=DKIM1; k=rsa; p=MIIBIjANBgkq"])
    assert leer({"Status": 3}, "MX") == (3, [])
    assert leer({"Status": 0}, "TXT") == (0, [])


def test_sin_consulta_no_se_afirma_nada():
    v = sin_veredicto("No se pudo consultar")
    assert [v[k]["bien"] for k in ("mx", "spf", "dkim", "dmarc")] == [None] * 4


def test_los_resolutores_son_https():
    from app import config_extra

    assert config_extra.RESOLUTORES_DOH and all(u.startswith("https://") for u in config_extra.RESOLUTORES_DOH)
