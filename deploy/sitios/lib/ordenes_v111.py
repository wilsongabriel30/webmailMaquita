"""Órdenes de la v1.11: despliegue desde git de los sitios PHP y uso de CPU y memoria por sitio.

maquita-sitios pasa aquí todo lo que empieza por «git-» o «recursos». La forma de cada orden (la misma que
comprueba maquita-sudo, validar_sitios_v111):

  git-estado <dominio>                       configuración, clave pública, gancho, versiones y registro
  git-configurar <dominio> <JSON b64url>     {repo, rama, carpeta, raiz_web, exclusiones}
  git-clave <dominio>                        clave de despliegue nueva
  git-gancho <dominio> <activar|desactivar>  activar: secreto nuevo (se devuelve una sola vez)
  git-desplegar <dominio> <panel|gancho>     en segundo plano; el resultado sale en git-estado
  git-volver <dominio> <AAAAMMDD-HHMMSS>     publica otra vez una versión guardada
  git-quitar <dominio> <dominio>             quita la configuración (los archivos publicados se quedan)
  recursos <dominio>                         CPU y memoria de las últimas 24 horas
  git-credencial|git-credencial-borrar <dominio>, git-credencial-guardar <dominio> <subida .cred>
                                             autenticación de git del sitio (también de las aplicaciones propias):
                                             ver, guardar (y probar) o borrar; detalle en git_credencial.py
Solo desde el sistema (no las admite maquita-sudo):
  git-desplegar-ahora <dominio> <panel|gancho>   lo que corre en la unidad sitio-git-<usuario>
  recursos-recoger                               temporizador sitios-recursos, cada 5 minutos
"""

import validacion as v
from comun import ErrorSitio

ORIGENES = ("panel", "gancho")


def despachar(args):
    import git_despliegue as gd
    import git_sitio as gs
    import recursos

    n = len(args)
    orden = args[0] if args else ""
    if orden.startswith("git-credencial"):
        import git_credencial

        return git_credencial.despachar(args)
    if args == ["recursos-recoger"]:
        return recursos.recoger()
    if n == 2 and orden == "recursos":
        return recursos.ver(v.dominio(args[1]))
    if n == 2 and orden == "git-estado":
        return gs.estado(v.dominio(args[1]))
    if n == 3 and orden == "git-configurar":
        return gs.configurar(v.dominio(args[1]), v.json_b64(args[2]))
    if n == 2 and orden == "git-clave":
        return gs.regenerar_clave(v.dominio(args[1]))
    if n == 3 and orden == "git-gancho" and args[2] in ("activar", "desactivar"):
        return gs.gancho(v.dominio(args[1]), args[2])
    if n == 3 and orden == "git-desplegar" and args[2] in ORIGENES:
        return gd.lanzar(v.dominio(args[1]), args[2])
    if n == 3 and orden == "git-desplegar-ahora" and args[2] in ORIGENES:
        return gd.desplegar(v.dominio(args[1]), args[2])
    if n == 3 and orden == "git-volver":
        return gd.volver(v.dominio(args[1]), args[2])
    if n == 3 and orden == "git-quitar":
        if args[1] != args[2]:
            raise ErrorSitio("quitar: la confirmación no coincide con el dominio")
        return gs.quitar(v.dominio(args[1]))
    raise ErrorSitio("orden o argumentos no permitidos")
