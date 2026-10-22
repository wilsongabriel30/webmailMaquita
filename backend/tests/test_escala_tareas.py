"""Las tareas de fondo no se repiten aunque haya varios workers (o varias máquinas).

Cada «worker» se simula con su propio objeto o su propio bucle sobre el mismo Redis real.
"""

import asyncio
from types import SimpleNamespace

from app.compliance import fraud_detector as fd
from app.escala import tareas_fondo
from app.rag import ingest
from app.safelinks import threatfeeds


async def _limpiar(redis, *claves):
    await redis.delete(*claves)


async def test_detector_de_fraude_una_revision_por_intervalo(redis, monkeypatch):
    await _limpiar(redis, "bloqueo:fraude:revision")
    revisiones = []

    async def revisar(self):
        revisiones.append(id(self))

    monkeypatch.setattr(fd.FraudDetector, "_revisar", revisar)
    workers = [fd.FraudDetector(None, redis) for _ in range(4)]
    tareas = [asyncio.create_task(w.start()) for w in workers]
    await asyncio.sleep(0.3)
    for w, t in zip(workers, tareas):
        w.stop()
        t.cancel()
    await asyncio.gather(*tareas, return_exceptions=True)
    assert len(revisiones) == 1
    await _limpiar(redis, "bloqueo:fraude:revision")


async def test_detector_sin_redis_se_comporta_como_antes(monkeypatch):
    revisiones = []

    async def revisar(self):
        revisiones.append(1)

    monkeypatch.setattr(fd.FraudDetector, "_revisar", revisar)
    d = fd.FraudDetector(None)
    t = asyncio.create_task(d.start())
    await asyncio.sleep(0.05)
    d.stop()
    t.cancel()
    await asyncio.gather(t, return_exceptions=True)
    assert revisiones == [1]


async def test_listas_de_amenazas_se_descargan_una_vez(redis, monkeypatch):
    await _limpiar(redis, "bloqueo:threatfeeds:refresco")
    descargas = []

    async def refresh(r, db=None):
        descargas.append(1)
        return {}

    monkeypatch.setattr(threatfeeds, "refresh", refresh)
    monkeypatch.setattr(threatfeeds, "ESPERA_INICIAL_S", 0)
    monkeypatch.setattr(threatfeeds, "REVISION_S", 0.05)
    app = SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=None))
    tareas = [asyncio.create_task(threatfeeds.loop(app)) for _ in range(4)]
    await asyncio.sleep(0.4)  # varias revisiones por worker; el intervalo es de 12 h
    for t in tareas:
        t.cancel()
    await asyncio.gather(*tareas, return_exceptions=True)
    assert descargas == [1]
    await _limpiar(redis, "bloqueo:threatfeeds:refresco")


async def test_lector_de_registro_un_solo_worker_por_maquina(redis, monkeypatch):
    arrancados, parados = [], []

    class _Ingestor:
        def stop(self):
            parados.append(self)

    async def start_log_ingestor(db_pool):
        i = _Ingestor()
        arrancados.append(i)
        return i

    import app.log_ingestor.mail_log_ingestor as mli

    monkeypatch.setattr(mli, "start_log_ingestor", start_log_ingestor)
    monkeypatch.setattr(tareas_fondo, "nodo_id", lambda: "nodo-prueba")
    await _limpiar(redis, "bloqueo:log_ingestor:nodo-prueba")
    app = SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=None))
    lideres = [tareas_fondo.iniciar_lector_registro(app) for _ in range(4)]
    await asyncio.sleep(0.2)
    assert len(arrancados) == 1
    assert sum(1 for x in lideres if x.es_lider) == 1
    for x in lideres:
        await x.detener()
    assert parados == arrancados


async def test_progreso_rag_visible_desde_otro_proceso(redis, monkeypatch):
    usuario = "ana@example.org"
    await _limpiar(redis, ingest.CLAVE_REDIS.format(usuario))
    soltar = asyncio.Event()

    async def ingest_user(db, username, limit=None, redis=None):
        await soltar.wait()

    monkeypatch.setattr(ingest, "ingest_user", ingest_user)
    assert await ingest.lanzar_en_segundo_plano(None, usuario, redis)
    # «Otro worker»: no tiene nada en memoria, pero ve la sincronización en Redis
    ingest._PROGRESO.pop(usuario, None)
    visto = await ingest.progreso_compartido(usuario, redis)
    assert visto and visto["estado"] == "en_curso"
    assert not await ingest.lanzar_en_segundo_plano(None, usuario, redis)
    soltar.set()
    await asyncio.sleep(0)
    await _limpiar(redis, ingest.CLAVE_REDIS.format(usuario))


async def test_progreso_rag_sin_redis_es_el_de_siempre(monkeypatch):
    usuario = "luis@example.org"
    ingest._PROGRESO.pop(usuario, None)

    async def ingest_user(db, username, limit=None, redis=None):
        return None

    monkeypatch.setattr(ingest, "ingest_user", ingest_user)
    assert await ingest.lanzar_en_segundo_plano(None, usuario)
    assert (await ingest.progreso_compartido(usuario))["estado"] == "en_curso"
    await asyncio.sleep(0)
