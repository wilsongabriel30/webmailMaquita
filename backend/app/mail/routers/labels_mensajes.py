"""Listado de correos por etiqueta con resúmenes (05/11/2026).

GET /api/mail/labels/{id}/mensajes?page&per_page -> {label, total, messages: MessageSummary[]}

La vista «Etiqueta: X» de la barra lateral lo prefiere frente a /labels/{id}/messages (que solo
devuelve carpeta+uid y obligaba al navegador a pedir cada resumen uno a uno). Aquí se agrupan las
asignaciones de la página por carpeta real, se seleccionan en IMAP y se obtienen los resúmenes con
las mismas funciones que el listado normal, devolviendo en cada uno su `folder` real.
Los UIDs que ya no existen en IMAP (correo borrado o movido) se omiten y se MARCAN como faltantes
(`faltante_desde`, 09/11/2026) solo si la carpeta respondió bien; `total` cuenta únicamente las vigentes y
la página se rellena con las siguientes asignaciones para no quedar corta. NO se borran aquí: un fallo
pasajero de IMAP las borraría sin motivo; las purga `services/etiquetas_huerfanas.py` tras 7 días.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import _quote_folder, fetch_message_headers
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.parsers.mime_parser import parse_headers
from app.mail.services.etiquetas_faltantes import (
    contar_vigentes,
    faltantes_de_pagina,
    marcar_faltantes,
)
from app.mail.services.message_service import _summary_from_normalized

router = APIRouter(prefix="/api/mail", tags=["mail-labels"])
log = logging.getLogger("maquita.webmail.etiquetas")


async def _resumenes_de_carpeta(
    imap, carpeta: str, uids: list[int]
) -> list[dict] | None:
    """Resúmenes de esos uids; None si la carpeta no se pudo seleccionar (no se marca nada)."""
    resp = await imap.select(_quote_folder(carpeta))
    if resp.result != "OK":
        log.warning(
            "etiquetas: carpeta %s no seleccionable, se omiten %d correos",
            carpeta,
            len(uids),
        )
        return None
    salida = []
    for raw in await fetch_message_headers(imap, uids):
        n = parse_headers(
            raw["raw_headers"], uid=raw["uid"], flags=raw["flags"], size=raw["size"]
        )
        resumen = _summary_from_normalized(n, carpeta)
        if raw.get("snippet"):
            resumen["snippet"] = raw["snippet"]
        if raw.get("has_attachments"):
            resumen["has_attachments"] = True
        resumen["received_date"] = raw.get("internal_date")
        salida.append(resumen)
    return salida


@router.get("/labels/{label_id}/mensajes")
async def mensajes_por_etiqueta(
    label_id: int,
    request: Request,
    page: int = 1,
    per_page: int = 50,
    username: str = Depends(get_current_user),
):
    page = max(page, 1)
    per_page = max(1, min(per_page, 300))
    db = request.app.state.db_pool
    lbl = await db.fetchrow(
        "SELECT id, name, color FROM user_labels WHERE id = $1 AND owner = $2",
        label_id,
        username,
    )
    if not lbl:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    filas = await _asignaciones(db, label_id, username, per_page, (page - 1) * per_page)
    mensajes: list[dict] = []
    if filas:
        password = await get_user_password(request, username)
        login_user = await get_imap_login_user(request, username)
        async with get_pooled_imap(login_user, password) as imap:
            mensajes, faltan = await _resolver(imap, filas)
            await marcar_faltantes(db, username, label_id, faltan)
            # Relleno: si faltaron correos en esta página, se traen las siguientes asignaciones
            # (una sola vez) para que la página no salga corta.
            if faltan and len(mensajes) < per_page:
                extra = await _asignaciones(
                    db,
                    label_id,
                    username,
                    len(faltan),
                    (page - 1) * per_page + len(filas),
                )
                if extra:
                    mas, faltan2 = await _resolver(imap, extra)
                    await marcar_faltantes(db, username, label_id, faltan2)
                    filas = filas + extra
                    mensajes.extend(mas)

    # Mismo orden que las asignaciones (más reciente primero); los que IMAP ya no tiene no aparecen.
    orden = {(f["folder"], f["message_uid"]): i for i, f in enumerate(filas)}
    mensajes.sort(key=lambda m: orden.get((m["folder"], m["uid"]), 999999))
    total = await contar_vigentes(db, username, label_id)
    return {
        "label": {"id": lbl["id"], "name": lbl["name"], "color": lbl["color"]},
        "total": total,
        "page": page,
        "per_page": per_page,
        "messages": mensajes,
    }


async def _asignaciones(
    db, label_id: int, username: str, limite: int, desplazamiento: int
):
    return await db.fetch(
        """SELECT folder, message_uid FROM message_labels
           WHERE label_id = $1 AND owner = $2 AND faltante_desde IS NULL
           ORDER BY created_at DESC, id DESC LIMIT $3 OFFSET $4""",
        label_id,
        username,
        limite,
        desplazamiento,
    )


async def _resolver(imap, filas) -> tuple[list[dict], list[tuple[str, int]]]:
    """Pide a IMAP los resúmenes de las asignaciones; devuelve (resúmenes, (carpeta, uid) faltantes)."""
    por_carpeta: dict[str, list[int]] = defaultdict(list)
    for f in filas:
        por_carpeta[f["folder"]].append(f["message_uid"])
    mensajes: list[dict] = []
    devueltos: dict[str, set[int]] = {}
    for carpeta, uids in por_carpeta.items():
        resumenes = await _resumenes_de_carpeta(imap, carpeta, uids)
        if resumenes is None:
            continue  # carpeta no consultable: no se marca nada de ella
        devueltos[carpeta] = {m["uid"] for m in resumenes}
        mensajes.extend(resumenes)
    return mensajes, faltantes_de_pagina(por_carpeta, devueltos)
