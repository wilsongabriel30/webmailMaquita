"""Mover y expulsar mensajes con los comandos modernos de IMAP.

Dovecot anuncia MOVE y UIDPLUS: un solo `UID MOVE` sustituye a COPY + STORE \\Deleted + EXPUNGE,
y `UID EXPUNGE` expurga solo los mensajes tocados en vez de recorrer toda la carpeta.
Si el servidor no anunciara esas capacidades se usa el camino clásico.
"""

import aioimaplib

from app.mail.clients.imap_copyuid import mapa_copyuid


def _capacidades(imap: aioimaplib.IMAP4) -> set:
    caps = getattr(imap, "capabilities", None)
    if caps is None:
        caps = getattr(getattr(imap, "protocol", None), "capabilities", None) or ()
    return {c.upper() for c in caps}


def _texto(linea) -> str:
    return (
        linea.decode("utf-8", errors="replace")
        if isinstance(linea, (bytes, bytearray))
        else str(linea)
    )


def _ya_copiado(lineas) -> bool:
    """¿El servidor llegó a copiar los mensajes aunque el comando acabara en error?

    Dovecot lo dice en la propia respuesta: `OK [COPYUID ...] Moved UIDs.`
    """
    for linea in lineas or ():
        texto = _texto(linea).upper()
        if "COPYUID" in texto or "MOVED UIDS" in texto:
            return True
    return False


async def _siguen_en_origen(imap: aioimaplib.IMAP4, uid_set: str) -> bool:
    """¿Quedan esos UIDs en la carpeta seleccionada?

    Ante la duda se responde que sí: es preferible fallar el movimiento a duplicar el correo.
    """
    try:
        resp = await imap.uid_search("UID", uid_set)
    except Exception:
        return True
    if resp.result != "OK":
        return True
    for linea in resp.lines:
        texto = _texto(linea).strip()
        if texto.endswith("completed.") or texto.lower().startswith("search completed"):
            continue
        if any(t.isdigit() for t in texto.split()):
            return True
    return False


async def expulsar_uids(imap: aioimaplib.IMAP4, uid_set: str) -> None:
    """Expurga los UIDs indicados (ya marcados \\Deleted); toda la carpeta si es 1:*."""
    if uid_set and uid_set != "1:*" and "UIDPLUS" in _capacidades(imap):
        try:
            await imap.uid("expunge", uid_set)
            return
        except Exception:
            pass
    await imap.expunge()


async def mover_uids(
    imap: aioimaplib.IMAP4, uid_set: str, destino_entrecomillado: str
) -> bool:
    """Mueve los UIDs a la carpeta destino (ya entrecomillada). Carpeta origen ya seleccionada."""
    ok, _ = await mover_uids_con_mapa(imap, uid_set, destino_entrecomillado)
    return ok


async def mover_uids_con_mapa(
    imap: aioimaplib.IMAP4, uid_set: str, destino_entrecomillado: str
) -> tuple[bool, dict[int, int] | None]:
    """Como `mover_uids`, y además devuelve el mapa {uid origen: uid destino} que informa el servidor
    con COPYUID (RFC 4315). Es None si el servidor no lo dijo o el movimiento no se hizo.

    Las etiquetas de base de datos (carpeta + uid) usan ese mapa para seguir al correo (09/11/2026).
    """
    if "MOVE" in _capacidades(imap):
        resp = None
        try:
            resp = await imap.uid("move", uid_set, destino_entrecomillado)
            if resp.result == "OK":
                return True, mapa_copyuid(resp.lines)
        except Exception:
            pass
        # Aqui el MOVE deja el trabajo a medias: copia el mensaje al destino y falla al
        # quitarlo del origen. La respuesta lo cuenta tal cual:
        #   OK [COPYUID 1779177635 5 1095] Moved UIDs.
        #   NO [NONEXISTENT] Mailbox doesn't exist: Expunged
        # Es lazy_expunge, que guarda lo expurgado en una carpeta «Expunged» que el MOVE no
        # encuentra. Volver a copiar dejaba el correo DUPLICADO: sacar uno de No deseado, o
        # moverlo de carpeta, creaba dos copias (21/09/2026). Si el servidor dice que ya
        # copio, solo falta borrarlo del origen.
        if resp is not None and _ya_copiado(resp.lines):
            await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
            await expulsar_uids(imap, uid_set)
            return True, mapa_copyuid(resp.lines)
        # Sin rastro de la copia: si ya no estan en el origen, el movimiento se hizo igual.
        if not await _siguen_en_origen(imap, uid_set):
            return True, None
    copia = await imap.uid("copy", uid_set, destino_entrecomillado)
    if copia.result != "OK":
        return False, None
    await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
    await expulsar_uids(imap, uid_set)
    return True, mapa_copyuid(copia.lines)
