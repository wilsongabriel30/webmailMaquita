"""Correo nuevo en carpetas distintas de INBOX (09/11/2026).

Pedido: «cuando llega correo a las carpetas (por una regla) no se pintan las carpetas con el
correo que llegó». El sondeo de `router._poll_user_inbox` solo miraba INBOX, así que un correo
que una regla de Sieve archiva directo en «Proveedores» no avisaba ni actualizaba el contador de
la carpeta hasta que la persona hacía algo. Aquí, en el mismo ciclo y con la misma conexión IMAP,
se comparan los no leídos de cada carpeta con el ciclo anterior (estado compartido en Redis, así
no avisa en falso al cambiar de worker) y se publica `new_mail` con la carpeta afectada; el
frontend ya sabe pintar el contador de `data.folder` y mostrar el aviso.
"""

from __future__ import annotations

import json
import logging

from app.mail.clients.imap_client import list_folders
from app.mail.services.folder_service import detect_folder_type
from app.websocket.resumen_correo_nuevo import resumen_correo

logger = logging.getLogger("maquita.webmail.sondeo_carpetas")

# Carpetas en las que un «no leído» nuevo no es correo que llega: no se avisa por ellas.
SIN_AVISO = {"inbox", "sent", "drafts", "trash", "junk"}
TTL_ESTADO_S = 24 * 3600


def _clave(usuario: str) -> str:
    return f"sondeo:carpetas:{usuario.lower()}"


async def _ultimo_sin_leer_en(imap, carpeta_imap: str) -> int | None:
    """UID del correo sin leer más reciente de la carpeta dada (la selecciona)."""
    try:
        from app.mail.clients.imap_client import _quote_folder

        r = await imap.select(_quote_folder(carpeta_imap))
        if getattr(r, "result", "") != "OK":
            return None
        r = await imap.uid_search("UNSEEN")
        if getattr(r, "result", "") != "OK":
            return None
        uids: list[int] = []
        for linea in r.lines or []:
            texto = (
                linea.decode("utf-8", "replace")
                if isinstance(linea, bytes)
                else str(linea)
            )
            uids.extend(int(u) for u in texto.split() if u.isdigit())
        return max(uids) if uids else None
    except Exception:
        return None


async def sondear(imap, redis, usuario: str, db=None) -> int:
    """Revisa las carpetas (menos INBOX y las especiales) y publica `new_mail` / `folder_update`.

    Devuelve cuántas carpetas recibieron correo nuevo. Nunca lanza: un fallo aquí no debe tumbar
    el sondeo de INBOX.
    """
    try:
        carpetas = await list_folders(imap)
    except Exception as exc:
        logger.debug(
            "sondeo de carpetas de %s: no se pudieron listar (%s)", usuario, exc
        )
        return 0

    try:
        previo_crudo = await redis.get(_clave(usuario))
        previo: dict[str, int] = json.loads(previo_crudo) if previo_crudo else {}
    except Exception:
        previo = {}

    actual: dict[str, int] = {}
    con_correo_nuevo = 0
    for c in carpetas:
        if "Noselect" in c.get("flags", []):
            continue
        tipo = detect_folder_type(c["name"], c.get("flags", []))
        if tipo in SIN_AVISO:
            continue
        nombre = c["name"]
        unseen = int(c.get("unseen") or 0)
        total = int(c.get("total") or c.get("messages") or 0)
        actual[nombre] = unseen
        if nombre not in previo:
            continue  # primer ciclo con esta carpeta: solo se memoriza
        antes = previo[nombre]
        if unseen > antes:
            con_correo_nuevo += 1
            uid = await _ultimo_sin_leer_en(imap, c.get("imap_name") or nombre)
            resumen = await resumen_correo(imap, uid) if uid else {}
            if db is not None:  # app de escritorio y push, como INBOX (10/11/2026)
                from app.websocket import avisos_subcarpeta

                await avisos_subcarpeta.avisar(
                    db, usuario, nombre, unseen - antes, unseen, uid, resumen
                )
            await redis.publish(
                f"ws:user:{usuario}",
                json.dumps(
                    {
                        "type": "new_mail",
                        "folder": nombre,
                        "unseen": unseen,
                        "total": total,
                        "delta": unseen - antes,
                        "uid": uid,
                        "de": resumen.get("de", ""),
                        "asunto": resumen.get("asunto", ""),
                    }
                ),
            )
        elif unseen != antes:
            await redis.publish(
                f"ws:user:{usuario}",
                json.dumps(
                    {
                        "type": "folder_update",
                        "folder": nombre,
                        "unseen": unseen,
                        "total": total,
                    }
                ),
            )

    if con_correo_nuevo:
        # El listado de carpetas se cachea 45 s: que la barra lateral vea el contador nuevo ya.
        try:
            await redis.delete(f"folders:{usuario}")
        except Exception:
            pass
    try:
        await redis.set(_clave(usuario), json.dumps(actual), ex=TTL_ESTADO_S)
    except Exception:
        pass
    return con_correo_nuevo
