# -*- coding: utf-8 -*-
"""Validadores de maquita-sudo para maquita-sitios: cada subacción con la forma exacta de sus argumentos (el ayudante
revalida). Sitios, PHP, bases, aplicaciones propias, funciones web, FTP, datos, desarrollo y git (v1.11).
"""
import os
import re

from sudo_base import _RE_B64URL, _RE_B64URL_LARGO, _RE_B64URL_MUY_LARGO, _RE_DOMINIO_SITIO, Rechazo, es_buzon


def validar_sitios(args):
    """maquita-sitios: cada subacción con la forma exacta de sus argumentos (el ayudante revalida)."""
    dom = lambda d: bool(_RE_DOMINIO_SITIO.fullmatch(d))  # noqa: E731
    if args in (["estado"], ["listar"], ["catalogo"]):
        return args
    if (args[:1] == ["crear"] and 2 <= len(args) <= 4 and dom(args[1])
            and (len(args) == 2 or args[2] in ("con-www", "sin-www"))
            and (len(args) < 4 or _RE_B64URL.fullmatch(args[3]))):
        return args
    if (len(args) == 5 and args[0] == "app" and dom(args[1]) and re.fullmatch(r"[a-z0-9-]{2,30}", args[2])
            and _RE_B64URL.fullmatch(args[3]) and es_buzon(args[4])):
        return args
    if len(args) == 3 and args[0] == "ftp" and dom(args[1]) and args[2] in ("activar", "desactivar"):
        return args
    if len(args) == 3 and args[0] == "ssl" and dom(args[1]) and es_buzon(args[2]):
        return args
    if len(args) == 3 and args[0] == "alias" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if (len(args) in (4, 5) and args[0] == "paquete" and dom(args[1]) and re.fullmatch(r"[0-9a-f]{32}\.(zip|tar\.gz|tgz)", args[2])
            and args[3] in ("con-bd", "sin-bd") and (len(args) == 4 or re.fullmatch(r"[0-9a-f]{32}\.(sql|sql\.gz)", args[4]))):
        return args
    texto = lambda a: bool(re.fullmatch(r"[0-9a-f]{32}\.txt", a))  # noqa: E731  contenido dejado en subidas/
    if len(args) == 2 and args[0] == "avanzado" and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "avanzado-nginx" and dom(args[1]) and texto(args[2]):
        return args
    if len(args) == 3 and args[0] == "avanzado-php" and dom(args[1]) and _RE_B64URL.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "avanzado-ver" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if len(args) == 4 and args[0] == "avanzado-archivo" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]) and texto(args[3]):
        return args
    if len(args) == 3 and args[0] == "avanzado-restaurar" and dom(args[1]) and re.fullmatch(r"\d{8}-\d{6}-\d{3}", args[2]):
        return args
    version_php = lambda a: bool(re.fullmatch(r"[578]\.[0-9]", a))  # noqa: E731
    if args[:1] == ["php-estado"] and (len(args) == 1 or (len(args) == 2 and dom(args[1]))):
        return args
    if args == ["php-repositorio"]:
        return args
    if len(args) == 2 and args[0] in ("php-instalar", "php-extensiones") and version_php(args[1]):
        return args
    if (len(args) == 4 and args[0] == "php-extension" and version_php(args[1]) and re.fullmatch(r"[a-z0-9]{2,20}", args[2])
            and args[3] in ("instalar", "quitar")):
        return args
    if len(args) == 3 and args[0] == "php-version" and dom(args[1]) and version_php(args[2]):
        return args
    if len(args) == 2 and args[0] == "tareas" and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "tareas-guardar" and dom(args[1]) and _RE_B64URL_MUY_LARGO.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] in ("tarea-ejecutar", "tarea-registro") and dom(args[1]) and re.fullmatch(r"[0-9a-f]{8}", args[2]):
        return args
    if len(args) == 3 and args[0] == "borrar" and dom(args[1]) and args[1] == args[2]:
        return args
    if len(args) == 2 and args[0] in ("entrar", "clave-admin", "revisar", "actualizar", "buscadores", "avisar", "terminar") and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "inicio" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if len(args) == 2 and args[0] in ("tienda", "bases") and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "base-crear" and dom(args[1]) and args[2] in ("mariadb", "postgresql"):
        return args
    if (len(args) == 4 and args[0] == "base-entrar" and dom(args[1]) and re.fullmatch(r"[wx]_[a-z0-9]+(_[0-9a-f]{4})?", args[2])
            and args[3] in ("phpmyadmin", "adminer")):
        return args
    if len(args) == 3 and args[0] == "base-borrar" and dom(args[1]) and re.fullmatch(r"x_[a-z0-9]+_[0-9a-f]{4}", args[2]):
        return args
    # Aplicaciones propias: la configuración y las variables viajan en base64url (el ayudante las valida).
    if len(args) == 4 and args[0] == "propia-crear" and dom(args[1]) and args[2] in ("estatico", "python", "node") \
            and _RE_B64URL_LARGO.fullmatch(args[3]):
        return args
    if len(args) == 2 and args[0] == "propia-estado" and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "propia-accion" and dom(args[1]) and args[2] in ("iniciar", "detener", "reiniciar", "desplegar"):
        return args
    if len(args) == 3 and args[0] == "propia-entorno" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "propia-quitar" and dom(args[1]) and args[1] == args[2]:
        return args
    if args[:1] and args[0] in _ORDENES_SITIOS_WEB:
        return validar_sitios_web(args)
    if args[:1] and args[0] in _ORDENES_SITIOS_V111:
        return validar_sitios_v111(args)
    if _validar_sitios_datos(args, dom) or _validar_sitios_desarrollo(args, dom):
        return args
    raise Rechazo("maquita-sitios: subacción o argumentos no permitidos")


