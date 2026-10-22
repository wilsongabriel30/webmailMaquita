"""Servicios reales (Redis, PostgreSQL) para las pruebas de gran escala.

Redis: PRUEBAS_REDIS_URL si está definida; si no, se arranca un `redis-server` temporal
(sin persistencia, en un puerto libre); si no hay binario, se prueba REDIS_URL (el CI
tiene un Redis de servicio). Si nada responde, la prueba se salta.

PostgreSQL: PRUEBAS_PG_URL o DATABASE_URL, solo si responde de verdad.
"""

import asyncio
import os
import shutil
import socket
import subprocess
import tempfile
import time

import pytest


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _responde(host: str, puerto: int) -> bool:
    try:
        with socket.create_connection((host, puerto), timeout=0.3):
            return True
    except OSError:
        return False


class RedisTemporal:
    def __init__(self):
        self.proc = None
        self.dir = None
        self.url = None

    def arrancar(self) -> str | None:
        propia = os.getenv("PRUEBAS_REDIS_URL")
        if propia:
            self.url = propia
            return propia
        binario = shutil.which("redis-server")
        if binario:
            self.dir = tempfile.mkdtemp(prefix="redis-pruebas-")
            puerto = puerto_libre()
            self.proc = subprocess.Popen(
                [binario, "--port", str(puerto), "--bind", "127.0.0.1", "--save", "",
                 "--appendonly", "no", "--dir", self.dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(50):
                if _responde("127.0.0.1", puerto):
                    self.url = f"redis://127.0.0.1:{puerto}/0"
                    return self.url
                time.sleep(0.05)
            self.parar()
        del_ci = os.getenv("REDIS_URL", "")
        if del_ci.startswith("redis://"):
            from urllib.parse import urlsplit

            p = urlsplit(del_ci)
            if _responde(p.hostname or "127.0.0.1", p.port or 6379):
                self.url = del_ci
                return del_ci
        return None

    def parar(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None


def url_pg() -> str | None:
    url = os.getenv("PRUEBAS_PG_URL") or os.getenv("DATABASE_URL") or ""
    if not url.startswith(("postgres://", "postgresql://")):
        return None

    async def _probar():
        import asyncpg

        con = await asyncio.wait_for(asyncpg.connect(url), 2)
        await con.close()

    try:
        asyncio.run(_probar())
        return url
    except Exception:
        return None


@pytest.fixture(scope="module")
def url_redis():
    r = RedisTemporal()
    url = r.arrancar()
    if not url:
        pytest.skip("No hay Redis para las pruebas (ni redis-server ni REDIS_URL)")
    yield url
    r.parar()


@pytest.fixture
async def redis(url_redis):
    import redis.asyncio as aioredis

    cliente = aioredis.from_url(url_redis, decode_responses=True)
    yield cliente
    await cliente.aclose()
