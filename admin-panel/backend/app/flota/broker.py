"""Cliente del registro de claves del servidor de túneles («broker») — Fase B del túnel de soporte.

APAGADO por defecto (`FLOTA_TUNEL_BROKER=true` lo activa). Habla por SSH con un usuario de gestión que
tiene una orden forzada: no da intérprete de órdenes, solo acepta estas cuatro acciones y responde texto:

    puerto-libre                      → el menor puerto libre
    listar                            → una línea «puerto<TAB>etiqueta» por clave instalada
    alta <etiqueta> <puerto> <clave pública>
    baja <etiqueta>

Ajustes (entorno del panel; aquí no hay valores de ningún servidor real):

    FLOTA_BROKER_HOST       dirección del servidor de túneles vista desde el panel
    FLOTA_BROKER_PUERTO     puerto SSH de gestión (por defecto 22)
    FLOTA_BROKER_USUARIO    usuario de gestión (por defecto «flota-gestor»)
    FLOTA_BROKER_CLAVE      ruta de la clave privada de gestión (legible solo por el usuario del panel)
    FLOTA_BROKER_HOST_KEY   clave pública de host del servidor («ssh-ed25519 AAAA…»): se FIJA, no se aprende
    FLOTA_BROKER_TIEMPO_S   tiempo máximo de cada llamada, en segundos (por defecto 10)

Cada llamada fija la clave de host en un fichero temporal propio y tiene tiempo máximo. El ejecutor es
sustituible para probar el módulo sin red.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from collections.abc import Awaitable, Callable

from app.flota.tunel_ajustes import PUERTO_MAX, PUERTO_MIN

Ejecutor = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]

_ETIQUETA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
_PUBLICA = re.compile(r"^ssh-ed25519 [A-Za-z0-9+/]{60,100}={0,2}$")
_HOST_KEY = re.compile(
    r"^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/]+={0,2}$"
)
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class ErrorBroker(RuntimeError):
    """El servidor de túneles no está configurado, no responde o rechazó la acción."""


def etiqueta_de(nombre: str, equipo_id: str) -> str:
    """Etiqueta única y sin caracteres raros para un equipo: su nombre y el inicio de su identificador."""
    limpio = re.sub(r"[^A-Za-z0-9._-]", "-", nombre or "").strip("-.")[:50] or "equipo"
    return f"{limpio}-{equipo_id[:8]}"


async def ejecutar_ssh(orden: list[str], tiempo_s: float) -> tuple[int, str, str]:
    """Ejecutor real: lanza `ssh` sin intérprete de órdenes intermedio y lo mata si se pasa de tiempo."""
    proceso = await asyncio.create_subprocess_exec(
        *orden,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        salida, error = await asyncio.wait_for(proceso.communicate(), timeout=tiempo_s)
    except asyncio.TimeoutError:
        proceso.kill()
        await proceso.wait()
        raise
    return (
        proceso.returncode or 0,
        salida.decode(errors="replace"),
        error.decode(errors="replace"),
    )


class Broker:
    def __init__(
        self,
        *,
        host: str,
        clave: str,
        host_key: str,
        puerto: int = 22,
        usuario: str = "flota-gestor",
        tiempo_s: float = 10.0,
        ejecutor: Ejecutor = ejecutar_ssh,
    ):
        if not host or not clave or not host_key:
            raise ErrorBroker(
                "Falta configurar el servidor de túneles (FLOTA_BROKER_HOST, FLOTA_BROKER_CLAVE y FLOTA_BROKER_HOST_KEY)."
            )
        if not _HOST.match(host) or not _HOST_KEY.match(host_key.strip()):
            raise ErrorBroker(
                "La dirección o la clave de host del servidor de túneles no tienen un formato válido."
            )
        self.host, self.puerto, self.usuario = host, int(puerto), usuario
        self.clave, self.host_key = clave, host_key.strip()
        self.tiempo_s, self.ejecutor = float(tiempo_s), ejecutor

    @classmethod
    def desde_entorno(cls, ejecutor: Ejecutor = ejecutar_ssh) -> "Broker":
        try:
            puerto = int(os.getenv("FLOTA_BROKER_PUERTO") or 22)
            tiempo_s = float(os.getenv("FLOTA_BROKER_TIEMPO_S") or 10)
        except ValueError:
            raise ErrorBroker(
                "FLOTA_BROKER_PUERTO y FLOTA_BROKER_TIEMPO_S deben ser números."
            ) from None
        return cls(
            host=(os.getenv("FLOTA_BROKER_HOST") or "").strip(),
            clave=(os.getenv("FLOTA_BROKER_CLAVE") or "").strip(),
            host_key=os.getenv("FLOTA_BROKER_HOST_KEY") or "",
            puerto=puerto,
            usuario=(os.getenv("FLOTA_BROKER_USUARIO") or "flota-gestor").strip(),
            tiempo_s=tiempo_s,
            ejecutor=ejecutor,
        )

    def _orden(self, conocidos: str, accion: str) -> list[str]:
        return [
            "ssh",
            "-T",
            "-p",
            str(self.puerto),
            "-i",
            self.clave,
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={conocidos}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            f"ConnectTimeout={max(1, int(self.tiempo_s))}",
            f"{self.usuario}@{self.host}",
            accion,
        ]

    async def _llamar(self, accion: str) -> str:
        destino = self.host if self.puerto == 22 else f"[{self.host}]:{self.puerto}"
        with tempfile.TemporaryDirectory(prefix="flota-broker-") as carpeta:
            conocidos = os.path.join(carpeta, "known_hosts")
            with open(conocidos, "w", encoding="ascii") as f:
                f.write(f"{destino} {self.host_key}\n")
            try:
                codigo, salida, error = await self.ejecutor(
                    self._orden(conocidos, accion), self.tiempo_s
                )
            except asyncio.TimeoutError:
                raise ErrorBroker(
                    f"El servidor de túneles no respondió en {self.tiempo_s:g} s."
                ) from None
            except OSError as e:
                raise ErrorBroker(
                    f"No se pudo ejecutar ssh: {e.strerror or e}"
                ) from None
        if codigo != 0:
            detalle = (error or salida).strip().splitlines()[-1:] or ["sin detalle"]
            raise ErrorBroker(
                f"El servidor de túneles rechazó «{accion.split()[0]}»: {detalle[0][:200]}"
            )
        return salida

    @staticmethod
    def _puerto(valor) -> int:
        try:
            puerto = int(str(valor).strip())
        except ValueError:
            raise ErrorBroker(
                "El servidor de túneles devolvió un puerto que no es un número."
            ) from None
        if not PUERTO_MIN <= puerto <= PUERTO_MAX:
            raise ErrorBroker(
                f"Puerto fuera del rango {PUERTO_MIN}-{PUERTO_MAX}: {puerto}"
            )
        return puerto

    @staticmethod
    def _etiqueta(etiqueta: str) -> str:
        if not _ETIQUETA.match(etiqueta or ""):
            raise ErrorBroker(
                "Etiqueta de equipo no válida para el servidor de túneles."
            )
        return etiqueta

    async def puerto_libre(self) -> int:
        return self._puerto(await self._llamar("puerto-libre"))

    async def listar(self) -> dict[int, str]:
        """puerto → etiqueta de cada clave instalada."""
        instaladas: dict[int, str] = {}
        for linea in (await self._llamar("listar")).splitlines():
            if not linea.strip():
                continue
            puerto, _, etiqueta = linea.partition("\t")
            instaladas[self._puerto(puerto)] = etiqueta.strip()
        return instaladas

    async def alta(self, etiqueta: str, puerto: int, publica: str) -> None:
        publica = " ".join((publica or "").split()[:2])
        if not _PUBLICA.match(publica):
            raise ErrorBroker(
                "La clave pública del equipo no es ed25519 en formato OpenSSH."
            )
        await self._llamar(
            f"alta {self._etiqueta(etiqueta)} {self._puerto(puerto)} {publica}"
        )

    async def baja(self, etiqueta: str) -> None:
        await self._llamar(f"baja {self._etiqueta(etiqueta)}")
