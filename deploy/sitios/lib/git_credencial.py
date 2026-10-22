"""Guardar, ver y borrar la autenticación de git de un sitio (métodos y archivos en git_clave.py).

Órdenes de maquita-sitios (la misma forma comprueba maquita-sudo con sudo_git_credencial.py):

  git-credencial <dominio>                         método, si está configurada, huella o final del token, fecha y,
                                                   con la clave generada, su clave pública. Nunca el secreto.
  git-credencial-guardar <dominio> <subida .cred>  JSON {metodo, repo, clave_privada | token | usuario, contrasena,
                                                   regenerar}. Viaja en un archivo de subidas/ (0600) y no en los
                                                   argumentos, que se ven con «ps» y quedan en el registro de sudo;
                                                   el archivo se borra en cuanto se lee.
  git-credencial-borrar <dominio>                  borra la clave o la credencial guardada (método «ninguna»).

Antes de dejar una credencial nueva en su sitio se prueba con «git ls-remote» contra el repositorio (el que viene o
el configurado): si el servidor de git no la acepta, se queda la anterior y el error dice por qué. La clave generada
no se puede probar hasta que se añada en el repositorio: se prueba si ya existía.
"""

import json
import os
import re
import stat
import time

import git_clave as gc
import validacion as v
from comun import ErrorSitio, ejecutar, guardar_meta, leer_meta

SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_SUBIDA = re.compile(r"[0-9a-f]{32}\.cred")
MAX_SUBIDA = 32 * 1024
MAX_CLAVE = 16 * 1024
CAMPOS = {"metodo", "repo", "clave_privada", "token", "usuario", "contrasena", "regenerar"}
RE_TOKEN = re.compile(r"[\x21-\x7e]{8,512}")
RE_USUARIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,99}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
RE_HUELLA = re.compile(r"^(\d+) (SHA256:[A-Za-z0-9+/=]+) .*\(([A-Z0-9-]+)\)\s*$")
RE_CABECERA = re.compile(r"-----BEGIN ((?:OPENSSH |RSA |EC )?)PRIVATE KEY-----\n[A-Za-z0-9+/=\n:,\- ]+"
                         r"-----END \1PRIVATE KEY-----\n")
# Usuario del token si la persona no lo indica (GitHub: cualquiera; GitLab: «oauth2»; Bitbucket: «x-token-auth»).
USUARIO_TOKEN = (("github.com", "x-access-token"), ("gitlab.com", "oauth2"), ("bitbucket.org", "x-token-auth"))
# Apps con las que convive git: sitio vacío, paquete propio (git del sitio PHP) o aplicación propia.
COMPATIBLES = (None, "paquete", "propia")


# --- Subida ---


def leer_subida(nombre):
    """El JSON de la subida .cred (y la subida se borra, haya ido bien o no)."""
    if not isinstance(nombre, str) or not RE_SUBIDA.fullmatch(nombre):
        raise ErrorSitio("datos de la credencial no válidos")
    ruta = os.path.join(SUBIDAS, nombre)
    try:
        fd = os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ErrorSitio("no llegaron los datos de la credencial")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ErrorSitio("datos de la credencial no válidos")
        datos = os.read(fd, MAX_SUBIDA + 1)
    finally:
        os.close(fd)
        try:
            os.remove(ruta)
        except OSError:
            pass
    if len(datos) > MAX_SUBIDA:
        raise ErrorSitio("los datos de la credencial son demasiado largos")
    try:
        valor = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ErrorSitio("datos de la credencial no válidos")
    if not isinstance(valor, dict):
        raise ErrorSitio("datos de la credencial no válidos")
    return valor


# --- Validación de cada método ---


def _texto(datos, campo):
    valor = datos.get(campo)
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ErrorSitio(f"dato no válido: {campo}")
    return valor


def usuario_token(host, usuario):
    if usuario:
        return usuario
    for nombre, defecto in USUARIO_TOKEN:
        if host == nombre or host.endswith("." + nombre):
            return defecto
    raise ErrorSitio("indique el usuario del token (en Gitea y Forgejo, su nombre de usuario; en un token de "
                     "despliegue de GitLab, el usuario que muestra al crearlo)")


