"""Recuperar correo borrado, por la propia persona, desde el webmail.

Cuando alguien borra un correo y además vacía la papelera, el mensaje desaparece de su buzón.
Dovecot guarda una copia en una carpeta protegida (lazy_expunge) a la que el usuario NO llega
por IMAP, así que hasta ahora recuperarlo pasaba siempre por sistemas.

Aquí cada persona recupera lo suyo, con dos límites deliberados:

* **Solo los últimos 30 días.** Es lo que la gente ya espera de una papelera (Gmail, Outlook) y
  evita convertir esto en un archivo histórico a la vista. Lo más antiguo sigue guardado y lo
  recupera sistemas desde el panel.
* **No se puede borrar de aquí.** La copia de seguridad es la garantía de no perder correo: si
  se pudiera vaciar desde la interfaz, dejaría de serlo. Quien necesite un borrado de verdad lo
  pide a sistemas, y así queda constancia.

El buzón NUNCA llega por parámetro: es siempre el de la sesión. Nadie puede mirar el correo
borrado de otra persona.
"""

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/mail/borrados", tags=["mail-borrados"])

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
ARCHIVO = "Expunged"
# Lo que ve la persona. Más atrás existe, pero lo recupera sistemas desde el panel.
VENTANA = "30d"
TOPE = 200
_ESPERA = 20

_BUZON = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _buzon_valido(buzon: str) -> str:
    if not _BUZON.match(buzon or ""):
        raise HTTPException(400, "Sesión no válida")
    return buzon


def _uid_valido(uid: str) -> str:
    if not str(uid).isdigit():
        raise HTTPException(400, "Identificador de correo no válido")
    return str(uid)


async def _doveadm(*args: str) -> tuple[str, int]:
    """Ejecuta doveadm por el sudo acotado. Devuelve (salida, código)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo",
            "-n",
            MAQUITA_SUDO,
            "doveadm",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        salida, _ = await asyncio.wait_for(proc.communicate(), timeout=_ESPERA)
        return salida.decode("utf-8", errors="replace"), proc.returncode
    except (asyncio.TimeoutError, Exception):
        return "", 1


def _campos(bloque: str, mapa: dict) -> dict:
    datos = {}
    for linea in bloque.split("\n"):
        for prefijo, clave in mapa.items():
            if linea.startswith(prefijo):
                datos[clave] = linea[len(prefijo) :].strip()
    return datos


@router.get("")
async def listar(texto: str = "", username: str = Depends(get_current_user)):
    """El correo que esta persona borró en los últimos 30 días."""
    buzon = _buzon_valido(username)
    criterio = ["mailbox", ARCHIVO, "savedsince", VENTANA]
    texto = (texto or "").strip()[:100]
    if texto:
        if texto.startswith("-"):
            raise HTTPException(400, "Búsqueda no válida")
        # Los paréntesis no son adorno: sin ellos, `mailbox X savedsince Y subject Z or from Z`
        # se lee como «(archivado reciente con ese asunto) o (ese remitente en CUALQUIER
        # carpeta)», y se colaría correo que no está borrado (21/09/2026).
        criterio += ["(", "subject", texto, "or", "from", texto, ")"]
    else:
        criterio += ["all"]

    salida, rc = await _doveadm(
        "fetch", "-u", buzon, "uid date.received hdr.from hdr.subject", *criterio
    )
    if rc != 0:
        return {"total": 0, "dias": 30, "mensajes": []}

    mapa = {
        "uid: ": "uid",
        "date.received: ": "fecha",
        "hdr.from: ": "de",
        "hdr.subject: ": "asunto",
    }
    # doveadm separa cada correo con un salto de página, no con una línea en blanco.
    mensajes = [
        d for b in salida.split("\f") if (d := _campos(b.strip(), mapa)).get("uid")
    ]
    mensajes.sort(key=lambda m: m.get("fecha", ""), reverse=True)
    return {"total": len(mensajes), "dias": 30, "mensajes": mensajes[:TOPE]}


@router.get("/{uid}")
async def ver(uid: str, username: str = Depends(get_current_user)):
    """Un correo borrado, entero, para confirmar antes de recuperarlo."""
    buzon = _buzon_valido(username)
    # La ventana va también aquí: fuera de los 30 días, para esta persona no existe.
    salida, rc = await _doveadm(
        "fetch",
        "-u",
        buzon,
        "hdr.from hdr.to hdr.date hdr.subject body",
        "mailbox",
        ARCHIVO,
        "savedsince",
        VENTANA,
        "uid",
        _uid_valido(uid),
    )
    if rc != 0 or not salida.strip():
        raise HTTPException(404, "Ese correo ya no se puede recuperar desde aquí")

    cabeceras, _, cuerpo = salida.partition("body:")
    mensaje = _campos(
        cabeceras,
        {
            "hdr.from: ": "de",
            "hdr.to: ": "para",
            "hdr.date: ": "fecha",
            "hdr.subject: ": "asunto",
        },
    )
    mensaje["cuerpo"] = cuerpo.strip()[:4000]
    return mensaje


@router.post("/{uid}/recuperar")
async def recuperar(uid: str, username: str = Depends(get_current_user)):
    """Devuelve el correo a la bandeja de entrada. La copia archivada se conserva."""
    buzon = _buzon_valido(username)
    salida, rc = await _doveadm(
        "copy",
        "-u",
        buzon,
        "INBOX",
        "mailbox",
        ARCHIVO,
        "savedsince",
        VENTANA,
        "uid",
        _uid_valido(uid),
    )
    if rc != 0:
        raise HTTPException(500, "No se pudo recuperar el correo. Inténtalo de nuevo.")
    return {"ok": True, "carpeta": "INBOX"}
