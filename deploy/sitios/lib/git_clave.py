"""Autenticación de git de un sitio, común a los sitios PHP (git_sitio.py, git_despliegue.py) y a las aplicaciones
propias Node.js, Python y estáticas (propias.py).

Un sitio tiene a la vez como mucho una de las dos cosas (git del sitio PHP o aplicación propia) y una sola forma de
autenticarse ante su servidor de git, que se elige en «Autenticación»:

  clave-generada      clave de despliegue ed25519 creada aquí (recomendada): la pública se añade en el repositorio
                      como clave de SOLO LECTURA; la privada nunca sale del servidor ni se muestra.
  clave-propia        una clave privada SSH de la persona (ed25519, ECDSA o RSA de 3072 bits o más), sin frase de paso.
  token-https         un token de acceso por HTTPS (GitHub, GitLab, Gitea, Forgejo, Bitbucket), con su usuario.
  usuario-contrasena  usuario y contraseña por HTTPS (servidores de git propios que no tienen otra cosa).
  ninguna             repositorio público por HTTPS.

Todo vive en la carpeta de despliegues del sitio, fuera de la carpeta pública, del usuario del sitio y 0700:

    /srv/sitios/<dominio>/despliegues/.ssh/clave        la clave (generada o propia), 0600
    /srv/sitios/<dominio>/despliegues/.ssh/conocidos    huellas de los servidores, fijadas en la primera conexión
    /srv/sitios/<dominio>/despliegues/.credencial/git   «username=…» y «password=…» del token o la contraseña, 0600

En el meta del sitio («git_auth») queda solo el método, la fecha, la huella de la clave o los cuatro últimos caracteres
del token: nunca el secreto. Git lo recibe sin que pase por la línea de órdenes, el entorno, la dirección del
repositorio ni .git/config: la clave con GIT_SSH_COMMAND (-i <archivo>) y el token o la contraseña con un ayudante de
credenciales que lee el archivo («credential.helper», puesto con GIT_CONFIG_* solo para esa orden).

Guardar, probar y borrar credenciales está en git_credencial.py.
"""

import os
import re
import subprocess
import time

from comun import ErrorSitio, ejecutar

METODOS = ("clave-generada", "clave-propia", "token-https", "usuario-contrasena", "ninguna")
CON_CLAVE = ("clave-generada", "clave-propia")
CON_SECRETO = ("token-https", "usuario-contrasena")

_HOST = r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252})"
_RUTA = r"[A-Za-z0-9._~][A-Za-z0-9._~/-]{0,299}"
RE_HTTPS = re.compile(rf"https://(?P<host>{_HOST})(?::\d{{1,5}})?/{_RUTA}")
RE_SSH = re.compile(rf"ssh://[A-Za-z0-9][A-Za-z0-9._-]{{0,63}}@(?P<host>{_HOST})(?::\d{{1,5}})?/{_RUTA}")
RE_SCP = re.compile(rf"[A-Za-z0-9][A-Za-z0-9._-]{{0,63}}@(?P<host>{_HOST}):{_RUTA}")
RE_CLAVE_PUBLICA = re.compile(r"ssh-ed25519 [A-Za-z0-9+/=]{60,100}(?: [A-Za-z0-9.@_-]{1,200})?")
# «https://usuario:token@servidor/…» o «ssh://usuario:contraseña@servidor/…»: credenciales metidas en la dirección.
RE_CON_CREDENCIAL = re.compile(r"(?:https?|ssh)://[^/@\s]*@")

TIEMPO_PRUEBA = 45
_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


# --- Rutas ---


def carpeta(meta):
    return os.path.join(meta["base"], "despliegues")


def carpeta_ssh(meta):
    return os.path.join(carpeta(meta), ".ssh")


def ruta_clave(meta):
    return os.path.join(carpeta_ssh(meta), "clave")


def ruta_conocidos(meta):
    return os.path.join(carpeta_ssh(meta), "conocidos")


def carpeta_credencial(meta):
    return os.path.join(carpeta(meta), ".credencial")


def ruta_credencial(meta):
    return os.path.join(carpeta_credencial(meta), "git")


# --- Dirección del repositorio ---


def validar_repo(repo):
    """(«https» o «ssh», servidor) de una dirección válida, o ErrorSitio. Nunca con credenciales dentro."""
    if not isinstance(repo, str) or ".." in repo:
        raise ErrorSitio("repositorio no válido")
    if RE_CON_CREDENCIAL.match(repo) and not RE_SSH.fullmatch(repo):
        raise ErrorSitio("no ponga usuario, contraseña ni token en la dirección del repositorio (quedarían en los "
                         "registros y en la configuración de git): use la dirección sin ellos y elija el método en "
                         "«Autenticación» (recomendado: clave de despliegue de solo lectura)")
    for esquema, patron in (("https", RE_HTTPS), ("ssh", RE_SSH), ("ssh", RE_SCP)):
        m = patron.fullmatch(repo)
        if m:
            return esquema, m.group("host")
    raise ErrorSitio("repositorio no válido: use https://servidor/ruta.git, ssh://usuario@servidor/ruta.git "
                     "o usuario@servidor:ruta.git (sin contraseñas en la dirección)")


