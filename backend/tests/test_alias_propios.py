"""Los alias personales se informan; si la consulta falla, la lista de cuentas no se rompe."""

import asyncio

from app.mail.services.alias_propios import alias_de


class _Db:
    def __init__(self, filas=None, falla=False):
        self.filas = filas or []
        self.falla = falla
        self.consulta = ""

    async def fetch(self, consulta, *_):
        if self.falla:
            raise RuntimeError("sin base de datos")
        self.consulta = consulta
        return self.filas


def test_devuelve_las_direcciones():
    db = _Db([{"direccion": "ana@example.org"}, {"direccion": "ana@example.net"}])
    assert asyncio.run(alias_de(db, "ana@example.com")) == ["ana@example.org", "ana@example.net"]


def test_solo_alias_que_entregan_a_esa_unica_cuenta():
    db = _Db()
    asyncio.run(alias_de(db, "ana@example.com"))
    assert "btrim(goto)) = lower($1)" in db.consulta


def test_si_falla_la_base_devuelve_lista_vacia():
    assert asyncio.run(alias_de(_Db(falla=True), "ana@example.com")) == []
