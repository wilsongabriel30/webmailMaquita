"""Aplicaciones propias de un sitio: estáticas (HTML/CSS/JS), Python (WSGI o ASGI) y Node.js.

- El código va en /srv/sitios/<dominio>/app/: se sube por SFTP o se clona de un repositorio git
  («Desplegar» trae los cambios), público por HTTPS o privado con la autenticación del sitio
  (git_clave.py: clave de despliegue de solo lectura, clave propia, token o usuario y contraseña;
  se configura antes de crear la aplicación con las órdenes git-credencial…). Una estática sin
  repositorio se sirve desde «publico», como cualquier sitio, pero sin PHP.
- Python y Node.js corren como servicio de systemd con el usuario del sitio, encerrados (ver
  propias_servicio.py), escuchando solo en 127.0.0.1:$PORT; nginx les pasa las peticiones con el
  cortafuegos de aplicación delante. Sin código propio todavía, se deja una aplicación de ejemplo.
- Variables de entorno desde el panel (solo root las lee; systemd se las da al proceso).
- Puerto público opcional para servicios que no son web: la aplicación lo recibe en PUERTO_PUBLICO y
  el cortafuegos del servidor lo abre mientras la aplicación exista.
"""

import os
import re
import shutil
import time

import git_clave as gc
import propias_servicio as srv
from comun import PAPELERA, ErrorSitio, ejecutar, guardar_meta, leer_meta

TIPOS = ("estatico", "python", "node")
RE_RAMA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
RE_CARPETA = re.compile(r"^[A-Za-z0-9._-]{1,60}(?:/[A-Za-z0-9._-]{1,60}){0,5}$")
RE_ENTRADA_PY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,99}:[A-Za-z_][A-Za-z0-9_]{0,59}$")
RE_ENTRADA_JS = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/-]{0,119}\.(?:js|mjs|cjs)$")

EJEMPLO_WSGI = '''"""Aplicación de ejemplo: reemplácela por la suya (por SFTP en la carpeta «app» o desde git)."""


def app(environ, start_response):
    cuerpo = "<!doctype html><meta charset=utf-8><title>Aplicación Python</title><h1>La aplicación Python funciona</h1>"
    datos = cuerpo.encode()
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(datos)))])
    return [datos]
'''

EJEMPLO_ASGI = '''"""Aplicación de ejemplo (ASGI): reemplácela por la suya (por SFTP en la carpeta «app» o desde git)."""


async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    datos = "<!doctype html><meta charset=utf-8><title>Aplicación Python</title><h1>La aplicación Python funciona</h1>".encode()
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(datos)).encode())]})
    await send({"type": "http.response.body", "body": datos})
'''

EJEMPLO_NODE = '''// Aplicación de ejemplo: reemplácela por la suya (por SFTP en la carpeta «app» o desde git).
// El panel le da el puerto en PORT y la dirección en HOST (siempre 127.0.0.1: nginx la publica).
const http = require("http");
const servidor = http.createServer((pet, res) => {
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end("<!doctype html><meta charset=utf-8><title>Aplicación Node.js</title><h1>La aplicación Node.js funciona</h1>");
});
servidor.listen(Number(process.env.PORT), process.env.HOST || "127.0.0.1");
'''


def _validar(dominio, tipo, conf):
    if tipo not in TIPOS:
        raise ErrorSitio("tipo de aplicación no válido")
    if not isinstance(conf, dict):
        raise ErrorSitio("configuración no válida")
    propia = {"tipo": tipo}
    git = (conf.get("git") or "").strip()
    if git:
        gc.validar_repo(git)  # https://, ssh:// o usuario@servidor:ruta; nunca con credenciales dentro
        propia["git"] = git
        rama = (conf.get("rama") or "").strip()
        if rama:
            if not RE_RAMA.match(rama) or ".." in rama:
                raise ErrorSitio("rama no válida")
            propia["rama"] = rama
    if tipo == "estatico":
        carpeta = (conf.get("carpeta") or "").strip().strip("/")
        if carpeta:
            if not git:
                raise ErrorSitio("la carpeta a publicar solo se indica con un repositorio git")
            if not RE_CARPETA.match(carpeta) or any(p in ("..", ".") for p in carpeta.split("/")):
                raise ErrorSitio("carpeta no válida")
            propia["carpeta"] = carpeta
        propia["spa"] = bool(conf.get("spa"))
        if conf.get("puerto_publico"):
            raise ErrorSitio("una aplicación estática no abre puertos")
        return propia
    if tipo == "python":
        propia["modo"] = conf.get("modo") or "wsgi"
        if propia["modo"] not in ("wsgi", "asgi"):
            raise ErrorSitio("modo no válido (wsgi o asgi)")
        propia["entrada"] = (conf.get("entrada") or "app:app").strip()
        if not RE_ENTRADA_PY.match(propia["entrada"]):
            raise ErrorSitio("entrada no válida: módulo:objeto (p. ej. app:app o proyecto.wsgi:application)")
    else:
        propia["entrada"] = (conf.get("entrada") or "server.js").strip()
        if propia["entrada"] != "npm start" and (not RE_ENTRADA_JS.match(propia["entrada"]) or ".." in propia["entrada"]):
            raise ErrorSitio("entrada no válida: un archivo .js de la carpeta de la aplicación o «npm start»")
    if conf.get("puerto_publico"):
        try:
            puerto = int(conf["puerto_publico"])
        except (TypeError, ValueError):
            raise ErrorSitio("puerto público no válido")
        propia["puerto_publico"] = srv.validar_puerto_publico(dominio, puerto)
        propia["protocolo"] = conf.get("protocolo") or "tcp"
        if propia["protocolo"] not in ("tcp", "udp"):
            raise ErrorSitio("protocolo no válido (tcp o udp)")
    return propia