# Para desarrolladores (v1.11): usuarios de bases, acceso remoto, cortafuegos de aplicaciones y claves SSH
# (deploy/sitios/lib/ordenes_desarrollo.py). Permisos, redes, ajustes y claves viajan en base64url (≤ 8000).
_ORDENES_DESARROLLO_LARGAS = ("base-usuario-crear", "base-usuario-permisos", "base-usuario-remoto", "waf-guardar",
                              "ssh-clave-agregar")
_RE_USUARIO_BD = re.compile(r"^u_[a-z0-9]+_[a-z][a-z0-9]{1,9}$")


def _validar_sitios_desarrollo(args, dom):
    b64 = lambda a: bool(_RE_B64URL_LARGO.fullmatch(a))  # noqa: E731
    if len(args) < 2 or not dom(args[1]):
        return False
    orden, n = args[0], len(args)
    if orden in ("bases-usuarios", "waf", "ssh-claves"):
        return n == 2
    if orden == "base-usuario-crear":
        return (n == 5 and bool(re.fullmatch(r"[wx]_[a-z0-9]+(_[0-9a-f]{4})?", args[2]))
                and bool(re.fullmatch(r"[a-z][a-z0-9]{1,9}", args[3])) and b64(args[4]))
    if orden in ("base-usuario-clave", "base-usuario-borrar"):
        return n == 3 and bool(_RE_USUARIO_BD.fullmatch(args[2]))
    if orden == "base-usuario-permisos":
        return n == 4 and bool(_RE_USUARIO_BD.fullmatch(args[2])) and b64(args[3])
    if orden == "base-usuario-remoto":
        return n in (4, 5) and bool(_RE_USUARIO_BD.fullmatch(args[2])) and b64(args[3]) and (n == 4 or args[4] == "amplia")
    if orden == "waf-guardar":
        return n == 3 and b64(args[2])
    if orden == "waf-bloqueos":
        return n == 2 or (n == 3 and bool(re.fullmatch(r"[1-9][0-9]{0,2}", args[2])))
    if orden == "ssh-clave-agregar":
        return n == 4 and bool(re.fullmatch(r"principal|[a-z][a-z0-9]{1,10}", args[2])) and b64(args[3])
    if orden == "ssh-clave-borrar":
        return n == 3 and bool(re.fullmatch(r"[0-9a-f]{8}", args[2]))
    return False