def host_de(repo):
    return validar_repo(repo)[1]


# --- Método elegido ---


def metodo(meta, defecto=None):
    """El método guardado; sin él, `defecto` o, si no se da, la clave generada si existe (sitios PHP de la v1.11)."""
    elegido = (meta.get("git_auth") or {}).get("metodo")
    if elegido in METODOS:
        return elegido
    if defecto:
        return defecto
    return "clave-generada" if meta.get("git_php") or clave_publica(meta) else "ninguna"


def comprobar_metodo(m, esquema):
    """ErrorSitio si el método no sirve para esa forma de dirección."""
    if esquema == "ssh" and m not in CON_CLAVE:
        raise ErrorSitio("un repositorio por SSH necesita una clave: elija «Clave de despliegue» (recomendado) o "
                         "«Clave SSH propia» en «Autenticación», o use la dirección https:// si el repositorio es público")
    if esquema == "https" and m == "clave-propia":
        raise ErrorSitio("una clave SSH solo sirve con la dirección SSH del repositorio (git@servidor:organizacion/repo.git)")


def _ayudante_credencial(ruta):
    """Ayudante de credenciales de git: en «get» devuelve el archivo (username=…, password=…); lo demás lo ignora."""
    return f"!f() {{ test \"$1\" = get && cat '{ruta}'; }}; f"


def entorno(meta, repo, defecto=None, m=None, clave=None, credencial=None):
    """Variables para git (además de HOME): protocolos admitidos, sin preguntas y con la credencial del método.
    `clave` y `credencial` permiten probar una nueva antes de dejarla en su sitio."""
    esquema, _ = validar_repo(repo)
    m = m or metodo(meta, defecto)
    comprobar_metodo(m, esquema)
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_ALLOW_PROTOCOL": "https:ssh" if m in CON_CLAVE else "https",
           # Ningún ayudante de credenciales del sistema o de la cuenta: solo el nuestro, si lo hay.
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": ""}
    if esquema == "ssh":
        env["GIT_SSH_COMMAND"] = (f"ssh -i {clave or ruta_clave(meta)} -o IdentitiesOnly=yes -o BatchMode=yes "
                                  f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={ruta_conocidos(meta)} "
                                  "-o ConnectTimeout=20")
    elif m in CON_SECRETO:
        ruta = credencial or ruta_credencial(meta)
        if not credencial and not os.path.isfile(ruta):
            raise ErrorSitio("falta la credencial guardada del repositorio: vuelva a configurar la autenticación")
        env.update({"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_1": "credential.helper",
                    "GIT_CONFIG_VALUE_1": _ayudante_credencial(ruta)})
    return env


# --- Errores de git, en claro ---

_ERRORES = (
    (("remote branch", "couldn't find remote ref", "could not find remote branch"),
     "la rama indicada no existe en el repositorio"),
    (("host key verification failed", "remote host identification has changed"),
     ("la huella del servidor de git no coincide con la de la primera conexión: si el cambio es legítimo, vuelva a "
      "guardar la autenticación (se olvida la huella anterior)")),
    (("could not read username", "could not read password", "terminal prompts disabled"),
     "el repositorio pide credenciales (es privado o la dirección no existe): elija un método en «Autenticación»"),
    (("permission denied (publickey", "authentication failed", "invalid username or password", "access denied",
      "http basic", "bad credentials", "error: 401", "error: 403", "returned error: 403", "returned error: 401",
      "permission to", "not authorized", "invalid credentials"),
     ("credencial rechazada por el servidor de git: compruebe que la clave de despliegue está añadida al repositorio, "
      "o que el token sigue vigente y tiene permiso de lectura sobre él")),
    (("repository not found", "does not appear to be a git repository", "not found", "error: 404",
      "project you were looking for could not be found"),
     "repositorio no encontrado: revise la dirección (o la credencial no tiene acceso a ese repositorio)"),
    (("could not resolve host", "could not resolve hostname", "name or service not known",
      "temporary failure in name resolution"),
     "servidor de git desconocido: no se encuentra su nombre"),
    (("connection timed out", "operation timed out", "connection refused", "network is unreachable",
      "no route to host", "failed to connect"),
     "no se pudo conectar con el servidor de git (tiempo agotado o conexión rechazada)"),
)


def explicar(salida):
    """La causa en claro de un fallo de git (o None si no se reconoce)."""
    texto = (salida or "").lower()
    for marcas, mensaje in _ERRORES:
        if any(x in texto for x in marcas):
            return mensaje
    return None


