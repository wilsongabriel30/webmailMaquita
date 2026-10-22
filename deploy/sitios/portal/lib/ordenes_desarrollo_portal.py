"""Para desarrolladores (v1.11), desde el portal: usuarios de bases con permisos, acceso remoto con TLS, cortafuegos
de aplicaciones web del sitio y claves SSH de sus cuentas SFTP.

Son las mismas órdenes que usa el panel general (deploy/sitios/lib/ordenes_desarrollo.py) con dos diferencias:
- el acceso remoto NUNCA lleva «amplia»: una red más amplia que /16 (IPv4) o /48 (IPv6) solo la puede autorizar el
  superadministrador desde el panel general;
- todo va sobre el sitio ya comprobado (alcance del administrador de dominio) y maquita-sitios vuelve a comprobar
  que la base, el usuario o la cuenta son de ese sitio.

Aquí se comprueba la forma de cada dato (claves conocidas, tipos y topes) y se arma el JSON que viaja en base64url.
"""

import ipaddress
import json
import re

from errores import ErrorPortal
from ordenes_sitios import b64, sitios

RE_BASE = re.compile(r"[wx]_[a-z0-9]+(_[0-9a-f]{4})?")
RE_SUFIJO = re.compile(r"[a-z][a-z0-9]{1,9}")
RE_USUARIO = re.compile(r"u_[a-z0-9]+_[a-z][a-z0-9]{1,9}")
RE_CUENTA = re.compile(r"principal|[a-z][a-z0-9]{1,10}")
RE_PRIVILEGIO = re.compile(r"[A-Z][A-Z ]{2,30}")
RE_ID_CLAVE = re.compile(r"[0-9a-f]{8}")
RE_RUTA = re.compile(r"/[A-Za-z0-9._~/-]{0,200}")
PERFILES = ("lectura", "escritura", "estructura", "todo", "medida")
TIEMPO = 120


