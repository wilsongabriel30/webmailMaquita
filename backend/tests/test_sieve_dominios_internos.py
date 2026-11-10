"""Dominios internos: una sola fuente para la política de reenvío y las alertas de fraude (C3)."""

import pytest

from app.compliance import fraud_detector
from app.security import account_protection
from app.sieve import dominios


class BaseFalsa:
    def __init__(self, filas=None, falla=False):
        self.filas = filas or []
        self.falla = falla
        self.consultas = 0
        self.ejecutadas: list = []

    async def fetch(self, sql, *args):
        self.consultas += 1
        if self.falla:
            raise RuntimeError("sin base")
        return [{"domain": d} for d in self.filas]

    async def fetchval(self, sql, *args):
        if "approved_forwards" in sql:
            return None
        if "fraud_alerts" in sql:
            return 0
        return None

    async def execute(self, sql, *args):
        self.ejecutadas.append((sql, args))


class RedisFalso:
    def __init__(self):
        self.listas: dict = {}
        self.contadores: dict = {}

    async def sismember(self, clave, valor):
        return False

    async def lpush(self, clave, valor):
        self.listas.setdefault(clave, []).insert(0, valor)

    async def ltrim(self, clave, a, b):
        pass

    async def incr(self, clave):
        self.contadores[clave] = self.contadores.get(clave, 0) + 1

    async def expire(self, clave, s):
        pass


@pytest.fixture(autouse=True)
def organizacion_de_prueba(monkeypatch):
    monkeypatch.setattr(
        dominios.organizacion, "dominios_propios", lambda: frozenset({"example.org"})
    )
    dominios.olvidar_cache()
    yield
    dominios.olvidar_cache()


async def test_sin_base_solo_los_de_la_organizacion():
    assert await dominios.dominios_internos(None) == frozenset({"example.org"})


async def test_une_organizacion_y_tabla_domain_con_cache():
    db = BaseFalsa(["Example.com", "example.net"])
    primero = await dominios.dominios_internos(db)
    assert primero == frozenset({"example.org", "example.com", "example.net"})
    await dominios.dominios_internos(db)
    await dominios.dominios_internos(db)
    assert db.consultas == 1, "la tabla se consulta una vez cada 10 minutos"
    dominios.olvidar_cache()
    await dominios.dominios_internos(db)
    assert db.consultas == 2


async def test_si_la_base_falla_se_responde_con_los_de_la_organizacion():
    assert await dominios.dominios_internos(BaseFalsa(falla=True)) == frozenset(
        {"example.org"}
    )


def test_dominio_de_direccion():
    assert dominios.dominio_de("Ana <ana@Example.ORG>") == "example.org"
    assert dominios.dominio_de("ana@example.com") == "example.com"
    assert dominios.dominio_de("sin arroba") == ""


async def test_es_interno():
    assert await dominios.es_interno("x@example.org") is True
    assert await dominios.es_interno("x@yahoo.com") is False


# ── Política de reenvío ───────────────────────────────────────────────────────


async def test_reenvio_a_dominio_propio_se_permite_sin_aprobacion():
    redis = RedisFalso()
    db = BaseFalsa(["example.com"])
    assert await account_protection.check_forward_policy(
        redis, "ana", "ana@example.org", db
    ) == {"allowed": True}
    assert await account_protection.check_forward_policy(
        redis, "ana", "Ana@Example.com", db
    ) == {"allowed": True}
    assert redis.listas == {}, "no se registra incidente"


async def test_reenvio_externo_sigue_requiriendo_aprobacion():
    redis = RedisFalso()
    resultado = await account_protection.check_forward_policy(
        redis, "ana", "ana@yahoo.com", BaseFalsa()
    )
    assert resultado["allowed"] is False
    assert "yahoo.com" in resultado["reason"]
    assert "security_incidents" in redis.listas


async def test_reenvio_externo_sin_base_tambien_se_bloquea():
    resultado = await account_protection.check_forward_policy(
        RedisFalso(), "ana", "a@gmail.com"
    )
    assert resultado["allowed"] is False


# ── Detector de fraude ────────────────────────────────────────────────────────


class BaseActividad(BaseFalsa):
    def __init__(self, actividad, dominios_tabla):
        super().__init__(dominios_tabla)
        self.actividad = actividad

    async def fetch(self, sql, *args):
        if "user_activity_log" in sql:
            return self.actividad
        return await super().fetch(sql, *args)


async def test_detector_no_alerta_por_reenvio_a_dominio_propio():
    db = BaseActividad(
        [
            {
                "username": "ana",
                "target": "jefe@example.com",
                "details": {},
                "ip_address": None,
            },
            {
                "username": "ana",
                "target": "Jefe <jefe@example.org>",
                "details": {},
                "ip_address": None,
            },
        ],
        ["example.com"],
    )
    detector = fraud_detector.FraudDetector(db)
    await detector._check_external_forwards()
    assert db.ejecutadas == []


async def test_detector_alerta_por_reenvio_externo():
    db = BaseActividad(
        [
            {
                "username": "ana",
                "target": "ana@yahoo.com",
                "details": {},
                "ip_address": None,
            }
        ],
        [],
    )
    detector = fraud_detector.FraudDetector(db)
    await detector._check_external_forwards()
    assert len(db.ejecutadas) == 1
    assert "fraud_alerts" in db.ejecutadas[0][0]
    assert db.ejecutadas[0][1][0] == "external_forward"
