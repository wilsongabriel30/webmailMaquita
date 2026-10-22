"""/api/salud, /api/listo, el alias /api/v1 y el DDL serializado compatible con PgBouncer."""

import asyncio
import time

import pytest

from app.escala import salud
from app.escala.api_v1 import ruta_sin_version
from app.escala.ddl import ddl_serializado
from app.main import app
from tests._escala_servicios import url_pg


class _PoolFalso:
    def __init__(self, responde=True, tarda=0.0):
        self.responde, self.tarda = responde, tarda

    async def fetchval(self, sql):
        await asyncio.sleep(self.tarda)
        if not self.responde:
            raise ConnectionError("sin base")
        return 1


class _RedisFalso:
    def __init__(self, responde=True):
        self.responde = responde

    async def ping(self):
        if not self.responde:
            raise ConnectionError("sin redis")
        return True


@pytest.fixture
def estado(monkeypatch, tmp_path):
    monkeypatch.setattr(salud, "ARCHIVO_DRENAJE", str(tmp_path / "drenar"))

    def poner(db=True, redis=True, tarda=0.0, cerrando=False):
        monkeypatch.setattr(app.state, "db_pool", _PoolFalso(db, tarda), raising=False)
        monkeypatch.setattr(app.state, "redis", _RedisFalso(redis), raising=False)
        monkeypatch.setattr(app.state, "cerrando", cerrando, raising=False)

    return poner


async def test_salud_responde_sin_base_ni_redis(client, estado):
    estado(db=False, redis=False)
    r = await client.get("/api/salud")
    assert r.status_code == 200 and r.json() == {"estado": "vivo"}
    assert r.headers["cache-control"] == "no-store"


async def test_listo_con_todo_bien(client, estado):
    estado()
    r = await client.get("/api/listo")
    assert r.status_code == 200 and r.json() == {"estado": "listo"}


@pytest.mark.parametrize("db,redis", [(False, True), (True, False), (False, False)])
async def test_listo_503_si_falta_algo(client, estado, db, redis):
    estado(db=db, redis=redis)
    r = await client.get("/api/listo")
    assert r.status_code == 503 and r.json() == {"estado": "no_listo"}
    assert "error" not in r.text.lower()  # público: sin mensajes internos


async def test_listo_no_se_cuelga_si_la_base_no_contesta(client, estado, monkeypatch):
    monkeypatch.setattr(salud, "ESPERA_S", 0.2)
    estado(tarda=5)
    t0 = time.monotonic()
    r = await client.get("/api/listo")
    assert r.status_code == 503 and time.monotonic() - t0 < 2


async def test_listo_503_en_drenaje_y_al_cerrar(client, estado, tmp_path):
    estado()
    (tmp_path / "drenar").write_text("")
    r = await client.get("/api/listo")
    assert r.status_code == 503 and r.json() == {"estado": "drenando"}
    (tmp_path / "drenar").unlink()
    estado(cerrando=True)
    assert (await client.get("/api/listo")).status_code == 503


async def test_listo_sin_estado_de_arranque(client, monkeypatch, tmp_path):
    monkeypatch.setattr(salud, "ARCHIVO_DRENAJE", str(tmp_path / "drenar"))
    monkeypatch.setattr(app.state, "db_pool", None, raising=False)
    monkeypatch.setattr(app.state, "redis", None, raising=False)
    assert (await client.get("/api/listo")).status_code == 503


# ── /api/v1 ──────────────────────────────────────────────────────────────


def test_ruta_sin_version():
    assert ruta_sin_version("/api/v1/mail/messages") == "/api/mail/messages"
    assert ruta_sin_version("/api/v1") == "/api"
    assert ruta_sin_version("/api/v10/x") is None
    assert ruta_sin_version("/api/mail") is None
    assert ruta_sin_version("/v1/api/x") is None


async def test_alias_v1_sirve_la_misma_ruta(client, estado):
    estado()
    r = await client.get("/api/v1/salud")
    assert r.status_code == 200 and r.json() == {"estado": "vivo"}
    assert r.headers["api-version"] == "1"
    assert "api-version" not in (await client.get("/api/salud")).headers


async def test_alias_v1_no_rompe_las_rutas_actuales(client):
    """El login responde igual por las dos rutas (aquí: cuerpo inválido → 400)."""
    a = await client.post("/api/auth/login", json={})
    b = await client.post("/api/v1/auth/login", json={})
    assert a.status_code == b.status_code == 400
    assert a.json() == b.json()


async def test_alias_v1_ruta_inexistente_es_404(client):
    assert (await client.get("/api/v1/no-existe-esta-ruta")).status_code == 404


# ── DDL serializado ──────────────────────────────────────────────────────


class _ConFalsa:
    def __init__(self, registro):
        self.registro = registro

    def transaction(self):
        registro = self.registro

        class _Tx:
            async def __aenter__(self):
                registro.append("BEGIN")

            async def __aexit__(self, *a):
                registro.append("ROLLBACK" if a[0] else "COMMIT")
                return False

        return _Tx()

    async def execute(self, sql, *args):
        self.registro.append((sql, args))


class _PoolDDL:
    def __init__(self):
        self.registro = []

    def acquire(self):
        con = _ConFalsa(self.registro)

        class _Ctx:
            async def __aenter__(self):
                return con

            async def __aexit__(self, *a):
                return False

        return _Ctx()


async def test_ddl_usa_bloqueo_de_transaccion():
    pool = _PoolDDL()
    async with ddl_serializado(pool, 815000) as con:
        await con.execute("CREATE TABLE IF NOT EXISTS x (id int)")
    assert pool.registro == [
        "BEGIN",
        ("SELECT pg_advisory_xact_lock($1)", (815000,)),
        ("CREATE TABLE IF NOT EXISTS x (id int)", ()),
        "COMMIT",
    ]


async def test_ddl_serializa_de_verdad_en_postgresql():
    """Con un PostgreSQL real (CI o PRUEBAS_PG_URL): dos «workers» no se solapan."""
    url = await asyncio.to_thread(url_pg)
    if not url:
        pytest.skip("Sin PostgreSQL accesible")
    import asyncpg

    pool = await asyncpg.create_pool(url, min_size=2, max_size=4, statement_cache_size=0)
    tramos = []

    async def worker(n):
        async with ddl_serializado(pool, 815999):
            inicio = time.monotonic()
            await asyncio.sleep(0.2)
            tramos.append((inicio, time.monotonic()))

    try:
        await asyncio.gather(worker(1), worker(2))
    finally:
        await pool.close()
    tramos.sort()
    assert tramos[0][1] <= tramos[1][0]  # el segundo empezó cuando acabó el primero
