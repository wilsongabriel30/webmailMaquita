"""Protección de salida — servicio del panel admin.

Invoca el helper privilegiado /usr/local/sbin/maquita-outbound vía sudo (acotado en
/etc/sudoers.d/maquita-outbound). El helper valida sus argumentos y es la única
superficie con privilegios; aquí solo orquestamos y devolvemos JSON.
"""
import asyncio
import json

HELPER = "/usr/local/sbin/maquita-outbound"


async def _run(*args: str) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "sudo", HELPER, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    text = (out or b"").decode().strip()
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        data = {"error": text or (err or b"").decode().strip() or "salida no válida"}
    if isinstance(data, dict) and data.get("error"):
        raise ValueError(data["error"])
    if proc.returncode != 0:
        raise ValueError((err or b"").decode().strip() or "fallo en maquita-outbound")
    return data


async def get_limits() -> dict:
    return await _run("get-limits")


async def set_limits(burst: int, rate_per_min: int) -> dict:
    return await _run("set-limits", str(burst), str(rate_per_min))


async def set_whitelist(emails: list[str]) -> dict:
    return await _run("set-whitelist", ",".join(emails))


async def set_dlp_exempt(emails: list[str]) -> dict:
    """Remitentes de sistema exentos de la Protección de datos (DLP) hacia externos."""
    return await _run("set-dlp-exempt", ",".join(emails))


async def activity(hours: int = 1) -> dict:
    return await _run("activity", str(hours))


async def lock(email: str) -> dict:
    return await _run("lock", email)


async def unlock(email: str) -> dict:
    return await _run("unlock", email)


async def status(email: str) -> dict:
    return await _run("status", email)
