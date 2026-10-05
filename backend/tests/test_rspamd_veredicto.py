"""Regla del filtro de correo: indicios débiles que Rspamd desmiente no van a no deseado."""

import email
import importlib.util
from pathlib import Path

_RUTA = Path(__file__).resolve().parents[2] / "scripts" / "rspamd_veredicto.py"
_spec = importlib.util.spec_from_file_location("rspamd_veredicto", _RUTA)
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)


def _correo(*cabeceras_rspamd):
    texto = "From: a@ejemplo.org\nTo: b@ejemplo.org\nSubject: hola\n"
    for c in cabeceras_rspamd:
        texto += "X-Spamd-Result: " + c + "\n"
    return email.message_from_string(texto + "\ncuerpo\n")


DEBILES = ["exceso-links(19)(+2)", "sin-dkim(+1)", "neurona(spam,0.89,neurona)(+0)"]


def test_rescata_indicios_debiles_con_rspamd_negativo():
    msg = _correo("default: False [-4.65 / 20.00];\n\tBAYES_HAM(-3.00)[99.9%]")
    assert rv.rescatar_por_rspamd(msg, 3, DEBILES) == (True, -4.65)


def test_no_rescata_si_rspamd_no_es_negativo():
    assert (
        rv.rescatar_por_rspamd(_correo("default: False [0.00 / 20.00]"), 3, DEBILES)[0]
        is False
    )
    assert (
        rv.rescatar_por_rspamd(_correo("default: False [2.10 / 20.00]"), 3, DEBILES)[0]
        is False
    )


def test_no_rescata_sin_cabecera_o_con_varias():
    assert rv.rescatar_por_rspamd(_correo(), 3, DEBILES) == (False, None)
    dos = _correo("default: False [-9.00 / 20.00]", "default: False [-9.00 / 20.00]")
    assert rv.rescatar_por_rspamd(dos, 3, DEBILES) == (False, None)


def test_no_rescata_indicios_fuertes():
    msg = _correo("default: False [-4.65 / 20.00]")
    for fuerte in (
        "blacklist-domain:malo.example(+10)",
        "greylist-domain:dudoso.example(+4)",
        "viagra(+3)",
        "urls-acortadas(2)(+2)",
        "adjunto-peligroso(a.exe)(+5)",
        "antivirus:no_escaneado(+2)",
    ):
        assert rv.rescatar_por_rspamd(msg, 4, ["sin-dkim(+1)", fuerte])[0] is False


def test_no_rescata_por_encima_del_tope():
    msg = _correo("default: False [-4.65 / 20.00]")
    razones = [
        "exceso-links(40)(+2)",
        "reply-to-diferente(x.example)(+2)",
        "sin-dkim-spf(+2)",
    ]
    assert rv.rescatar_por_rspamd(msg, rv.TOPE_INDICIOS_DEBILES, razones)[0] is False


def test_los_descuentos_no_impiden_el_rescate():
    msg = _correo("default: False [-1.20 / 20.00]")
    razones = [
        "exceso-links(30)(+2)",
        "reply-to-diferente(x.example)(+2)",
        "whitelist-dominio:ejemplo.org",
    ]
    assert rv.rescatar_por_rspamd(msg, 3, razones)[0] is True
