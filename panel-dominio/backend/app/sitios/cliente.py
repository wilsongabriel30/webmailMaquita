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
           "php-version": 300, "revisar": 200, "php-estado": 200, "clave-admin": 150, "tareas-guardar": 120,
           # v1.10: copias, estadísticas y archivos grandes (copiar, comprimir, subir, descargar).
           **dict.fromkeys(("copia-crear", "copia-restaurar", "copia-descargar", "estadisticas-generar",
                            "archivos-subir", "archivos-descargar", "archivos-copiar", "archivos-comprimir",
                            "archivos-descomprimir", "archivos-borrar", "archivos-vaciar"), 1190),
           **dict.fromkeys(("web-redirecciones", "web-errores", "web-hotlink", "web-bloqueo", "web-optimizacion",
                            "web-privado-agregar", "web-privado-quitar", "web-purgar", "ftp-cuenta-crear",
                            "ftp-cuenta-clave", "ftp-cuenta-quitar", "web"), 130),
           # v1.11: bases, cortafuegos de aplicaciones y claves SSH (el intermediario espera 120 s a maquita-sitios).
           **dict.fromkeys(("bases-usuarios", "base-usuario-crear", "base-usuario-permisos", "base-usuario-clave",
                            "base-usuario-borrar", "base-usuario-remoto", "waf", "waf-guardar", "waf-bloqueos",
                            "ssh-claves", "ssh-clave-agregar", "ssh-clave-borrar"), 130),
           # v1.11: alias (certificado), aplicaciones propias (pip, npm), git y DNS dinámico.
           "alias": 610, "propia-crear": 1160, "propia-accion": 1160, "propia-entorno": 310, "propia-quitar": 310,
           "git-configurar": 130, "git-volver": 1195, "git-quitar": 310, "servidor-info": 190, "gancho-git": 70,
           **dict.fromkeys(("ddns-crear", "ddns-actualizar"), 130)}
ORDENES = {
    "listar", "catalogo", "crear", "app", "entrar", "clave-admin", "revisar", "actualizar", "terminar",
    "ssl", "ftp", "tareas", "tareas-guardar", "tarea-ejecutar", "tarea-registro",
    "bases", "base-crear", "base-entrar", "base-borrar",
    "avanzado", "avanzado-php", "avanzado-ver", "avanzado-archivo", "avanzado-restaurar", "php-estado", "php-version",
    "paquete", "dns-ver", "dns-agregar", "dns-modificar", "dns-borrar",
    # v1.10: funciones web y cuentas FTP adicionales.
    "web", "web-redirecciones", "web-errores", "web-hotlink", "web-bloqueo", "web-optimizacion", "web-purgar",
    "web-privado-agregar", "web-privado-quitar", "ftp-cuentas", "ftp-cuenta-crear", "ftp-cuenta-clave", "ftp-cuenta-quitar",
    # v1.10: registros, estadísticas, disponibilidad, copias del sitio y administrador de archivos.
    "registros", "estadisticas", "estadisticas-generar", "estadisticas-informe", "disponibilidad",
    "copias", "copia-crear", "copia-descargar", "copia-restaurar", "copia-borrar",
    "archivos-listar", "archivos-subir", "archivos-descargar", "archivos-carpeta", "archivos-mover", "archivos-copiar",
    "archivos-descomprimir", "archivos-borrar", "archivos-comprimir", "archivos-permisos", "archivos-papelera",
    "archivos-recuperar", "archivos-vaciar",
    # v1.11: usuarios de bases con permisos y acceso remoto, cortafuegos de aplicaciones y claves SSH.
    "bases-usuarios", "base-usuario-crear", "base-usuario-permisos", "base-usuario-clave", "base-usuario-borrar",
    "base-usuario-remoto", "waf", "waf-guardar", "waf-bloqueos", "ssh-claves", "ssh-clave-agregar", "ssh-clave-borrar",
    # v1.11: alias, aplicaciones Node.js y Python, git de los sitios PHP, CPU y memoria, información del servidor
    # y DNS dinámico; «gancho-git» y «ddns-actualizar» van sin sesión (app/publico.py).
    "alias", "propia-crear", "propia-estado", "propia-accion", "propia-entorno", "propia-quitar",
    "git-estado", "git-configurar", "git-clave", "git-gancho", "git-desplegar", "git-volver", "git-quitar",
    "recursos", "servidor-info", "ddns-ver", "ddns-crear", "ddns-clave", "ddns-borrar", "gancho-git", "ddns-actualizar",
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
