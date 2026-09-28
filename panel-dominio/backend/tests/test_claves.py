"""Hash de buzón compatible con Dovecot y hash del portal."""

import asyncio

from app import claves


def test_hash_de_buzon_valida_su_clave_y_no_otra():
    h = asyncio.run(claves.hash_buzon("Cafe-Molido.2026"))
    assert h.startswith("{SHA512-CRYPT}$6$")
    assert asyncio.run(claves.comprobar_buzon("Cafe-Molido.2026", h))
    assert not asyncio.run(claves.comprobar_buzon("Cafe-Molido.2027", h))


def test_dos_hashes_de_la_misma_clave_son_distintos():
    a = asyncio.run(claves.hash_buzon("Cafe-Molido.2026"))
    b = asyncio.run(claves.hash_buzon("Cafe-Molido.2026"))
    assert a != b


def test_clave_con_simbolos_raros():
    clave = "Ñandú $HOME `x` \"q\" 'r' -salt;"
    h = asyncio.run(claves.hash_buzon(clave))
    assert asyncio.run(claves.comprobar_buzon(clave, h))


def test_portal():
    h = claves.hash_portal("Cafe-Molido.2026")
    assert claves.comprobar_portal("Cafe-Molido.2026", h)
    assert not claves.comprobar_portal("otra", h)
    assert not claves.comprobar_portal("Cafe-Molido.2026", None)
