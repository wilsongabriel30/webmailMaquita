"""¿Existe el buzón virtual «Virtual.Todo»? (informe de Andes, 15/11/2026)."""

import asyncio
from types import SimpleNamespace

from app.mail.services import buzon_virtual as bv


class _Redis:
    def __init__(self):
        self.datos, self.caducidad = {}, {}

    async def get(self, clave):
        return self.datos.get(clave)

    async def set(self, clave, valor, ex=None):
        self.datos[clave], self.caducidad[clave] = valor, ex


class _Imap:
    """`lista`: lo que responde LIST; `status`: resultado de STATUS; `tarda`: segundos por orden."""

    def __init__(self, lista=(), status="NO", tarda=0.0):
        self.lista, self.resultado_status, self.tarda = list(lista), status, tarda
        self.ordenes: list[str] = []
        self.protocol = SimpleNamespace(
            transport=SimpleNamespace(close=lambda: self.ordenes.append("cerrada"))
        )

    async def list(self, _ref, patron):
        self.ordenes.append(f"list {patron}")
        await asyncio.sleep(self.tarda)
        return SimpleNamespace(result="OK", lines=self.lista + [b"List completed."])

    async def status(self, carpeta, _campos):
        self.ordenes.append(f"status {carpeta}")
        return SimpleNamespace(result=self.resultado_status, lines=[])


async def test_existe_si_el_servidor_lo_lista_y_no_hace_falta_abrirlo():
    imap = _Imap([b'(\\HasNoChildren) "." Virtual.Todo'])
    assert await bv.existe(imap) is True
    assert imap.ordenes == ["list Virtual.Todo"]


async def test_si_no_lo_lista_se_confirma_con_status():
    assert await bv.existe(_Imap([], status="OK")) is True
    imap = _Imap([], status="NO")
    assert await bv.existe(imap) is False
    assert imap.ordenes == ["list Virtual.Todo", "status Virtual.Todo"]


async def test_un_nombre_que_no_es_buzon_no_cuenta():
    assert await bv.existe(_Imap([b'(\\Noselect) "." Virtual.Todo'])) is False
    assert await bv.existe(_Imap([b'(\\NonExistent) "." Virtual.Todo'])) is False


async def test_se_recuerda_mas_tiempo_el_si_que_el_no():
    redis = _Redis()
    con = _Imap([b'(\\HasNoChildren) "." Virtual.Todo'])
    assert await bv.existe(con, redis, "Ana@Example.org") is True
    assert redis.datos == {"buzon_virtual:ana@example.org": "1"}
    assert (
        await bv.existe(_Imap([]), redis, "ana@example.org") is True
    ), "sale de la memoria"

    sin = _Imap([])
    assert await bv.existe(sin, redis, "luis@example.org") is False
    assert redis.datos["buzon_virtual:luis@example.org"] == "0"
    assert (
        redis.caducidad["buzon_virtual:luis@example.org"]
        < redis.caducidad["buzon_virtual:ana@example.org"]
    )
    assert await bv.existe(_Imap([], status="OK"), redis, "luis@example.org") is False


async def test_la_memoria_de_redis_puede_venir_en_bytes():
    redis = _Redis()
    redis.datos["buzon_virtual:ana@example.org"] = b"1"
    imap = _Imap([])
    assert await bv.existe(imap, redis, "ana@example.org") is True
    assert imap.ordenes == []


async def test_si_el_servidor_no_contesta_no_hay_y_no_se_recuerda(monkeypatch):
    monkeypatch.setattr(bv, "TOPE_S", 0.05)
    redis, imap = _Redis(), _Imap([], tarda=1.0)
    assert await bv.existe(imap, redis, "ana@example.org") is False
    assert redis.datos == {}, "la próxima vez se vuelve a preguntar"
    assert "cerrada" in imap.ordenes and imap.conexion_sucia is True


def test_las_capacidades_dicen_si_hay_todas_las_carpetas():
    import inspect

    from app.mail.routers import busqueda_capacidades as r

    assert '"todas_las_carpetas"' in inspect.getsource(r.capacidades_de_busqueda)
