"""Mover y expulsar mensajes con los comandos modernos de IMAP.

Dovecot anuncia MOVE y UIDPLUS: un solo `UID MOVE` sustituye a COPY + STORE \\Deleted + EXPUNGE,
y `UID EXPUNGE` expurga solo los mensajes tocados en vez de recorrer toda la carpeta.
Si el servidor no anunciara esas capacidades se usa el camino clásico.
"""

import aioimaplib


def _capacidades(imap: aioimaplib.IMAP4) -> set:
    caps = getattr(imap, "capabilities", None)
    if caps is None:
        caps = getattr(getattr(imap, "protocol", None), "capabilities", None) or ()
    return {c.upper() for c in caps}


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
    if "MOVE" in _capacidades(imap):
        try:
            resp = await imap.uid("move", uid_set, destino_entrecomillado)
            if resp.result == "OK":
                return True
        except Exception:
            pass
    copia = await imap.uid("copy", uid_set, destino_entrecomillado)
    if copia.result != "OK":
        return False
    await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
    await expulsar_uids(imap, uid_set)
    return True
