"""Las etiquetas siguen al correo cuando se mueve o se elimina (09/11/2026).

`message_labels` guarda cada asignación como (owner, carpeta, uid). Hasta ahora mover o eliminar un correo
dejaba esa fila apuntando a un correo que ya no estaba: la etiqueta anunciaba correos que no se veían.
Aquí, DESPUÉS de que IMAP confirme la acción:

- eliminar definitivo (expunge): se borran las asignaciones de (carpeta, uid);
- mover / archivar: se trasladan a (carpeta destino, uid nuevo). El uid nuevo sale del COPYUID que informa
  el servidor (RFC 4315; Dovecot siempre lo da). Si no vino, se resuelve por Message-ID en la carpeta
  destino con las cabeceras leídas ANTES de mover (`preparar_reubicacion`).

Regla: nunca se borra una asignación por un fallo de IMAP. Esto solo se llama cuando la acción se hizo; y
si al mover no se puede saber el uid nuevo, la fila se queda como está (la marcará como faltante el
listado y la purgará `etiquetas_huerfanas` pasados 7 días si no reaparece).
"""

import logging
import re

from app.mail.clients.imap_client import _quote_folder

log = logging.getLogger("maquita.webmail.etiquetas")

ACCIONES_QUE_MUEVEN = frozenset({"move", "archive"})
_MESSAGE_ID = re.compile(rb"Message-ID:\s*(<[^>]+>)", re.IGNORECASE)
_UID_FETCH = re.compile(rb"UID\s+(\d+)")


def _texto(linea) -> bytes:
    if isinstance(linea, str):
        return linea.encode("utf-8", errors="replace")
    return bytes(linea)


async def uids_etiquetados(db, owner: str, folder: str, uids: list[int]) -> list[int]:
    """De los uids dados, cuáles tienen alguna etiqueta (para no trabajar de más)."""
    if not uids or db is None:
        return []
    filas = await db.fetch(
        "SELECT DISTINCT message_uid FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = ANY($3::int[])",
        owner,
        folder,
        uids,
    )
    return [f["message_uid"] for f in filas]


async def message_ids_de(imap, folder: str, uids: list[int]) -> dict[int, str]:
    """{uid: Message-ID} leyendo solo esa cabecera (PEEK: no marca como leído). Carpeta queda seleccionada."""
    if not uids:
        return {}
    try:
        resp = await imap.select(_quote_folder(folder))
        if resp.result != "OK":
            return {}
        resp = await imap.uid(
            "fetch",
            ",".join(str(u) for u in uids),
            "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])",
        )
        if resp.result != "OK":
            return {}
    except Exception as e:
        log.debug("etiquetas: no se pudieron leer Message-ID en %s: %s", folder, e)
        return {}
    salida: dict[int, str] = {}
    uid_actual: int | None = None
    for linea in resp.lines:
        b = _texto(linea)
        m_uid = _UID_FETCH.search(b) if b"FETCH" in b else None
        if m_uid:
            uid_actual = int(m_uid.group(1))
        m_id = _MESSAGE_ID.search(b)
        if m_id and uid_actual is not None:
            salida[uid_actual] = m_id.group(1).decode("utf-8", errors="replace")
    return salida


async def buscar_por_message_id(imap, folder: str, message_id: str) -> int | None:
    """UID del correo con ese Message-ID en la carpeta, o None. Selecciona la carpeta."""
    try:
        resp = await imap.select(_quote_folder(folder))
        if resp.result != "OK":
            return None
        resp = await imap.uid_search("HEADER", "Message-ID", f'"{message_id}"')
        if resp.result != "OK":
            return None
    except Exception:
        return None
    for linea in resp.lines:
        partes = _texto(linea).split()
        numeros = [int(p) for p in partes if p.isdigit()]
        if numeros:
            return numeros[-1]  # si hubiera dos copias, la más nueva
    return None


