"""Bloqueo distribuido (Redis SET NX + caducidad) y elección de líder.

Se prueba contra un Redis real (temporal o el del CI): el comportamiento que importa
(atomicidad de SET NX, scripts Lua de renovar/liberar) es el del servidor.
"""

import asyncio
import os
import subprocess
import sys
import uuid

import pytest
import redis.asyncio as aioredis

from app.escala import bloqueo as bl


def _nombre() -> str:
    return f"prueba:{uuid.uuid4().hex}"


async def test_adquirir_es_exclusivo_y_solo_libera_el_titular(redis):
    n = _nombre()
    t1 = await bl.adquirir(redis, n, 10)
    assert t1
    assert await bl.adquirir(redis, n, 10) is None
    # Otro testigo no puede liberarlo ni renovarlo
    assert not await bl.liberar(redis, n, "intruso")
    assert not await bl.renovar(redis, n, "intruso", 10)
    assert await bl.titular(redis, n) == t1
    assert await bl.liberar(redis, n, t1)
    assert await bl.adquirir(redis, n, 10)


async def test_el_bloqueo_caduca_solo(redis):
    n = _nombre()
    assert await bl.adquirir(redis, n, 0.2)
    await asyncio.sleep(0.35)
    assert await bl.adquirir(redis, n, 10)


async def test_concurrencia_un_solo_ganador(redis):
    n = _nombre()
    testigos = await asyncio.gather(*(bl.adquirir(redis, n, 10) for _ in range(25)))
    assert sum(1 for t in testigos if t) == 1


async def test_bloqueo_se_renueva_mientras_dura_el_bloque(redis):
    n = _nombre()
    async with bl.bloqueo(redis, n, ttl_s=0.3) as b:
        assert b.obtenido
        await asyncio.sleep(0.8)  # más que el ttl: sin renovación se habría perdido
        assert not b.perdido
        async with bl.bloqueo(redis, n, ttl_s=0.3) as otro:
            assert not otro.obtenido
    # Al salir se libera
    async with bl.bloqueo(redis, n, ttl_s=1) as b2:
        assert b2.obtenido


async def test_bloqueo_se_libera_aunque_el_bloque_falle(redis):
    n = _nombre()
    with pytest.raises(RuntimeError):
        async with bl.bloqueo(redis, n, ttl_s=5) as b:
            assert b.obtenido
            raise RuntimeError("fallo")
    assert await bl.titular(redis, n) is None


async def test_una_vez_por_intervalo(redis):
    n = _nombre()
    corridas = 0
    for _ in range(3):
        async with bl.una_vez_por_intervalo(redis, n, 0.5) as t:
            if t.obtenido:
                corridas += 1
    assert corridas == 1  # tres «workers» seguidos, una sola vuelta
    await asyncio.sleep(0.6)
    async with bl.una_vez_por_intervalo(redis, n, 0.5) as t:
        assert t.obtenido  # pasado el intervalo, toca otra vez


async def test_sin_redis_no_se_concede(redis):
    caido = aioredis.from_url(
        "redis://127.0.0.1:1/0", decode_responses=True, socket_connect_timeout=0.2
    )
    async with bl.bloqueo(caido, _nombre(), ttl_s=1) as b:
        assert not b.obtenido
    await caido.aclose()


async def test_lider_unico_y_relevo(redis):
    n = _nombre()
    arrancados, parados = [], []

    def hacer(etiqueta):
        async def arrancar():
            arrancados.append(etiqueta)
            return etiqueta

        return arrancar

    a = bl.Lider(redis, n, hacer("a"), parados.append, ttl_s=0.3, reintento_s=0.05)
    b = bl.Lider(redis, n, hacer("b"), parados.append, ttl_s=0.3, reintento_s=0.05)
    a.iniciar()
    await asyncio.sleep(0.15)
    b.iniciar()
    await asyncio.sleep(0.6)
    assert arrancados == ["a"] and a.es_lider and not b.es_lider
    await a.detener()  # el líder se apaga: suelta el bloqueo y el otro lo toma
    await asyncio.sleep(0.3)
    assert parados == ["a"]
    assert arrancados == ["a", "b"] and b.es_lider
    await b.detener()
    assert parados == ["a", "b"]
    assert await bl.titular(redis, n) is None


async def test_lider_que_pierde_el_bloqueo_para_el_trabajo(redis):
    n = _nombre()
    parados = []

    async def arrancar():
        return "trabajo"

    lider = bl.Lider(redis, n, arrancar, parados.append, ttl_s=0.3, reintento_s=10)
    lider.iniciar()
    await asyncio.sleep(0.1)
    assert lider.es_lider
    await redis.set(bl.PREFIJO + n, "otro-nodo")  # otro proceso se quedó con él
    await asyncio.sleep(0.3)
    assert parados == ["trabajo"] and not lider.es_lider
    await lider.detener()
    assert await bl.titular(redis, n) == "otro-nodo"  # nunca suelta el de otro


_HIJO = """
import asyncio, sys
import redis.asyncio as aioredis
from app.escala.bloqueo import una_vez_por_intervalo

async def main(url, nombre):
    r = aioredis.from_url(url, decode_responses=True)
    async with una_vez_por_intervalo(r, nombre, 30) as t:
        if t.obtenido:
            await r.incr(nombre + ":corridas")
            await asyncio.sleep(0.3)
    await r.aclose()

asyncio.run(main(sys.argv[1], sys.argv[2]))
"""


async def test_varios_procesos_una_sola_corrida(redis, url_redis):
    """Como varios workers de uvicorn (procesos distintos) en la misma máquina."""
    n = _nombre()
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    procs = [
        subprocess.Popen([sys.executable, "-c", _HIJO, url_redis, n], cwd=raiz)
        for _ in range(4)
    ]
    for p in procs:
        assert await asyncio.to_thread(p.wait, 30) == 0
    assert await redis.get(n + ":corridas") == "1"