def correr_git(meta, args, env, cwd=None, tiempo=600):
    """git `args` como el usuario del sitio, con `env`. Devuelve la salida; si falla, ErrorSitio con la causa."""
    entorno_total = {"PATH": _PATH, "LANG": "C.UTF-8", "HOME": carpeta(meta), **env}
    try:
        r = subprocess.run(["runuser", "-u", meta["usuario"], "--", "git", *args], capture_output=True, text=True,
                           timeout=tiempo, env=entorno_total, cwd=cwd or "/", check=False)
    except subprocess.TimeoutExpired:
        raise ErrorSitio("git tardó demasiado: el servidor de git no responde")
    salida = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        lineas = [x for x in salida.splitlines() if x.strip()]
        raise ErrorSitio(explicar(salida) or ("git: " + (lineas[-1][:300] if lineas else f"código {r.returncode}")))
    return r.stdout or ""


def probar(meta, repo, env):
    """«git ls-remote» con la credencial: ErrorSitio con la causa si el servidor no la acepta."""
    correr_git(meta, ["-c", "core.hooksPath=/dev/null", "ls-remote", "--heads", "--", repo], env, tiempo=TIEMPO_PRUEBA)


# --- Carpetas y clave generada (todo con el usuario del sitio) ---


def preparar(meta):
    """despliegues/, .ssh/ y .credencial/ del usuario del sitio, 0700. despliegues/ la crea root (la carpeta del
    sitio es de root) y se la da al usuario."""
    base = carpeta(meta)
    if os.path.islink(base) or (os.path.exists(base) and not os.path.isdir(base)):
        raise ErrorSitio("la carpeta de despliegues del sitio no es válida")
    if not os.path.isdir(base):
        os.mkdir(base, 0o700)
        ejecutar(["chown", f"{meta['usuario']}:{meta['usuario']}", base])
    ejecutar(["mkdir", "-p", "-m", "700", carpeta_ssh(meta), carpeta_credencial(meta)], como=meta["usuario"])


def generar_clave(meta):
    """Clave ed25519 nueva (la anterior deja de valer en cuanto se borre del servidor de git)."""
    preparar(meta)
    ejecutar(["rm", "-f", "--", ruta_clave(meta), ruta_clave(meta) + ".pub"], como=meta["usuario"])
    ejecutar(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", f"despliegue@{meta['dominio']}", "-f", ruta_clave(meta)],
             como=meta["usuario"], tiempo=60)


def clave_publica(meta):
    """La clave pública generada (para el servidor de git) o None. Es del usuario: se lee sin seguir enlaces."""
    try:
        fd = os.open(ruta_clave(meta) + ".pub", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        texto = os.read(fd, 2048).decode("ascii", errors="replace").strip()
    finally:
        os.close(fd)
    return texto if RE_CLAVE_PUBLICA.fullmatch(texto) else None


def huella_publica(texto):
    """«SHA256:…» de una clave pública en una línea (sin ssh-keygen: es el hash del blob en base64)."""
    import base64
    import hashlib

    try:
        blob = base64.b64decode(texto.split()[1])
    except (IndexError, ValueError):
        return None
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def registro_generada(meta):
    """Lo que se anota en el meta al generar la clave: método, fecha y huella."""
    return {"metodo": "clave-generada", "fecha": time.strftime("%Y-%m-%d %H:%M"), "tipo_clave": "ED25519 256",
            "huella": huella_publica(clave_publica(meta) or "")}


def olvidar(meta):
    """Borra la clave, la credencial y las huellas, y el método del meta (lo guarda quien llama)."""
    if os.path.isdir(carpeta(meta)) and not os.path.islink(carpeta(meta)):
        ejecutar(["rm", "-rf", "--", carpeta_ssh(meta), carpeta_credencial(meta)], como=meta["usuario"])
    meta.pop("git_auth", None)


# --- Lo que se enseña (nunca el secreto) ---


def resumen(meta, defecto=None):
    m = metodo(meta, defecto)
    auth = meta.get("git_auth") or {}
    datos = {"dominio": meta["dominio"], "metodo": m, "metodos": list(METODOS), "fecha": auth.get("fecha")}
    if m == "clave-generada":
        datos["clave_publica"] = clave_publica(meta)
        datos["configurada"] = bool(datos["clave_publica"])
        datos["huella"] = huella_publica(datos["clave_publica"] or "") or auth.get("huella")
        datos["tipo_clave"] = "ED25519 256"
    elif m == "clave-propia":
        datos["configurada"] = os.path.isfile(ruta_clave(meta))
        datos.update({k: auth.get(k) for k in ("huella", "tipo_clave")})
    elif m in CON_SECRETO:
        datos["configurada"] = os.path.isfile(ruta_credencial(meta))
        datos.update({k: auth.get(k) for k in ("usuario", "final")})
    else:
        datos["configurada"] = False
    return datos
