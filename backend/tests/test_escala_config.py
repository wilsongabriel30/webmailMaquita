"""Configuración de gran escala: Redis Sentinel y PgBouncer.

Lo de serie (REDIS_URL simple, sin PGBOUNCER) tiene que quedar exactamente igual.
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace

import pytest

from app import database
from app.escala.redis_conexion import crear_cliente, leer_config
from tests._escala_servicios import puerto_libre


def _ajustes(**kw):
    base = dict(
        redis_url="",
        redis_sentinels="",
        redis_sentinel_master="mymaster",
        redis_sentinel_password="",
        pgbouncer=False,
        db_pool_min=2,
        db_pool_max=10,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ── Redis ────────────────────────────────────────────────────────────────


def test_redis_simple_es_lo_de_serie():
    cfg = leer_config(_ajustes(redis_url="redis://:clave@127.0.0.1:6379/0"))
    assert cfg.modo == "simple"
    assert cfg.url == "redis://:clave@127.0.0.1:6379/0"


def test_url_sentinel_completa():
    cfg = leer_config(
        _ajustes(
            redis_url="redis+sentinel://:cl%40ve@c1.example.org:26379,c2.example.org,"
            "[2001:db8::1]:26380/principal/3?sentinel_password=secreto"
        )
    )
    assert cfg.modo == "sentinel"
    assert cfg.centinelas == [
        ("c1.example.org", 26379),
        ("c2.example.org", 26379),
        ("2001:db8::1", 26380),
    ]
    assert cfg.principal == "principal"
    assert cfg.db == 3
    assert cfg.clave == "cl@ve"
    assert cfg.clave_centinela == "secreto"


def test_url_sentinel_sin_clave_toma_el_maestro_por_defecto():
    cfg = leer_config(_ajustes(redis_url="redis+sentinel://192.0.2.10:26379"))
    assert cfg.centinelas == [("192.0.2.10", 26379)]
    assert cfg.principal == "mymaster" and cfg.db == 0 and cfg.clave is None


def test_variables_sentinel_con_clave_de_redis_url():
    cfg = leer_config(
        _ajustes(
            redis_url="redis://:clave@ignorado:6379/2",
            redis_sentinels="192.0.2.10:26379, 192.0.2.11:26379",
            redis_sentinel_master="correo",
            redis_sentinel_password="cent",
        )
    )
    assert cfg.modo == "sentinel"
    assert cfg.centinelas == [("192.0.2.10", 26379), ("192.0.2.11", 26379)]
    assert (cfg.principal, cfg.db, cfg.clave, cfg.clave_centinela) == (
        "correo",
        2,
        "clave",
        "cent",
    )


def test_sentinel_sin_centinelas_falla_claro():
    with pytest.raises(ValueError):
        leer_config(_ajustes(redis_url="redis+sentinel:///mymaster"))


def test_cliente_sentinel_se_construye():
    from redis.asyncio import Redis

    cfg = leer_config(_ajustes(redis_sentinels="192.0.2.10:26379"))
    cliente = crear_cliente(cfg)
    assert isinstance(cliente, Redis)
    assert cliente.connection_pool.service_name == "mymaster"


@pytest.fixture
def sentinel_real():
    """Un Redis principal y un centinela de verdad (si hay redis-server)."""
    binario = shutil.which("redis-server")
    if not binario:
        pytest.skip("Sin redis-server para probar Sentinel")
    dir_ = tempfile.mkdtemp(prefix="sentinel-pruebas-")
    p_redis, p_cent = puerto_libre(), puerto_libre()
    conf = os.path.join(dir_, "sentinel.conf")
    with open(conf, "w") as f:
        f.write(
            f"port {p_cent}\nbind 127.0.0.1\ndir {dir_}\n"
            f"sentinel monitor pruebas 127.0.0.1 {p_redis} 1\n"
        )
    procs = [
        subprocess.Popen(
            [binario, "--port", str(p_redis), "--bind", "127.0.0.1", "--save", "",
             "--dir", dir_],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            [binario, conf, "--sentinel"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ]
    time.sleep(0.6)
    yield p_cent
    for p in procs:
        p.terminate()
        p.wait(timeout=5)
    shutil.rmtree(dir_, ignore_errors=True)


async def test_cliente_sentinel_habla_con_el_principal(sentinel_real):
    cfg = leer_config(
        _ajustes(redis_url=f"redis+sentinel://127.0.0.1:{sentinel_real}/pruebas/0")
    )
    cliente = crear_cliente(cfg)
    for _ in range(20):
        try:
            assert await cliente.set("escala:prueba", "ok")
            break
        except Exception:
            await asyncio.sleep(0.2)
    assert await cliente.get("escala:prueba") == "ok"
    await cliente.aclose()


# ── PostgreSQL / PgBouncer ───────────────────────────────────────────────


def test_pool_de_serie_sin_cambios():
    op = database.opciones_pool(_ajustes())
    assert op == {"min_size": 2, "max_size": 10}


def test_pool_con_pgbouncer_apaga_sentencias_preparadas():
    op = database.opciones_pool(_ajustes(pgbouncer=True))
    assert op["statement_cache_size"] == 0
    assert op["max_cached_statement_lifetime"] == 0


def test_pool_tamano_coherente():
    op = database.opciones_pool(_ajustes(db_pool_min=5, db_pool_max=3))
    assert op == {"min_size": 5, "max_size": 5}
    assert database.opciones_pool(_ajustes(), 1, 2) == {"min_size": 1, "max_size": 2}


def test_pgbouncer_se_lee_del_entorno(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("PGBOUNCER", "true")
    monkeypatch.setenv("DB_POOL_MAX", "40")
    s = Settings()
    assert s.pgbouncer is True and s.db_pool_max == 40
    monkeypatch.delenv("PGBOUNCER")
    assert Settings().pgbouncer is False


async def test_create_db_pool_pasa_las_opciones(monkeypatch):
    capturado = {}

    async def falso(dsn, **kw):
        capturado.update(kw, dsn=dsn)
        return "pool"

    monkeypatch.setattr(database.asyncpg, "create_pool", falso)
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(
            **vars(_ajustes(pgbouncer=True)),
            database_url="postgresql://u:c@192.0.2.5:6432/maildb",
            database_url_lectura="",
        ),
    )
    assert await database.create_db_pool() == "pool"
    assert capturado["dsn"].startswith("postgres://")
    assert capturado["statement_cache_size"] == 0
    assert await database.create_read_pool() is None


def test_pool_lectura_cae_en_la_principal():
    estado = SimpleNamespace(db_pool="principal")
    assert database.pool_lectura(estado) == "principal"
    estado.db_pool_lectura = "replica"
    assert database.pool_lectura(estado) == "replica"


def test_nada_del_backend_usa_sentencias_incompatibles():
    """En modo «transaction» no valen LISTEN, SET de sesión, PREPARE ni bloqueos
    consultivos de sesión. Si alguien los añade, que lo haga a sabiendas."""
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parent.parent / "app"
    prohibido = re.compile(
        r"pg_advisory_lock\(|pg_advisory_unlock\(|\bLISTEN\s|add_listener\(|\.prepare\(|"
        r"[\"']SET (SESSION|search_path)",
    )
    culpables = [
        str(p.relative_to(raiz))
        for p in raiz.rglob("*.py")
        if prohibido.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert culpables == []
