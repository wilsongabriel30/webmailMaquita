"""Panel de UrBackup (VM 113) con un usuario PROPIO, no `admin`.

Credenciales SOLO en el servidor: `/etc/maquita-mail/urbackup-api.env` (root:www-data, 640), con
    URBACKUP_API_USUARIO=...
    URBACKUP_API_CLAVE=...
    URBACKUP_API_URL=https://<servidor de respaldos>     (opcional; por defecto ORG_SERVIDOR_RESPALDOS)
Se lee en cada uso: al crear el archivo no hace falta reiniciar el backend. Sin archivo o sin
credenciales válidas todo responde «no disponible» (503 para la app). La clave del panel nunca se
registra ni sale del servidor; la clave de cada cliente solo se devuelve en el canje.

Permisos mínimos del usuario del panel: ver el estado de los clientes («status»), leer los ajustes
de cliente («settings», para su clave de internet) y añadir clientes de internet («add_client»).

Inicio de sesión: el mismo cálculo que hace el panel (md5(salt+clave), PBKDF2-SHA256 si el servidor
pide rondas, y md5(rnd+...)), comprobado en el JS del panel 2.5.32 el 20/10/2026.
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from app import organizacion

logger = logging.getLogger(__name__)
ARCHIVO = "/etc/maquita-mail/urbackup-api.env"


def servidor() -> str:
    """Nombre público del servidor de respaldos (organizacion.env). Es el que se da a los equipos."""
    return organizacion.valor("ORG_SERVIDOR_RESPALDOS", "respaldos.example.org")


def puerto() -> int:
    return int(organizacion.valor("ORG_PUERTO_RESPALDOS", "55415"))


class NoDisponible(Exception):
    """El panel no responde, no hay credenciales o las rechaza."""


class NombreOcupado(Exception):
    """Ya existe un cliente con ese nombre: NUNCA se entrega su clave a otra persona."""


def _config() -> dict:
    datos = {}
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    datos[k.strip()] = v.strip().strip("\"'")
    except OSError:
        pass
    return datos


def configurado() -> bool:
    c = _config()
    return bool(c.get("URBACKUP_API_USUARIO") and c.get("URBACKUP_API_CLAVE"))


def _valor(v):
    """Igual que getVal() del panel: un ajuste puede venir plano o con su origen (grupo/cliente)."""
    if not isinstance(v, dict):
        return v
    uso = v.get("use")
    if uso is None:
        return v.get("value", "")
    if uso == 1:
        return v.get("value_group")
    if uso == 4:
        return v.get("value_client")
    return v.get("value")


class Panel:
    def __init__(self):
        c = _config()
        self.usuario = c.get("URBACKUP_API_USUARIO", "")
        self._clave = c.get("URBACKUP_API_CLAVE", "")
        self.url = c.get("URBACKUP_API_URL", f"https://{servidor()}").rstrip("/")
        self.ses = ""

    async def __aenter__(self):
        if not self.usuario or not self._clave:
            raise NoDisponible("sin credenciales del panel")
        self.http = httpx.AsyncClient(timeout=15)
        try:
            await self._entrar()
        except Exception:
            await self.http.aclose()
            raise
        return self

    async def __aexit__(self, *exc):
        await self.http.aclose()

    async def _llamar(self, accion: str, **datos) -> dict:
        if self.ses:
            datos["ses"] = self.ses
        try:
            r = await self.http.post(f"{self.url}/x", params={"a": accion}, data=datos)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            # Solo el tipo de error: la petición lleva la sesión del panel.
            raise NoDisponible(f"{accion}: {type(e).__name__}") from None

    async def _entrar(self) -> None:
        s = await self._llamar("salt", username=self.usuario)
        if not s.get("salt"):
            raise NoDisponible("el panel no dio salt (¿usuario inexistente?)")
        self.ses = s.get("ses", "")
        h = hashlib.md5((s["salt"] + self._clave).encode()).hexdigest()
        rondas = int(s.get("pbkdf2_rounds") or 0)
        if rondas > 0:
            h = hashlib.pbkdf2_hmac(
                "sha256", bytes.fromhex(h), s["salt"].encode(), rondas
            ).hex()
        h = hashlib.md5((s.get("rnd", "") + h).encode()).hexdigest()
        r = await self._llamar("login", username=self.usuario, password=h)
        if not r.get("success"):
            raise NoDisponible("el panel rechazó al usuario de la API")
        self.ses = r.get("session") or self.ses

    async def clientes(self) -> dict[str, int]:
        """Nombre en minúsculas → id de todos los clientes que el usuario puede ver."""
        st = await self._llamar("status")
        return {
            str(c.get("name", "")).lower(): int(c["id"])
            for c in st.get("status", [])
            if c.get("id") is not None
        }

    async def clave_de(self, clientid: int) -> str:
        r = await self._llamar(
            "settings", sa="clientsettings", t_clientid=str(clientid)
        )
        clave = _valor((r.get("settings") or {}).get("internet_authkey", ""))
        if not clave:
            raise NoDisponible(f"sin clave de internet para el cliente {clientid}")
        return str(clave)

    async def crear(self, nombre: str) -> tuple[int, str]:
        r = await self._llamar("add_client", clientname=nombre)
        if r.get("already_exists"):
            raise NombreOcupado(nombre)
        if not r.get("added_new_client") or not r.get("new_authkey"):
            raise NoDisponible("add_client no creó el cliente (¿permiso add_client?)")
        logger.info(
            "respaldos_cliente_creado | cliente=%s | id=%s",
            nombre,
            r.get("new_clientid"),
        )
        return int(r["new_clientid"]), str(r["new_authkey"])
