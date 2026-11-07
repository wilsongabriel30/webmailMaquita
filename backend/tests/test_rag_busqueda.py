"""Búsqueda RAG: exacta en buzones pequeños, HNSW iterativo en los grandes (con respaldo)."""

from contextlib import asynccontextmanager

from app.rag import busqueda


class FakeCon:
    def __init__(self, total, filas_hnsw):
        self.total, self.filas_hnsw, self.sql = total, filas_hnsw, []

    async def fetchval(self, sql, *a):
        return self.total

    async def execute(self, sql, *a):
        self.sql.append(sql)

    async def fetch(self, sql, *a):
        self.sql.append(sql)
        if "MATERIALIZED" in sql:
            return self.filas_hnsw
        return [{"folder": "Sent", "msg_uid": "1"}] * a[2]

    def transaction(self):
        @asynccontextmanager
        async def t():
            yield

        return t()


class FakePool:
    def __init__(self, con):
        self.con = con

    def acquire(self):
        @asynccontextmanager
        async def a():
            yield self.con

        return a()


async def test_buzon_pequeno_usa_busqueda_exacta():
    con = FakeCon(total=800, filas_hnsw=[])
    filas = await busqueda.buscar(FakePool(con), "ana@x", [0.1, 0.2], k=6)
    assert len(filas) == 6
    assert not any("MATERIALIZED" in s for s in con.sql)
    assert any("+ 0" in s for s in con.sql)


async def test_buzon_grande_usa_hnsw_iterativo_y_respaldo_si_faltan():
    con = FakeCon(total=200000, filas_hnsw=[{"folder": "INBOX", "msg_uid": "9"}] * 6)
    filas = await busqueda.buscar(FakePool(con), "ana@x", [0.1], k=6)
    assert filas[0]["msg_uid"] == "9"
    assert any("iterative_scan" in s for s in con.sql)
    con = FakeCon(total=200000, filas_hnsw=[{"folder": "INBOX", "msg_uid": "9"}])
    filas = await busqueda.buscar(FakePool(con), "ana@x", [0.1], k=6)
    assert len(filas) == 6 and filas[0]["folder"] == "Sent"  # completó con la exacta
