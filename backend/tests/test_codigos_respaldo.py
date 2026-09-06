"""H-03 (cuarta revisión): códigos de respaldo de 128 bits, hash con sal, un solo uso atómico."""

import asyncio
import hashlib

import pytest
from app.auth import codigos_respaldo as cr

pytestmark = pytest.mark.asyncio


class _BD:
    """Doble mínimo de asyncpg para la tabla user_totp_backup_codes."""

    def __init__(self):
        self.filas: list[dict] = []
        self._id = 0

    async def execute(self, sql, *p):
        s = " ".join(sql.split())
        if s.startswith("CREATE TABLE"):
            return
        if s.startswith("DELETE FROM user_totp_backup_codes"):
            self.filas = [f for f in self.filas if f["username"] != p[0]]
            return
        if s.startswith("INSERT INTO user_totp_backup_codes"):
            self._id += 1
            self.filas.append(
                {
                    "id": self._id,
                    "username": p[0],
                    "sal": p[1],
                    "code_hash": p[2],
                    "used_at": None,
                }
            )
            return
        raise AssertionError(s)

    async def fetch(self, sql, *p):
        assert "used_at IS NULL" in sql
        return [f for f in self.filas if f["username"] == p[0] and f["used_at"] is None]

    async def fetchrow(self, sql, *p):
        s = " ".join(sql.split())
        if s.startswith("UPDATE user_totp_backup_codes SET used_at"):
            for f in self.filas:
                if f["id"] == p[0] and f["used_at"] is None:
                    f["used_at"] = "ahora"
                    return {"id": f["id"]}
            return None
        if s.startswith("SELECT count(*)"):
            return {"n": len(await self.fetch("used_at IS NULL", p[0]))}
        raise AssertionError(s)


def test_generar_128_bits_y_formato():
    codigos = cr.generar()
    assert len(codigos) == 8 and len(set(codigos)) == 8
    for c in codigos:
        assert len(cr.normalizar(c)) == 32  # 128 bits en hexadecimal
        assert cr.es_formato(c) and cr.es_formato(c.lower().replace("-", " "))
    assert not cr.es_formato("A1B2C3D4")  # formato antiguo (32 bits)


def test_hash_con_sal_no_es_sha256_ni_se_repite():
    h1 = cr.hash_codigo("AAAA-BBBB", "00" * 16)
    h2 = cr.hash_codigo("AAAA-BBBB", "11" * 16)
    assert h1 != h2
    assert h1 != hashlib.sha256(b"AAAABBBB").hexdigest()
    assert cr.hash_codigo("aaaa bbbb", "00" * 16) == h1  # normalizado


async def test_guardar_consumir_una_sola_vez():
    bd = _BD()
    codigos = cr.generar()
    await cr.guardar(bd, "ana@example.com", codigos)
    assert all(f["code_hash"] != cr.normalizar(c) for f, c in zip(bd.filas, codigos))
    assert await cr.restantes(bd, "ana@example.com") == 8
    assert await cr.consumir(bd, "ana@example.com", codigos[0].lower()) is True
    assert await cr.consumir(bd, "ana@example.com", codigos[0]) is False  # ya usado
    assert await cr.consumir(bd, "ana@example.com", codigos[1][:-1] + "0") is False
    assert (
        await cr.consumir(bd, "otra@example.com", codigos[2]) is False
    )  # de otra persona
    assert await cr.restantes(bd, "ana@example.com") == 7


async def test_consumo_concurrente_solo_uno_gana():
    bd = _BD()
    codigos = cr.generar()
    await cr.guardar(bd, "ana@example.com", codigos)
    resultados = await asyncio.gather(
        *[cr.consumir(bd, "ana@example.com", codigos[3]) for _ in range(5)]
    )
    assert resultados.count(True) == 1


async def test_regenerar_invalida_los_anteriores():
    bd = _BD()
    viejos = cr.generar()
    await cr.guardar(bd, "ana@example.com", viejos)
    nuevos = cr.generar()
    await cr.guardar(bd, "ana@example.com", nuevos)
    assert await cr.consumir(bd, "ana@example.com", viejos[0]) is False
    assert await cr.consumir(bd, "ana@example.com", nuevos[0]) is True
