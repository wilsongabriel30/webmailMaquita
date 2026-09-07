"""Correos más grandes del buzón (para liberar espacio).

El Drive muestra el espacio del correo por separado y, para liberarlo, manda a la persona al webmail
(`/webmail/?vista=grandes`): aquí se listan los mensajes que más ocupan en las carpetas principales,
con su tamaño, para que la persona decida qué borrar. Un solo FETCH por carpeta (`UID RFC822.SIZE`
de todo el rango), después las cabeceras solo de los N mayores. Resultado en caché 60 s.
"""

import json
import re

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import get_imap_connection
from app.mail.imap_service import _decode_lines, _parse_fetch_response

router = APIRouter(prefix="/api/mail", tags=["mail-espacio"])

CARPETAS = ("INBOX", "Sent", "Drafts", "Junk", "Trash", "Archive")
_TAM = re.compile(
    r"UID\s+(\d+).*?RFC822\.SIZE\s+(\d+)|RFC822\.SIZE\s+(\d+).*?UID\s+(\d+)"
)


def _tamanos(lineas: list[str]) -> list[tuple[int, int]]:
    """[(uid, bytes)] de un FETCH (UID RFC822.SIZE)."""
    salida = []
    for l in lineas:
        m = _TAM.search(l)
        if not m:
            continue
        if m.group(1):
            salida.append((int(m.group(1)), int(m.group(2))))
        else:
            salida.append((int(m.group(4)), int(m.group(3))))
    return salida


async def _mayores_de(imap, carpeta: str, n: int) -> list[dict]:
    resp = await imap.select(carpeta)
    if resp.result != "OK":
        return []
    total = 0
    for l in _decode_lines(resp.lines):
        m = re.search(r"(\d+)\s+EXISTS", l)
        if m:
            total = int(m.group(1))
    if total == 0:
        return []
    r = await imap.fetch("1:*", "(UID RFC822.SIZE)")
    if r.result != "OK":
        return []
    mayores = sorted(
        _tamanos(_decode_lines(r.lines)), key=lambda x: x[1], reverse=True
    )[:n]
    salida = []
    for uid, tam in mayores:
        r = await imap.uid(
            "fetch",
            str(uid),
            "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] RFC822.SIZE)",
        )
        parseados = (
            _parse_fetch_response(_decode_lines(r.lines)) if r.result == "OK" else []
        )
        d = (
            parseados[0]
            if parseados
            else {"subject": "(sin asunto)", "from": "", "date": None}
        )
        salida.append(
            {
                "folder": carpeta,
                "uid": uid,
                "size": tam,
                "subject": d.get("subject"),
                "from": d.get("from"),
                "date": d.get("date"),
            }
        )
    return salida


@router.get("/grandes")
async def correos_grandes(
    request: Request,
    limit: int = Query(40, ge=5, le=200),
    username: str = Depends(get_current_user),
):
    """Los `limit` mensajes más grandes de todo el buzón (carpetas principales), de mayor a menor."""
    redis = request.app.state.redis
    clave = f"grandes:{username}:{limit}"
    try:
        cache = await redis.get(clave)
        if cache:
            return json.loads(cache)
    except Exception:
        pass
    password = await get_user_password(request, username)
    imap = await get_imap_connection(
        await get_imap_login_user(request, username), password
    )
    try:
        todos: list[dict] = []
        for carpeta in CARPETAS:
            todos += await _mayores_de(imap, carpeta, limit)
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
    todos.sort(key=lambda m: m["size"], reverse=True)
    salida = {
        "mensajes": todos[:limit],
        "total_bytes": sum(m["size"] for m in todos[:limit]),
    }
    try:
        await redis.set(clave, json.dumps(salida), ex=60)
    except Exception:
        pass
    return salida
