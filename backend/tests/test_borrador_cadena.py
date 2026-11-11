"""Un borrador, una sola copia: UID viejo → vigente, «nuevo» repetido y candado por persona."""

import asyncio

from app.mail.services import borrador_cadena as bc


class _Redis:
    def __init__(self):
        self.d = {}

    async def set(self, k, v, nx=False, px=None, ex=None):
        if nx and k in self.d:
            return None
        self.d[k] = v
        return True

    async def get(self, k):
        return self.d.get(k)

    async def delete(self, k):
        self.d.pop(k, None)


class _RedisRoto:
    async def set(self, *a, **k):
        raise RuntimeError("sin redis")

    get = delete = set


async def test_uid_viejo_se_traduce_al_vigente():
    r = _Redis()
    await bc.anotar(r, "ana@x", "h", 106, 105)
    await bc.anotar(r, "ana@x", "h", 107, 106)
    assert await bc.vigente(r, "ana@x", 105) == 107
    assert await bc.vigente(r, "ana@x", 107) == 107
    assert await bc.vigente(r, "ana@x", 999) == 999
    assert await bc.vigente(r, "otra@x", 105) == 105
    assert await bc.vigente(r, "ana@x", None) is None


async def test_borrador_nuevo_igual_reemplaza_al_recien_creado():
    r = _Redis()
    h = bc.huella("Re: Datos", ["B@x.co", "a@x.co"], "<m1>")
    assert h == bc.huella(" Re: Datos ", ["a@x.co", "b@x.co"], "<m1>")
    assert h != bc.huella("Re: Datos", ["a@x.co"], "<m1>")
    assert await bc.recien_creado(r, "ana@x", h) is None
    await bc.anotar(r, "ana@x", h, 105)
    assert await bc.recien_creado(r, "ana@x", h) == 105


async def test_candado_pone_en_fila_y_sin_redis_no_estorba():
    r, orden = _Redis(), []

    async def guardar(nombre, espera):
        async with bc.candado(r, "ana@x"):
            orden.append(nombre + ":entra")
            await asyncio.sleep(espera)
            orden.append(nombre + ":sale")

    await asyncio.gather(guardar("a", 0.12), guardar("b", 0.0))
    assert orden in (
        ["a:entra", "a:sale", "b:entra", "b:sale"],
        ["b:entra", "b:sale", "a:entra", "a:sale"],
    )
    assert not [k for k in r.d if "candado" in k]
    async with bc.candado(_RedisRoto(), "ana@x"):
        pass
    assert await bc.vigente(_RedisRoto(), "ana@x", 5) == 5
    await bc.anotar(_RedisRoto(), "ana@x", "h", 6, 5)
