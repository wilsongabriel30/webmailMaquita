"""Reinyecta un mensaje ya existente en la cola de salida, sin modificarlo.

Se usa sendmail con el remitente original en el envelope (-f), de modo que el destinatario
recibe exactamente el correo que se escribio: mismo From, mismo cuerpo, mismos adjuntos y
las cabeceras de hilo (In-Reply-To/References) intactas. No es un "FW:" del area de
sistemas, es el mensaje original volviendo a intentarse.
"""
import asyncio
import re
from asyncio.subprocess import PIPE

SENDMAIL = "/usr/sbin/sendmail"
_DIRECCION_OK = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _validar_direcciones(remitente: str, destinatarios: list[str]):
    """Evita inyeccion de argumentos: todo debe parecer una direccion de correo."""
    if not _DIRECCION_OK.match(remitente or ""):
        raise ValueError(f"Remitente invalido: {remitente}")
    if not destinatarios:
        raise ValueError("Sin destinatarios")
    for d in destinatarios:
        if not _DIRECCION_OK.match(d or ""):
            raise ValueError(f"Destinatario invalido: {d}")


async def reinyectar(remitente: str, destinatarios: list[str], mensaje: str) -> None:
    """Vuelve a poner el mensaje en la cola, solo para los destinatarios indicados.

    Importante: se envia unicamente a quienes se pasa en `destinatarios` (normalmente los
    que fallaron), no a todos los del encabezado. Asi no se duplica a quienes si lo
    recibieron la primera vez.
    """
    _validar_direcciones(remitente, destinatarios)
    if not mensaje.strip():
        raise ValueError("El mensaje original esta vacio")

    proc = await asyncio.create_subprocess_exec(
        "sudo", SENDMAIL, "-f", remitente, "--", *destinatarios,
        stdin=PIPE, stdout=PIPE, stderr=PIPE,
    )
    _, err = await proc.communicate(mensaje.encode("utf-8", "ignore"))
    if proc.returncode != 0:
        raise RuntimeError(err.decode("utf-8", "ignore").strip() or "sendmail fallo")