def _git(meta, *args, cwd=None):
    """git con el usuario del sitio y la autenticación elegida (la credencial nunca va en la dirección ni en
    .git/config: git la recibe para cada orden)."""
    env = {"HOME": meta["tmp"], **gc.entorno(meta, meta["propia"]["git"], "ninguna")}
    return gc.correr_git(meta, list(args), env, cwd=cwd or meta["app_dir"], tiempo=600)


def _preparar_carpeta(meta, tipo):
    """«app» del usuario del sitio. Una estática la lee nginx (grupo www-data); Python y Node no."""
    os.makedirs(meta["app_dir"])
    grupo = "www-data" if tipo == "estatico" else meta["usuario"]
    ejecutar(["chown", f"{meta['usuario']}:{grupo}", meta["app_dir"]])
    os.chmod(meta["app_dir"], 0o2750 if tipo == "estatico" else 0o750)


def _ejemplo(meta, propia):
    if propia["tipo"] == "python":
        archivo, texto = "app.py", (EJEMPLO_ASGI if propia["modo"] == "asgi" else EJEMPLO_WSGI)
        if propia["entrada"] != "app:app":
            return
    else:
        archivo, texto = "server.js", EJEMPLO_NODE
        if propia["entrada"] != "server.js":
            return
    ruta = os.path.join(meta["app_dir"], archivo)
    with open(ruta, "w") as f:
        f.write(texto)
    ejecutar(["chown", f"{meta['usuario']}:{meta['usuario']}", ruta])


def _raiz_estatica(meta, propia):
    if not propia.get("git"):
        return meta["publico"]
    raiz = os.path.realpath(os.path.join(meta["app_dir"], propia.get("carpeta", "")))
    if not (raiz == meta["app_dir"] or raiz.startswith(meta["app_dir"] + "/")) or not os.path.isdir(raiz):
        raise ErrorSitio(f"el repositorio no tiene la carpeta «{propia.get('carpeta', '')}»")
    return raiz


def _poner_en_marcha(meta):
    srv.dependencias(meta)
    srv.instalar_unidad(meta)
    srv.systemctl(meta, "restart")
    srv.esperar_activo(meta)


def crear(dominio, tipo, conf):
    import sitio

    meta = leer_meta(dominio)
    if meta.get("app"):
        raise ErrorSitio("el sitio ya tiene una aplicación: quítela antes")
    propia = _validar(dominio, tipo, conf)
    if propia.get("git"):  # el método de autenticación sirve para esa dirección (antes de crear nada)
        gc.comprobar_metodo(gc.metodo(meta, "ninguna"), gc.validar_repo(propia["git"])[0])
    meta["app_dir"] = os.path.join(meta["base"], "app")
    usa_carpeta = tipo != "estatico" or propia.get("git")
    if usa_carpeta and os.path.exists(meta["app_dir"]):
        raise ErrorSitio("ya existe la carpeta «app» del sitio: quítela o vacíela antes")
    try:
        if usa_carpeta:
            _preparar_carpeta(meta, tipo)
            if propia.get("git"):
                meta["propia"] = propia  # _git toma de aquí el repositorio
                _git(meta, "clone", "--depth", "1", *(["--branch", propia["rama"]] if propia.get("rama") else []),
                     "--", propia["git"], ".")
            else:
                _ejemplo(meta, propia)
        if tipo == "estatico":
            propia["raiz"] = _raiz_estatica(meta, propia)
        else:
            propia["puerto"] = srv.puerto_interno(meta)
        meta["app"], meta["propia"] = "propia", propia
        if tipo != "estatico":
            _poner_en_marcha(meta)
            if propia.get("puerto_publico"):
                propia["cortafuegos"] = srv.abrir_puerto(meta)
        guardar_meta(meta)
        sitio.escribir_vhost(meta)
        sitio.recargar_nginx()
    except Exception:
        _deshacer(meta, usa_carpeta)
        raise
    return estado(dominio)


def _deshacer(meta, borrar_carpeta):
    import sitio

    srv.quitar_unidad(meta)
    try:
        srv.cerrar_puerto(meta)
    except ErrorSitio:
        pass
    if borrar_carpeta:
        shutil.rmtree(meta["app_dir"], ignore_errors=True)
        shutil.rmtree(srv.ruta_venv(meta), ignore_errors=True)
    meta["app"] = None
    meta.pop("propia", None)
    meta.pop("app_dir", None)
    guardar_meta(meta)
    try:
        sitio.escribir_vhost(meta)
        sitio.recargar_nginx()
    except ErrorSitio:
        pass