# Observación y datos de los sitios: registros, estadísticas, disponibilidad, copias del cliente y archivos.
# Las rutas viajan en base64url (el ayudante las decodifica, las resuelve dentro del sitio y opera como su usuario).
_ORDENES_DATOS_SOLO_DOMINIO = ("estadisticas", "estadisticas-generar", "estadisticas-informe", "disponibilidad",
                               "copias", "copia-crear", "archivos-papelera", "archivos-vaciar")
_RE_COPIA_SITIO = re.compile(r"^\d{8}-\d{6}$")
_MODOS_ARCHIVO = ("644", "755", "600", "700", "640", "750")


def _validar_sitios_datos(args, dom):
    ruta = lambda a: bool(_RE_B64URL_LARGO.fullmatch(a))  # noqa: E731
    if len(args) < 2 or not dom(args[1]):
        return False
    orden, n = args[0], len(args)
    if orden in _ORDENES_DATOS_SOLO_DOMINIO:
        return n == 2
    if orden == "registros":
        return (n in (4, 5) and args[2] in ("error", "acceso", "php") and re.fullmatch(r"[1-9][0-9]{0,3}", args[3])
                and int(args[3]) <= 1000 and (n == 4 or bool(_RE_B64URL.fullmatch(args[4]))))
    if orden in ("copia-descargar", "copia-restaurar", "copia-borrar"):
        return n == 3 and bool(_RE_COPIA_SITIO.fullmatch(args[2]))
    if orden in ("archivos-listar", "archivos-descargar", "archivos-carpeta", "archivos-borrar"):
        return n == 3 and ruta(args[2])
    if orden == "archivos-subir":
        return (n in (4, 5) and ruta(args[2]) and bool(re.fullmatch(r"[0-9a-f]{32}\.subida", args[3]))
                and (n == 4 or args[4] == "reemplazar"))
    if orden in ("archivos-mover", "archivos-copiar", "archivos-descomprimir"):
        return n == 4 and ruta(args[2]) and ruta(args[3])
    if orden == "archivos-comprimir":
        return n == 3 and bool(_RE_B64URL_MUY_LARGO.fullmatch(args[2]))
    if orden == "archivos-permisos":
        return n == 4 and ruta(args[2]) and args[3] in _MODOS_ARCHIVO
    if orden == "archivos-recuperar":
        return n == 3 and bool(re.fullmatch(r"[0-9a-f]{12}", args[2]))
    return False


# --- maquita-sitios: funciones web por sitio y cuentas FTP adicionales (v1.10) ---
# Bloque aparte de validar_sitios para que otras secciones se fusionen sin tocarlo. Los datos libres (listas,
# carpetas, contraseñas) viajan en base64url y el ayudante los vuelve a validar uno a uno.
_ORDENES_SITIOS_WEB_JSON = ("web-redirecciones", "web-errores", "web-hotlink", "web-bloqueo", "web-optimizacion")
_ORDENES_SITIOS_WEB = {"web", "web-purgar", "web-privado-agregar", "web-privado-quitar", "ftp-cuentas",
                       "ftp-cuenta-crear", "ftp-cuenta-clave", "ftp-cuenta-quitar", *_ORDENES_SITIOS_WEB_JSON}
_RE_B64URL_LISTA = re.compile(r"^[A-Za-z0-9_-]{1,20000}$")  # hasta 200 redirecciones o 500 IP
_RE_USUARIO_CARPETA = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_RE_CUENTA_FTP = re.compile(r"^[a-z][a-z0-9]{1,10}$")