def _validar(datos):
    if set(datos) - CAMPOS:
        raise ErrorSitio("datos de la credencial no válidos")
    m = datos.get("metodo")
    if m not in gc.METODOS:
        raise ErrorSitio("método de autenticación no válido")
    usuario = _texto(datos, "usuario").strip()
    if usuario and not RE_USUARIO.fullmatch(usuario):
        raise ErrorSitio("usuario no válido: letras, números y . _ @ + -")
    limpio = {"metodo": m, "repo": _texto(datos, "repo").strip(), "usuario": usuario,
              "regenerar": datos.get("regenerar") is True}
    if m == "clave-propia":
        clave = _texto(datos, "clave_privada").replace("\r\n", "\n").strip() + "\n"
        if len(clave) > MAX_CLAVE or not RE_CABECERA.fullmatch(clave):
            raise ErrorSitio("pegue la clave PRIVADA SSH completa, de «-----BEGIN … PRIVATE KEY-----» a «-----END …»")
        if "ENCRYPTED" in clave:
            raise ErrorSitio("la clave tiene frase de paso: aquí no se puede usar (no hay nadie que la escriba en cada "
                             "despliegue). Cree una clave solo para este repositorio sin frase, o mejor use la clave "
                             "de despliegue generada")
        limpio["clave_privada"] = clave
    elif m == "token-https":
        token = _texto(datos, "token").strip()
        if not RE_TOKEN.fullmatch(token):
            raise ErrorSitio("token no válido: de 8 a 512 caracteres, sin espacios")
        limpio["token"] = token
    elif m == "usuario-contrasena":
        contrasena = _texto(datos, "contrasena")
        if not usuario:
            raise ErrorSitio("falta el usuario")
        if not 1 <= len(contrasena) <= 512 or _CONTROL.search(contrasena):
            raise ErrorSitio("contraseña no válida (hasta 512 caracteres, en una línea)")
        limpio["contrasena"] = contrasena
    return limpio


# --- Archivos (con el usuario del sitio: nunca root dentro de una carpeta suya) ---


def _escribir(meta, ruta, contenido):
    """`contenido` en `ruta`, 0600, del usuario del sitio. Va por la entrada estándar, no por los argumentos."""
    ejecutar(["sh", "-c", 'umask 077 && cat > "$1"', "sh", ruta], entrada=contenido, como=meta["usuario"], tiempo=30)


def _mover(meta, origen, destino):
    ejecutar(["mv", "-f", "-T", "--", origen, destino], como=meta["usuario"], tiempo=30)


def _borrar(meta, *rutas):
    ejecutar(["rm", "-f", "--", *rutas], como=meta["usuario"], tiempo=30)


def _datos_clave(meta, ruta):
    """(tipo, bits, huella) de una clave privada sin frase de paso, o ErrorSitio."""
    try:
        publica = ejecutar(["ssh-keygen", "-y", "-P", "", "-f", ruta], como=meta["usuario"], tiempo=30)
    except ErrorSitio as e:
        if "passphrase" in str(e).lower():
            raise ErrorSitio("la clave tiene frase de paso: quítesela (ssh-keygen -p -N \"\" -f archivo) o, mejor, "
                             "use la clave de despliegue generada")
        raise ErrorSitio("no es una clave privada SSH válida")
    linea = ejecutar(["ssh-keygen", "-l", "-f", "-"], entrada=publica, como=meta["usuario"], tiempo=30).strip()
    m = RE_HUELLA.match(linea.splitlines()[-1] if linea else "")
    if not m:
        raise ErrorSitio("no es una clave privada SSH válida")
    bits, huella, tipo = int(m.group(1)), m.group(2), m.group(3)
    if tipo not in ("ED25519", "ECDSA", "RSA"):
        raise ErrorSitio(f"tipo de clave no admitido ({tipo}): use ed25519 (recomendado), ECDSA o RSA de 3072 bits")
    if tipo == "RSA" and bits < 3072:
        raise ErrorSitio(f"la clave RSA es de {bits} bits: hacen falta 3072 o más (o use ed25519)")
    return tipo, bits, huella


# --- Órdenes ---


def _repo_configurado(meta):
    return (meta.get("git_php") or {}).get("repo") or (meta.get("propia") or {}).get("git") or ""


def _de_sitio(dominio):
    meta = leer_meta(dominio)
    if meta.get("app") not in COMPATIBLES:
        raise ErrorSitio(f"el sitio tiene {meta.get('app')} del catálogo, que no se despliega desde git")
    return meta


