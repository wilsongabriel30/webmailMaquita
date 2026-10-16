"""Acceso a los archivos del sitio (FTP seguro y SFTP) y certificado HTTPS.

FTP y SFTP usan la misma cuenta: el usuario de sistema del sitio, encerrado en su carpeta.
- FTP solo con cifrado (FTPS explícito, vsftpd). Sin cifrado no se acepta el inicio de sesión.
- SFTP por SSH con `internal-sftp` y ChrootDirectory (sshd_config.d/sitios.conf), sin shell.
Mientras el acceso está desactivado la cuenta no tiene contraseña válida y no figura en la lista
de vsftpd.
"""

import os

from comun import ACME_WEBROOT, LISTA_FTP, ErrorSitio, clave, ejecutar, guardar_meta, leer_meta


def _lista():
    try:
        with open(LISTA_FTP) as f:
            return [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return []


def _guardar_lista(usuarios):
    tmp = LISTA_FTP + ".tmp"
    with open(tmp, "w") as f:
        f.write("".join(u + "\n" for u in sorted(set(usuarios))))
    os.chmod(tmp, 0o644)
    os.replace(tmp, LISTA_FTP)


def quitar_de_lista_ftp(usuario):
    _guardar_lista([u for u in _lista() if u != usuario])


def ftp(dominio, accion):
    """accion: activar (o nueva clave) | desactivar. Devuelve la clave nueva una sola vez."""
    meta = leer_meta(dominio)
    usuario = meta["usuario"]
    if accion == "desactivar":
        ejecutar(["passwd", "-l", usuario])
        quitar_de_lista_ftp(usuario)
        meta["ftp"] = False
        guardar_meta(meta)
        return {"dominio": dominio, "ftp": False}
    nueva = clave(16)
    ejecutar(["chpasswd"], entrada=f"{usuario}:{nueva}\n")
    ejecutar(["passwd", "-u", usuario])
    _guardar_lista(_lista() + [usuario])
    meta["ftp"] = True
    guardar_meta(meta)
    return {
        "dominio": dominio,
        "ftp": True,
        "usuario": usuario,
        "clave": nueva,
        "carpeta_web": "publico",
    }


def ssl(dominio, correo):
    """Pide el certificado de Let's Encrypt por HTTP (el dominio ya debe apuntar a este servidor)."""
    import sitio

    meta = leer_meta(dominio)
    nombres = [dominio] + (["www." + dominio] if meta.get("www", True) else [])
    base = ["certbot", "certonly", "--webroot", "-w", ACME_WEBROOT, "--non-interactive", "--agree-tos",
            "-m", correo, "--cert-name", dominio, "--key-type", "ecdsa",
            "--deploy-hook", "systemctl reload nginx"]
    try:
        ejecutar(base + sum((["-d", n] for n in nombres), []), tiempo=300)
    except ErrorSitio as e:
        if len(nombres) == 1:
            raise ErrorSitio(f"no se pudo emitir el certificado: ¿{dominio} apunta ya a este servidor? ({e})")
        # Si www todavía no existe en el DNS, se emite solo para el dominio y www queda sin HTTPS.
        ejecutar(base + ["-d", dominio], tiempo=300)
        meta["www"] = False
    meta["ssl"] = True
    guardar_meta(meta)
    sitio.escribir_vhost(meta)
    sitio.recargar_nginx()
    if meta.get("app") == "wordpress":
        # WordPress guarda su dirección: sin esto seguiría enlazando a http://
        import aplicaciones

        for opcion in ("home", "siteurl"):
            aplicaciones._wp(meta, "option", "update", opcion, f"https://{dominio}")
        meta["app_admin"] = f"https://{dominio}/wp-admin/"
        guardar_meta(meta)
    return sitio.publico(meta)