def _json(datos, tope=8000):
    texto = b64(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    if len(texto) > tope:
        raise ErrorPortal(400, "Demasiados datos de una vez")
    return texto


def _de(ctx, nombre, patron, que):
    valor = ctx.args.get(nombre)
    if not isinstance(valor, str) or not patron.fullmatch(valor):
        raise ErrorPortal(400, f"{que} no válido")
    return valor


def _permisos(valor):
    if not isinstance(valor, dict) or set(valor) - {"perfil", "lista"} or valor.get("perfil") not in PERFILES:
        raise ErrorPortal(400, "Permisos no válidos: lectura, escritura, estructura, todo o una lista a medida")
    if valor["perfil"] != "medida":
        return {"perfil": valor["perfil"]}
    lista = valor.get("lista")
    if not isinstance(lista, list) or not 1 <= len(lista) <= 20 or \
            not all(isinstance(p, str) and RE_PRIVILEGIO.fullmatch(p) for p in lista):
        raise ErrorPortal(400, "Elige al menos un permiso de la lista")
    return {"perfil": "medida", "lista": lista}


# --- Usuarios de bases ---


def usuarios(ctx):
    return sitios("bases-usuarios", ctx.sitio, tiempo=TIEMPO)


def usuario_crear(ctx):
    return sitios("base-usuario-crear", ctx.sitio, _de(ctx, "base", RE_BASE, "Base de datos"),
                  _de(ctx, "sufijo", RE_SUFIJO, "Nombre"), _json(_permisos(ctx.args.get("permisos"))), tiempo=TIEMPO)


def usuario_permisos(ctx):
    return sitios("base-usuario-permisos", ctx.sitio, _de(ctx, "usuario", RE_USUARIO, "Usuario"),
                  _json(_permisos(ctx.args.get("permisos"))), tiempo=TIEMPO)


def usuario(orden):
    def funcion(ctx):
        return sitios(orden, ctx.sitio, _de(ctx, "usuario", RE_USUARIO, "Usuario"), tiempo=TIEMPO)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


def usuario_remoto(ctx):
    """Sin «amplia»: aquí ya se rechaza lo más amplio que /16 o /48 y nunca se abre a todos."""
    lista = ctx.args.get("redes")
    if not isinstance(lista, list) or len(lista) > 20:
        raise ErrorPortal(400, "Se admiten hasta 20 IP o redes por usuario")
    redes = []
    for valor in lista:
        try:
            red = ipaddress.ip_network(str(valor).strip(), strict=False) if isinstance(valor, str) and len(valor) <= 50 else None
        except ValueError:
            red = None
        if red is None:
            raise ErrorPortal(400, f"IP o red no válida: {str(valor)[:50]}")
        if red.prefixlen < (16 if red.version == 4 else 48):
            raise ErrorPortal(400, f"Red demasiado amplia: {red}. Usa una de /{16 if red.version == 4 else 48} o menor; "
                                   "una más amplia solo la puede autorizar el administrador general")
        redes.append(str(red))
    return sitios("base-usuario-remoto", ctx.sitio, _de(ctx, "usuario", RE_USUARIO, "Usuario"), _json(redes), tiempo=TIEMPO)


# --- Cortafuegos de aplicaciones web ---


def waf(ctx):
    return sitios("waf", ctx.sitio, tiempo=TIEMPO)


def waf_guardar(ctx):
    datos = ctx.args.get("waf")
    if not isinstance(datos, dict) or set(datos) - {"modo", "paranoia", "exclusiones"}:
        raise ErrorPortal(400, "Datos del cortafuegos no válidos")
    if datos.get("modo", "bloquear") not in ("apagado", "detectar", "bloquear"):
        raise ErrorPortal(400, "Modo no válido")
    paranoia = datos.get("paranoia", 1)
    if paranoia not in (1, 2) or isinstance(paranoia, bool):
        raise ErrorPortal(400, "El nivel de paranoia es 1 o 2")
    exclusiones = datos.get("exclusiones", [])
    if not isinstance(exclusiones, list) or len(exclusiones) > 50:
        raise ErrorPortal(400, "Se admiten hasta 50 exclusiones")
    limpias = []
    for e in exclusiones:
        if not isinstance(e, dict) or set(e) - {"regla", "ruta"}:
            raise ErrorPortal(400, "Exclusión no válida")
        regla, ruta = e.get("regla"), e.get("ruta")
        if isinstance(regla, bool) or not isinstance(regla, int) or not 900000 <= regla <= 999999:
            raise ErrorPortal(400, "Regla no válida: un número de regla de OWASP CRS (9xxxxx)")
        if ruta not in (None, "") and (not isinstance(ruta, str) or not RE_RUTA.fullmatch(ruta)):
            raise ErrorPortal(400, "Ruta no válida")
        limpias.append({"regla": regla, "ruta": ruta or None})
    limpio = {"modo": datos.get("modo", "bloquear"), "paranoia": paranoia, "exclusiones": limpias}
    return sitios("waf-guardar", ctx.sitio, _json(limpio), tiempo=TIEMPO)


def waf_bloqueos(ctx):
    cuantos = ctx.args.get("cuantos", 50)
    if isinstance(cuantos, bool) or not isinstance(cuantos, int) or not 1 <= cuantos <= 200:
        raise ErrorPortal(400, "Se muestran de 1 a 200 sucesos")
    return sitios("waf-bloqueos", ctx.sitio, str(cuantos), tiempo=TIEMPO)


# --- Claves SSH ---


def ssh_claves(ctx):
    return sitios("ssh-claves", ctx.sitio, tiempo=TIEMPO)


def ssh_clave_agregar(ctx):
    clave = ctx.args.get("clave")
    if not isinstance(clave, str) or not clave.strip() or len(clave) > 5000 or "\n" in clave.strip():
        raise ErrorPortal(400, "Pega una sola clave pública, en una línea")
    return sitios("ssh-clave-agregar", ctx.sitio, _de(ctx, "cuenta", RE_CUENTA, "Cuenta"), b64(clave.strip()), tiempo=TIEMPO)


def ssh_clave_borrar(ctx):
    return sitios("ssh-clave-borrar", ctx.sitio, _de(ctx, "id", RE_ID_CLAVE, "Clave"), tiempo=TIEMPO)


ORDENES = {
    "bases-usuarios": ("sitio", usuarios),
    "base-usuario-crear": ("sitio", usuario_crear),
    "base-usuario-permisos": ("sitio", usuario_permisos),
    "base-usuario-clave": ("sitio", usuario("base-usuario-clave")),
    "base-usuario-borrar": ("sitio", usuario("base-usuario-borrar")),
    "base-usuario-remoto": ("sitio", usuario_remoto),
    "waf": ("sitio", waf),
    "waf-guardar": ("sitio", waf_guardar),
    "waf-bloqueos": ("sitio", waf_bloqueos),
    "ssh-claves": ("sitio", ssh_claves),
    "ssh-clave-agregar": ("sitio", ssh_clave_agregar),
    "ssh-clave-borrar": ("sitio", ssh_clave_borrar),
}
