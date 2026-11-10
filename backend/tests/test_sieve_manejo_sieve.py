"""ManageSieve que rechaza la autenticación: 424 con aviso claro, nunca 401 (que expulsaba).

Levanta un servidor ManageSieve de mentira en un puerto libre de localhost.
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.sieve import router as sieve_router


async def _servidor_falso(acepta: bool):
    """Un ManageSieve mínimo: saluda, responde a AUTHENTICATE y a GETSCRIPT."""

    async def atender(reader, writer):
        writer.write(b'"IMPLEMENTATION" "Falso"\r\n"SASL" "PLAIN"\r\nOK "Listo"\r\n')
        await writer.drain()
        while True:
            linea = await reader.readline()
            if not linea:
                break
            if linea.startswith(b"AUTHENTICATE"):
                writer.write(b'OK "Autenticado"\r\n' if acepta else b'NO "Authentication failed."\r\n')
            elif linea.startswith(b"GETSCRIPT"):
                writer.write(b'NO (NONEXISTENT) "Script not found"\r\n')
            elif linea.startswith(b"LOGOUT"):
                writer.write(b'OK "Hasta luego"\r\n')
                await writer.drain()
                break
            else:
                writer.write(b'NO "Orden desconocida"\r\n')
            await writer.drain()
        writer.close()

    servidor = await asyncio.start_server(atender, "127.0.0.1", 0)
    return servidor, servidor.sockets[0].getsockname()[1]


class PeticionFalsa:
    class app:
        class state:
            redis = None
            db_pool = None


@pytest.fixture
def sesion(monkeypatch):
    async def contrasena(request, username):
        return "clave-que-no-vale-para-sieve"

    monkeypatch.setattr(sieve_router, "get_user_password", contrasena)


async def test_autenticacion_rechazada_da_424_y_no_401(monkeypatch, sesion):
    servidor, puerto = await _servidor_falso(acepta=False)
    monkeypatch.setattr(sieve_router, "SIEVE_PORT", puerto)
    try:
        with pytest.raises(HTTPException) as exc:
            await sieve_router.list_filters(PeticionFalsa(), "test@example.org")
        assert exc.value.status_code == 424
        assert exc.value.detail.startswith("No se pudo conectar con el servicio de reglas de correo")
        assert "borrado" in exc.value.detail
    finally:
        servidor.close()
        await servidor.wait_closed()


async def test_autenticacion_rechazada_se_registra(monkeypatch, sesion, caplog):
    servidor, puerto = await _servidor_falso(acepta=False)
    monkeypatch.setattr(sieve_router, "SIEVE_PORT", puerto)
    try:
        with caplog.at_level("WARNING", logger="sieve"):
            with pytest.raises(HTTPException):
                await sieve_router.get_vacation(PeticionFalsa(), "test@example.org")
        assert any("ManageSieve rechazó" in r.getMessage() and "test@example.org" in r.getMessage() for r in caplog.records)
    finally:
        servidor.close()
        await servidor.wait_closed()


async def test_sin_script_devuelve_lista_vacia(monkeypatch, sesion):
    servidor, puerto = await _servidor_falso(acepta=True)
    monkeypatch.setattr(sieve_router, "SIEVE_PORT", puerto)
    try:
        assert await sieve_router.list_filters(PeticionFalsa(), "test@example.org") == []
    finally:
        servidor.close()
        await servidor.wait_closed()


async def test_servidor_caido_da_502_con_el_mismo_aviso(monkeypatch, sesion):
    servidor, puerto = await _servidor_falso(acepta=True)
    servidor.close()
    await servidor.wait_closed()
    monkeypatch.setattr(sieve_router, "SIEVE_PORT", puerto)
    with pytest.raises(HTTPException) as exc:
        await sieve_router.list_filters(PeticionFalsa(), "test@example.org")
    assert exc.value.status_code == 502
    assert exc.value.detail == sieve_router.DETALLE_SIEVE_NO_DISPONIBLE