def _de_sitio(dominio):
    meta = leer_meta(dominio)
    if meta.get("app") != "propia":
        raise ErrorSitio("el sitio no tiene una aplicación propia")
    return meta


def accion(dominio, que):
    meta = _de_sitio(dominio)
    propia = meta["propia"]
    if que == "desplegar":
        if propia.get("git"):
            _git(meta, "pull", "--ff-only")
        if propia["tipo"] == "estatico":
            if not propia.get("git"):
                raise ErrorSitio("la aplicación estática sin repositorio se actualiza subiendo los archivos por SFTP")
            return estado(dominio)
        _poner_en_marcha(meta)
        return estado(dominio)
    if propia["tipo"] == "estatico":
        raise ErrorSitio("una aplicación estática no se inicia ni se detiene: la sirve nginx")
    if que == "detener":
        srv.systemctl(meta, "stop")
    else:
        srv.systemctl(meta, "restart")
        srv.esperar_activo(meta)
    return estado(dominio)


def estado(dominio):
    import subprocess

    meta = _de_sitio(dominio)
    propia = meta["propia"]
    visible = {k: propia.get(k) for k in ("tipo", "git", "rama", "carpeta", "spa", "modo", "entrada", "puerto_publico",
                                          "protocolo", "cortafuegos") if propia.get(k) not in (None, "")}
    if propia["tipo"] == "estatico":
        return dict(visible, dominio=dominio, activo="nginx", carpeta_servida=os.path.relpath(propia["raiz"], meta["base"]))
    activo = subprocess.run(["systemctl", "is-active", srv.unidad(meta)], capture_output=True, text=True).stdout.strip()
    return dict(visible, dominio=dominio, activo=activo, variables=sorted(srv.leer_entorno(meta)),
                registros=srv.registros(meta))


def entorno(dominio, datos):
    """Variables de entorno: {"CLAVE": "valor"} pone o cambia, {"CLAVE": null} conserva el valor actual;
    las que no vienen se quitan. Reinicia la aplicación para que las tome."""
    meta = _de_sitio(dominio)
    if meta["propia"]["tipo"] == "estatico":
        raise ErrorSitio("una aplicación estática no usa variables de entorno")
    if not isinstance(datos, dict) or len(datos) > 50:
        raise ErrorSitio("variables no válidas (máximo 50)")
    actuales, nuevas = srv.leer_entorno(meta), {}
    for clave, valor in datos.items():
        if not isinstance(clave, str) or not srv.RE_VARIABLE.match(clave):
            raise ErrorSitio(f"nombre de variable no válido: {str(clave)[:40]} (mayúsculas, números y _)")
        if clave in srv.VARIABLES_PROPIAS:
            raise ErrorSitio(f"{clave} la pone el panel y no se puede cambiar")
        if valor is None:
            if clave in actuales:
                nuevas[clave] = actuales[clave]
            continue
        if not isinstance(valor, str) or len(valor) > 4096 or re.search(r"[\x00-\x1f\x7f]", valor):
            raise ErrorSitio(f"valor no válido para {clave} (una línea, hasta 4096 caracteres)")
        nuevas[clave] = valor
    srv.guardar_entorno(meta, nuevas)
    srv.systemctl(meta, "restart")
    try:
        srv.esperar_activo(meta)
    except ErrorSitio as e:
        raise ErrorSitio(f"Variables guardadas, pero {e}")
    return estado(dominio)


def quitar(dominio):
    """Quita la aplicación: para el servicio, cierra su puerto y deja su código en la papelera."""
    import sitio

    meta = _de_sitio(dominio)
    srv.quitar_unidad(meta)
    srv.cerrar_puerto(meta)
    papelera = None
    if os.path.isdir(meta.get("app_dir", "")):
        os.makedirs(PAPELERA, mode=0o700, exist_ok=True)
        papelera = os.path.join(PAPELERA, f"{dominio}-app-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.move(meta["app_dir"], papelera)
        ejecutar(["chown", "-R", "root:root", papelera])
    shutil.rmtree(srv.ruta_venv(meta), ignore_errors=True)
    gc.olvidar(meta)  # la clave o la credencial del repositorio: quítela también en el servidor de git
    meta["app"] = None
    meta.pop("propia", None)
    meta.pop("app_dir", None)
    guardar_meta(meta)
    sitio.escribir_vhost(meta)
    sitio.recargar_nginx()
    return {"dominio": dominio, "quitada": True, "papelera": papelera}


def limpiar_para_baja(meta):
    """Al dar de baja el sitio: servicio y puerto fuera (el código se va a la papelera con el sitio)."""
    if meta.get("app") != "propia":
        return
    srv.quitar_unidad(meta)
    try:
        srv.cerrar_puerto(meta)
    except ErrorSitio:
        pass
