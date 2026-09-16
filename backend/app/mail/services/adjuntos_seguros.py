"""Extensiones de archivo que no se aceptan ni en borradores ni en envíos.

Son ejecutables, scripts o contenedores que Windows u Office abren sin preguntar.
El análisis antimalware (safeattach) sigue actuando sobre el resto de archivos.
"""

from fastapi import HTTPException

EXTENSIONES_PELIGROSAS = {
    # ejecutables y bibliotecas
    "exe", "dll", "com", "scr", "pif", "msi", "msp", "cpl", "sys", "drv",
    # scripts y automatizaciones
    "bat", "cmd", "ps1", "psm1", "vbs", "vbe", "js", "jse", "wsf", "wsh", "hta",
    "jar", "reg", "lnk", "sh", "app", "apk", "gadget", "inf", "scf", "url",
    # contenedores que se montan o abren solos y datos binarios sin tipo
    "iso", "img", "vhd", "vhdx", "dat",
}


def extension_de(nombre: str) -> str:
    nombre = (nombre or "").strip().lower().rstrip(". ")
    return nombre.rsplit(".", 1)[-1] if "." in nombre else ""


def es_peligroso(nombre: str) -> bool:
    return extension_de(nombre) in EXTENSIONES_PELIGROSAS


def rechazar_peligrosos(nombres) -> None:
    """Lanza 422 si algún nombre de archivo tiene una extensión bloqueada."""
    malos = [n for n in nombres if es_peligroso(n)]
    if malos:
        raise HTTPException(
            status_code=422,
            detail={
                "attachment_blocked": True,
                "filename": malos[0],
                "filenames": malos,
                "reason": "Tipo de archivo no permitido por seguridad (."
                + extension_de(malos[0])
                + "). Comprímalo en .zip con contraseña si de verdad hay que enviarlo.",
            },
        )
