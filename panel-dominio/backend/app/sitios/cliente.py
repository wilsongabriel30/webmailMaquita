"""Cliente del intermediario root de los sitios (maquita-sitios-portal), por su socket Unix.

Protocolo: una línea JSON de ida y una de vuelta.
  ida:    {"ficha", "orden", "dominio", "args"}
  vuelta: {"ok": true, "datos": …} | {"ok": false, "codigo": 4xx|503, "error": "texto para la persona"}

El intermediario no se fía del portal: con la ficha vuelve a comprobar la sesión y el alcance en
la base. Por eso se le pasa la ficha de la petición tal cual, y no un nombre de usuario.
"""

import asyncio
import contextlib
import json

from fastapi import HTTPException

from app.sitios import config

NO_INSTALADO = "Los sitios web no están instalados en este servidor"
SIN_RESPUESTA = "El servicio de sitios web no responde. Inténtalo en unos minutos o avisa al administrador general."
MAX_PETICION = 64 * 1024
MAX_RESPUESTA = 8 * 1024 * 1024

# Segundos que se espera cada orden. Las largas descargan, verifican o instalan; el intermediario
# corta a los 1200 s (RuntimeMaxSec), así que nada espera más.
_LARGAS = {"app": 1190, "paquete": 1190, "actualizar": 900, "base-borrar": 600, "ssl": 400,
           "php-version": 300, "revisar": 200, "php-estado": 200, "clave-admin": 150, "tareas-guardar": 120}
ORDENES = {
    "listar", "catalogo", "crear", "app", "entrar", "clave-admin", "revisar", "actualizar", "terminar",
    "ssl", "ftp", "tareas", "tareas-guardar", "tarea-ejecutar", "tarea-registro",
    "bases", "base-crear", "base-entrar", "base-borrar",
    "avanzado", "avanzado-php", "avanzado-ver", "avanzado-archivo", "avanzado-restaurar", "php-estado", "php-version",
    "paquete", "dns-ver", "dns-agregar", "dns-modificar", "dns-borrar",
}


def tiempo_de(orden: str) -> int:
    return _LARGAS.get(orden, 60)


async def pedir(ficha: str, orden: str, dominio: str | None = None, args: dict | None = None):
    if orden not in ORDENES:
        raise ValueError(f"orden desconocida: {orden}")
    peticion = {"ficha": ficha, "orden": orden, "args": args or {}}
    if dominio is not None:
        peticion["dominio"] = dominio
    linea = json.dumps(peticion, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
    if len(linea) > MAX_PETICION:
        raise HTTPException(413, "Lo enviado es demasiado grande")
    try:
        lector, escritor = await asyncio.wait_for(
            asyncio.open_unix_connection(config.SOCKET, limit=MAX_RESPUESTA), timeout=10)
    except (FileNotFoundError, ConnectionRefusedError):
        raise HTTPException(503, NO_INSTALADO)
    except (OSError, asyncio.TimeoutError):
        raise HTTPException(503, SIN_RESPUESTA)
    try:
        escritor.write(linea)
        await escritor.drain()
        crudo = await asyncio.wait_for(lector.readline(), timeout=tiempo_de(orden))
    except asyncio.TimeoutError:
        raise HTTPException(504, "La operación tardó demasiado. Revisa el estado del sitio en unos minutos.")
    except (ValueError, asyncio.LimitOverrunError):
        raise HTTPException(502, "La respuesta del servicio de sitios web es demasiado grande")
    except OSError:
        raise HTTPException(503, SIN_RESPUESTA)
    finally:
        escritor.close()
        with contextlib.suppress(Exception):
            await escritor.wait_closed()
    return interpretar(crudo)


def interpretar(crudo: bytes):
    """Respuesta del intermediario ⇒ datos, o HTTPException con su código y su texto."""
    if not crudo.strip():
        raise HTTPException(503, SIN_RESPUESTA)
    try:
        respuesta = json.loads(crudo)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(502, "Respuesta no válida del servicio de sitios web")
    if not isinstance(respuesta, dict):
        raise HTTPException(502, "Respuesta no válida del servicio de sitios web")
    if respuesta.get("ok") is True:
        return respuesta.get("datos")
    try:
        codigo = int(respuesta.get("codigo") or 400)
    except (TypeError, ValueError):
        codigo = 400
    if not 400 <= codigo <= 599 or codigo in (401, 500):
        # 401 cerraría la sesión del portal en el navegador: el intermediario no decide eso.
        codigo = 403 if codigo == 401 else 502
    texto = str(respuesta.get("error") or "No se pudo completar la operación")[:500]
    raise HTTPException(codigo, texto)