async def preparar_reubicacion(
    db, imap, owner: str, folder: str, uids: list[int], action: str
) -> dict:
    """Antes de mover: guarda los Message-ID de los correos etiquetados, por si el servidor no da COPYUID.

    Devuelve un contexto para `completar_reubicacion`. Si la acción no mueve, o nada está etiquetado,
    no toca IMAP.
    """
    contexto = {
        "owner": owner,
        "folder": folder,
        "uids": list(uids),
        "action": action,
        "message_ids": {},
    }
    if action not in ACCIONES_QUE_MUEVEN or not uids:
        return contexto
    try:
        etiquetados = await uids_etiquetados(db, owner, folder, uids)
        if etiquetados:
            contexto["message_ids"] = await message_ids_de(imap, folder, etiquetados)
    except Exception as e:
        log.debug(
            "etiquetas: preparación de reubicación falló (%s/%s): %s", owner, folder, e
        )
    return contexto


async def borrar_asignaciones(db, owner: str, folder: str, uids: list[int]) -> int:
    """Borra las asignaciones de esos uids; con lista vacía, las de toda la carpeta (vaciar carpeta)."""
    if db is None:
        return 0
    if uids:
        r = await db.execute(
            "DELETE FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = ANY($3::int[])",
            owner,
            folder,
            uids,
        )
    else:
        r = await db.execute(
            "DELETE FROM message_labels WHERE owner = $1 AND folder = $2", owner, folder
        )
    return _filas(r)


async def trasladar_asignaciones(
    db, owner: str, folder: str, destino: str, mapa: dict[int, int]
) -> int:
    """Pasa las asignaciones de (folder, uid viejo) a (destino, uid nuevo). Devuelve cuántas filas movió.

    Si en el destino ya existiera la misma etiqueta para ese uid (no debería), no se duplica.
    """
    if db is None or not mapa:
        return 0
    movidas = 0
    for viejo, nuevo in mapa.items():
        filas = await db.fetch(
            "SELECT id, label_id FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = $3",
            owner,
            folder,
            viejo,
        )
        if not filas:
            continue
        for f in filas:
            await db.execute(
                """INSERT INTO message_labels (owner, folder, message_uid, label_id, faltante_desde)
                   VALUES ($1, $2, $3, $4, NULL) ON CONFLICT DO NOTHING""",
                owner,
                destino,
                nuevo,
                f["label_id"],
            )
            await db.execute("DELETE FROM message_labels WHERE id = $1", f["id"])
            movidas += 1
    return movidas


async def completar_reubicacion(
    db, imap, contexto: dict, mapa_copyuid: dict[int, int] | None, destino: str
) -> int:
    """Después de que IMAP confirmó la acción. Devuelve filas tocadas. Nunca lanza."""
    owner, folder, uids, action = (
        contexto["owner"],
        contexto["folder"],
        contexto["uids"],
        contexto["action"],
    )
    try:
        if action == "delete":
            n = await borrar_asignaciones(db, owner, folder, uids)
            if n:
                log.info("etiquetas: %s borró %d asignaciones de %s", owner, n, folder)
            return n
        if action not in ACCIONES_QUE_MUEVEN:
            return 0
        destino = destino or "Archive"
        etiquetados = await uids_etiquetados(db, owner, folder, uids)
        if not etiquetados:
            return 0
        mapa: dict[int, int] = {}
        if mapa_copyuid:
            mapa = {u: mapa_copyuid[u] for u in etiquetados if u in mapa_copyuid}
        pendientes = [u for u in etiquetados if u not in mapa]
        if pendientes and contexto.get("message_ids"):
            for u in pendientes:
                mid = contexto["message_ids"].get(u)
                if not mid:
                    continue
                nuevo = await buscar_por_message_id(imap, destino, mid)
                if nuevo is not None:
                    mapa[u] = nuevo
        n = await trasladar_asignaciones(db, owner, folder, destino, mapa)
        sin_resolver = [u for u in etiquetados if u not in mapa]
        if sin_resolver:
            log.warning(
                "etiquetas: %s movió %s→%s pero no se pudo seguir el uid de %s; se quedan hasta reconciliar",
                owner,
                folder,
                destino,
                sin_resolver[:10],
            )
        if n:
            log.info(
                "etiquetas: %s trasladó %d asignaciones de %s a %s",
                owner,
                n,
                folder,
                destino,
            )
        return n
    except Exception as e:
        log.warning(
            "etiquetas: no se pudieron reubicar asignaciones (%s/%s/%s): %s",
            owner,
            folder,
            action,
            e,
        )
        return 0


def _filas(resultado) -> int:
    try:
        return int(str(resultado).split()[-1])
    except (ValueError, IndexError):
        return 0