def estado(dominio):
    meta = leer_meta(dominio)
    return dict(gc.resumen(meta), compatible=meta.get("app") in COMPATIBLES, repo=_repo_configurado(meta) or None)


def guardar(dominio, datos):
    meta = _de_sitio(dominio)
    d = _validar(datos)
    m, repo = d["metodo"], d["repo"] or _repo_configurado(meta)
    esquema = None
    if repo:
        esquema, host = gc.validar_repo(repo)
        gc.comprobar_metodo(m, esquema)
    elif m != "clave-generada" and m != "ninguna":
        raise ErrorSitio("indique el repositorio para comprobar la credencial antes de guardarla")
    gc.preparar(meta)
    clave, credencial = gc.ruta_clave(meta), gc.ruta_credencial(meta)
    ahora = time.strftime("%Y-%m-%d %H:%M")
    prueba = None
    if m == "ninguna":
        if repo:
            gc.probar(meta, repo, gc.entorno(meta, repo, m=m))
            prueba = {"ok": True}
        _borrar(meta, clave, clave + ".pub", credencial)
        registro = {"metodo": m, "fecha": ahora}
    elif m == "clave-generada":
        existia = gc.metodo(meta) == "clave-generada" and gc.clave_publica(meta)
        if d["regenerar"] or not existia:
            gc.generar_clave(meta)
        _borrar(meta, credencial)
        if existia and not d["regenerar"] and esquema == "ssh":
            try:
                gc.probar(meta, repo, gc.entorno(meta, repo, m=m))
                prueba = {"ok": True}
            except ErrorSitio as e:
                prueba = {"ok": False, "error": str(e)}
        registro = dict(gc.registro_generada(meta), fecha=ahora)
    elif m == "clave-propia":
        nueva = clave + ".nueva"
        _escribir(meta, nueva, d["clave_privada"])
        try:
            tipo, bits, huella = _datos_clave(meta, nueva)
            _borrar(meta, gc.ruta_conocidos(meta))  # la huella del servidor se aprende de nuevo con esta clave
            gc.probar(meta, repo, gc.entorno(meta, repo, m=m, clave=nueva))
        except ErrorSitio:
            _borrar(meta, nueva)
            raise
        _mover(meta, nueva, clave)
        _borrar(meta, clave + ".pub", credencial)
        prueba = {"ok": True}
        registro = {"metodo": m, "fecha": ahora, "tipo_clave": f"{tipo} {bits}", "huella": huella}
    else:
        usuario = usuario_token(host, d["usuario"]) if m == "token-https" else d["usuario"]
        secreto = d["token"] if m == "token-https" else d["contrasena"]
        nueva = credencial + ".nueva"
        _escribir(meta, nueva, f"username={usuario}\npassword={secreto}\n")
        try:
            gc.probar(meta, repo, gc.entorno(meta, repo, m=m, credencial=nueva))
        except ErrorSitio:
            _borrar(meta, nueva)
            raise
        _mover(meta, nueva, credencial)
        _borrar(meta, clave, clave + ".pub")
        prueba = {"ok": True}
        registro = {"metodo": m, "fecha": ahora, "usuario": usuario}
        if m == "token-https":
            registro["final"] = secreto[-4:]
    meta = leer_meta(dominio)  # otra orden pudo cambiar el meta mientras se probaba
    meta["git_auth"] = registro
    guardar_meta(meta)
    return dict(estado(dominio), prueba=prueba)


def borrar(dominio):
    meta = leer_meta(dominio)
    if os.path.isdir(gc.carpeta(meta)):
        _borrar(meta, gc.ruta_clave(meta), gc.ruta_clave(meta) + ".pub", gc.ruta_credencial(meta))
    meta["git_auth"] = {"metodo": "ninguna", "fecha": time.strftime("%Y-%m-%d %H:%M")}
    guardar_meta(meta)
    return estado(dominio)


ORDENES = ("git-credencial", "git-credencial-guardar", "git-credencial-borrar")


def despachar(args):
    if len(args) == 2 and args[0] == "git-credencial":
        return estado(v.dominio(args[1]))
    if len(args) == 3 and args[0] == "git-credencial-guardar":
        dominio = v.dominio(args[1])
        return guardar(dominio, leer_subida(args[2]))
    if len(args) == 2 and args[0] == "git-credencial-borrar":
        return borrar(v.dominio(args[1]))
    raise ErrorSitio("orden o argumentos no permitidos")
