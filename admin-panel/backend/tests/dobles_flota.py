"""Dobles para las pruebas de Flota: una base simulada (con transacciones) y una clave de firma de usar y tirar."""

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ADMIN = {
    "id": 1,
    "username": "ana",
    "role": "superadmin",
    "session_id": 1,
    "totp": True,
}
EQUIPO = "11111111-2222-4333-8444-555555555555"
OTRO = "99999999-2222-4333-8444-555555555555"
GUID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


class _Contexto:
    def __init__(self, valor=None):
        self.valor = valor

    async def __aenter__(self):
        return self.valor

    async def __aexit__(self, *_):
        return False


class BaseFalsa:
    """Responde según un trozo de la consulta y apunta todo lo ejecutado. Sirve de pool y de conexión."""

    def __init__(self):
        self.ejecutado: list[tuple[str, tuple]] = []
        self.filas: dict = {}
        self.fila: dict = {}

    def _buscar(self, tabla, sql, defecto):
        for clave, valor in tabla.items():
            if clave in sql:
                return valor
        return defecto

    def acquire(self):
        return _Contexto(self)

    def transaction(self):
        return _Contexto()

    async def fetch(self, sql, *args):
        self.ejecutado.append((sql, args))
        return self._buscar(self.filas, sql, [])

    async def fetchrow(self, sql, *args):
        self.ejecutado.append((sql, args))
        return self._buscar(self.fila, sql, None)

    async def fetchval(self, sql, *args):
        self.ejecutado.append((sql, args))
        return None

    async def execute(self, sql, *args):
        self.ejecutado.append((sql, args))
        return "UPDATE 1"

    def con(self, trozo: str) -> list[tuple]:
        return [a for s, a in self.ejecutado if trozo in s]

    def todo_como_texto(self) -> str:
        return json.dumps(self.ejecutado, default=str, ensure_ascii=False)


def clave_de_firma(tmp_path, monkeypatch):
    """Clave ECDSA P-256 de pruebas en un fichero temporal, puesta como clave de firma de Flota."""
    from app.flota import firma

    ruta = tmp_path / "orden-firma.key"
    ruta.write_bytes(
        ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    monkeypatch.setattr(firma, "RUTA", str(ruta))
    firma._privada.cache_clear()
    return firma


def leer_carga(carga_b64: str) -> dict:
    return json.loads(base64.b64decode(carga_b64))
