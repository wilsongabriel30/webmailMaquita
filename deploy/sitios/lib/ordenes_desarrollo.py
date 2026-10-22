"""Órdenes «para desarrolladores» (v1.11): usuarios de bases con permisos, acceso remoto con TLS, cortafuegos de
aplicaciones web por sitio y claves SSH de las cuentas SFTP.

maquita-sitios pasa aquí las órdenes de ORDENES. La forma de cada una (la misma que comprueba maquita-sudo,
_validar_sitios_desarrollo):

  bases-usuarios <dominio>                                          usuarios, bases, privilegios y estado del servidor
  base-usuario-crear <dominio> <base> <sufijo> <permisos JSON b64>  {"perfil": "lectura"} o {"perfil": "medida", "lista": [...]}
  base-usuario-permisos <dominio> <usuario> <permisos JSON b64>
  base-usuario-clave <dominio> <usuario>                            contraseña nueva (se muestra una vez)
  base-usuario-borrar <dominio> <usuario>
  base-usuario-remoto <dominio> <usuario> <lista JSON b64> [amplia] IP o redes con acceso (TLS); «amplia» solo la
                                                                    pasa el panel general con la confirmación del
                                                                    superadministrador
  waf <dominio>                                                     modo, paranoia y exclusiones del sitio
  waf-guardar <dominio> <JSON b64>                                  {"modo", "paranoia", "exclusiones"}
  waf-bloqueos <dominio> [cuántos 1-200]                            últimos bloqueos y detecciones
  ssh-claves <dominio>                                              claves SSH de las cuentas SFTP del sitio
  ssh-clave-agregar <dominio> <cuenta> <clave pública b64>          «principal» o el nombre de una cuenta adicional
  ssh-clave-borrar <dominio> <id de 8 hex>
"""

import re

import validacion as v
from comun import ErrorSitio, de_base64

ORDENES = ("bases-usuarios", "base-usuario-crear", "base-usuario-permisos", "base-usuario-clave", "base-usuario-borrar",
           "base-usuario-remoto", "waf", "waf-guardar", "waf-bloqueos", "ssh-claves", "ssh-clave-agregar",
           "ssh-clave-borrar")
RE_BASE = re.compile(r"[wx]_[a-z0-9]+(_[0-9a-f]{4})?")
RE_CUENTA = re.compile(r"principal|[a-z][a-z0-9]{1,10}")


def _texto(b64, que, tope=17000):
    try:
        texto = de_base64(b64)
    except ValueError:
        raise ErrorSitio(f"{que} no válida")
    if not texto or len(texto) > tope:
        raise ErrorSitio(f"{que} no válida")
    return texto


def _base(valor):
    if not RE_BASE.fullmatch(valor):
        raise ErrorSitio("base de datos no válida")
    return valor


def despachar(args):
    import bases_usuarios as bu
    import claves_ssh
    import waf_bloqueos
    import waf_sitio

    n, orden = len(args), args[0] if args else ""
    if n == 2 and orden == "bases-usuarios":
        return bu.listar(v.dominio(args[1]))
    if n == 5 and orden == "base-usuario-crear":
        return bu.crear(v.dominio(args[1]), _base(args[2]), args[3], v.json_b64(args[4]))
    if n == 4 and orden == "base-usuario-permisos":
        return bu.cambiar_permisos(v.dominio(args[1]), args[2], v.json_b64(args[3]))
    if n == 3 and orden == "base-usuario-clave":
        return bu.nueva_clave(v.dominio(args[1]), args[2])
    if n == 3 and orden == "base-usuario-borrar":
        return bu.borrar(v.dominio(args[1]), args[2])
    if n in (4, 5) and orden == "base-usuario-remoto" and (n == 4 or args[4] == "amplia"):
        return bu.remoto(v.dominio(args[1]), args[2], v.json_b64(args[3]), amplia=n == 5)
    if n == 2 and orden == "waf":
        return waf_sitio.ver(v.dominio(args[1]))
    if n == 3 and orden == "waf-guardar":
        return waf_sitio.guardar(v.dominio(args[1]), v.json_b64(args[2]))
    if n in (2, 3) and orden == "waf-bloqueos" and (n == 2 or re.fullmatch(r"[1-9][0-9]{0,2}", args[2])):
        return waf_bloqueos.ultimos(v.dominio(args[1]), int(args[2]) if n == 3 else 50)
    if n == 2 and orden == "ssh-claves":
        return claves_ssh.listar(v.dominio(args[1]))
    if n == 4 and orden == "ssh-clave-agregar" and RE_CUENTA.fullmatch(args[2]):
        return claves_ssh.agregar(v.dominio(args[1]), args[2], _texto(args[3], "clave"))
    if n == 3 and orden == "ssh-clave-borrar":
        return claves_ssh.borrar(v.dominio(args[1]), args[2])
    raise ErrorSitio("orden o argumentos no permitidos")