def validar_sitios_web(args):
    """maquita-sitios web…/ftp-…: forma exacta de cada argumento (ver deploy/sitios/lib/funciones_web.py)."""
    dom = lambda d: bool(_RE_DOMINIO_SITIO.fullmatch(d))  # noqa: E731
    b64 = lambda a: bool(_RE_B64URL.fullmatch(a))  # noqa: E731  carpeta, subcarpeta o contraseña (≤ 200)
    if len(args) == 2 and args[0] in ("web", "web-purgar", "ftp-cuentas") and dom(args[1]):
        return args
    if len(args) == 3 and args[0] in ("web-redirecciones", "web-bloqueo") and dom(args[1]) and _RE_B64URL_LISTA.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] in ("web-errores", "web-hotlink", "web-optimizacion") and dom(args[1]) \
            and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if (len(args) in (4, 5) and args[0] == "web-privado-agregar" and dom(args[1]) and b64(args[2])
            and _RE_USUARIO_CARPETA.fullmatch(args[3]) and (len(args) == 4 or b64(args[4]))):
        return args
    if (len(args) in (3, 4) and args[0] == "web-privado-quitar" and dom(args[1]) and b64(args[2])
            and (len(args) == 3 or _RE_USUARIO_CARPETA.fullmatch(args[3]))):
        return args
    if len(args) == 4 and args[0] == "ftp-cuenta-crear" and dom(args[1]) and _RE_CUENTA_FTP.fullmatch(args[2]) and b64(args[3]):
        return args
    if len(args) == 3 and args[0] in ("ftp-cuenta-clave", "ftp-cuenta-quitar") and dom(args[1]) and _RE_CUENTA_FTP.fullmatch(args[2]):
        return args
    raise Rechazo("maquita-sitios: subacción o argumentos no permitidos")


# --- maquita-sitios: despliegue desde git de los sitios PHP y CPU y memoria por sitio (v1.11) ---
# Ver deploy/sitios/lib/ordenes_v111.py. «git-desplegar-ahora» y «recursos-recoger» son del sistema: no pasan.
_ORDENES_SITIOS_V111 = {"git-estado", "git-configurar", "git-clave", "git-gancho", "git-desplegar", "git-volver",
                        "git-quitar", "recursos", "git-credencial", "git-credencial-guardar", "git-credencial-borrar"}


def _validador(nombre):  # módulo aparte de maquita-sitios (deploy/sitios/lib/sudo_*.py), cargado por su ruta
    import importlib.util
    for ruta in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sitios", "lib", nombre + ".py"),
                 f"/usr/local/lib/maquita-sitios/{nombre}.py"):
        if os.path.isfile(ruta):
            spec = importlib.util.spec_from_file_location("maquita_sudo_" + nombre, ruta)
            return spec.loader.exec_module(modulo := importlib.util.module_from_spec(spec)) or modulo
    raise Rechazo(f"maquita-sitios: falta el validador {nombre}")


def validar_sitios_v111(args):
    dom = lambda d: bool(_RE_DOMINIO_SITIO.fullmatch(d))  # noqa: E731
    if args[0].startswith("git-credencial") and _validador("sudo_git_credencial").valida(args):  # autenticación de git
        return args
    if len(args) == 2 and args[0] in ("git-estado", "git-clave", "recursos") and dom(args[1]):
        return args
    if len(args) == 3 and args[0] == "git-configurar" and dom(args[1]) and _RE_B64URL_LARGO.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "git-gancho" and dom(args[1]) and args[2] in ("activar", "desactivar"):
        return args
    if len(args) == 3 and args[0] == "git-desplegar" and dom(args[1]) and args[2] in ("panel", "gancho"):
        return args
    if len(args) == 3 and args[0] == "git-volver" and dom(args[1]) and re.fullmatch(r"\d{8}-\d{6}", args[2]):
        return args
    if len(args) == 3 and args[0] == "git-quitar" and dom(args[1]) and args[1] == args[2]:
        return args
    raise Rechazo("maquita-sitios: subacción o argumentos no permitidos")
