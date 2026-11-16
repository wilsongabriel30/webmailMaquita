"""Devolver a su carpeta los correos pospuestos cuya hora ya llegó.

Hasta el 15/11/2026 el restaurador no devolvía nada (informe de Andes, y en Maquita desde junio):

- pedía la contraseña del buzón en una clave de Redis (`user_password:<cuenta>`) que nada escribe, y abría
  Redis sin la contraseña de `REDIS_URL`; siempre salía por «sin contraseña» y el correo se quedaba en
  «Pospuestos» para siempre;
- cuando llegaba a mover algo (al cancelar a mano), movía «el primero» de la carpeta Pospuestos, no el
  correo de esa fila: con dos pospuestos podía volver el equivocado.

Ahora el buzón se abre con el usuario maestro (como las cuentas delegadas) y cada fila recuerda el UID que
el correo tiene dentro de Pospuestos (`snoozed_uid`). Las filas antiguas, sin ese dato, se resuelven
comparando remitente y asunto; si no hay una única coincidencia no se toca nada y se deja constancia.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("maquita.webmail.pospuestos")

CARPETA = "Snoozed"

DEVUELTO = "devuelto"
YA_NO_ESTABA = "ya_no_estaba"  # la persona lo sacó de Pospuestos por su cuenta
INDETERMINADO = "indeterminado"  # no se puede saber cuál es: no se mueve nada
SIN_ACCESO = "sin_acceso"


def _texto(valor) -> str:
    return " ".join((valor or "").split()).strip().lower()


def datos_de_cabecera(h) -> tuple[int, str, str]:
    """(uid, asunto, remitente) de lo que devuelve `fetch_message_headers` (objeto o diccionario)."""
    if isinstance(h, dict):
        if h.get("raw_headers"):
            from app.mail.parsers.mime_parser import parse_headers

            nm = parse_headers(h["raw_headers"], uid=h.get("uid", 0))
            return (
                int(nm.uid or h.get("uid", 0) or 0),
                nm.subject or "",
                nm.from_addr or "",
            )
        return (
            int(h.get("uid", 0) or 0),
            h.get("subject", "") or "",
            h.get("from", "") or h.get("from_addr", "") or "",
        )
    return (
        int(getattr(h, "uid", 0) or 0),
        getattr(h, "subject", "") or "",
        getattr(h, "from_addr", "") or "",
    )


def elegir_uid(
    snoozed_uid: int | None,
    asunto: str,
    remitente: str,
    en_carpeta: list[tuple[int, str, str]],
) -> tuple[str, int | None]:
    """Decide qué correo de Pospuestos corresponde a una fila. Devuelve (resultado, uid).

    `en_carpeta` es la lista (uid, asunto, remitente) de lo que hay ahora en Pospuestos.
    """
    uids = [u for u, _, _ in en_carpeta]
    if snoozed_uid:
        return (DEVUELTO, snoozed_uid) if snoozed_uid in uids else (YA_NO_ESTABA, None)
    if not uids:
        return YA_NO_ESTABA, None
    # Fila antigua, sin UID: remitente y asunto deben señalar un único correo. La tabla guarda el
    # asunto recortado a 500 caracteres y el remitente a 255: se compara con el mismo recorte.
    a, r = _texto(asunto[:500]), _texto(remitente[:255])
    iguales = [
        u for u, s, f in en_carpeta if _texto(s[:500]) == a and _texto(f[:255]) == r
    ]
    if len(iguales) == 1:
        return DEVUELTO, iguales[0]
    # Ninguna o varias coincidencias: no se adivina. El correo sigue en Pospuestos, a la vista de la persona.
    return INDETERMINADO, None


async def _lo_que_hay(imap) -> list[tuple[int, str, str]]:
    from app.mail.clients.imap_client import fetch_message_headers

    resp = await imap.select(CARPETA)
    if resp.result != "OK":
        return []
    busqueda = await imap.uid_search("ALL")
    uids: list[int] = []
    if busqueda.result == "OK":
        for linea in busqueda.lines:
            s = linea.decode() if isinstance(linea, bytes) else linea
            if "completed" not in s.lower():
                uids.extend(int(x) for x in s.split() if x.isdigit())
    if not uids:
        return []
    cabeceras = await fetch_message_headers(imap, uids)
    hallados = {d[0]: d for d in (datos_de_cabecera(h) for h in cabeceras or [])}
    # Un correo cuya cabecera no se pudo leer sigue contando como presente (sin asunto ni remitente).
    return [hallados.get(u, (u, "", "")) for u in uids]


async def devolver(imap, fila) -> str:
    """Devuelve a su carpeta el correo de una fila de `snoozed_emails`, con el buzón ya abierto."""
    from app.mail.clients.imap_client import uid_bulk_action

    resultado, uid = elegir_uid(
        fila["snoozed_uid"],
        fila["subject"] or "",
        fila["from_addr"] or "",
        await _lo_que_hay(imap),
    )
    if resultado != DEVUELTO:
        return resultado
    movido = await uid_bulk_action(
        imap, CARPETA, [uid], "move", fila["original_folder"]
    )
    if not movido:
        # La carpeta de origen pudo desaparecer: a la bandeja de entrada antes que dejarlo escondido.
        movido = await uid_bulk_action(imap, CARPETA, [uid], "move", "INBOX")
    return DEVUELTO if movido else SIN_ACCESO


async def abrir_buzon_del_dueno(owner: str):
    """Conexión IMAP al buzón con el usuario maestro; None si la instalación no lo tiene."""
    from app.config import get_settings
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.cuentas_delegadas import credenciales_maestras

    settings = get_settings()
    if not settings.master_password:
        return None
    usuario, clave = credenciales_maestras(owner, settings)
    return await get_imap_connection(usuario, clave)


# `snooze_until` se guarda en UTC sin zona: se compara con la hora UTC, sea cual sea la zona de la base.
_CONSULTA = """SELECT id, owner, original_folder, snoozed_uid, subject, from_addr
                 FROM snoozed_emails
                WHERE snooze_until <= (NOW() AT TIME ZONE 'UTC') AND restored = FALSE"""


async def restaurar_vencidos(db, owner: str | None = None, imap=None) -> dict[str, int]:
    """Una vuelta del restaurador. Con `owner` e `imap`, solo lo de esa persona con su propia sesión."""
    if owner:
        filas = await db.fetch(_CONSULTA + " AND owner = $1 ORDER BY id", owner)
    else:
        filas = await db.fetch(_CONSULTA + " ORDER BY owner, id")
    cuenta: dict[str, int] = {}
    por_dueno: dict[str, list] = {}
    for f in filas:
        por_dueno.setdefault(f["owner"], []).append(f)
    for dueno, suyas in por_dueno.items():
        conexion, propia = imap, False
        try:
            if conexion is None:
                conexion, propia = await abrir_buzon_del_dueno(dueno), True
            if conexion is None:
                cuenta[SIN_ACCESO] = cuenta.get(SIN_ACCESO, 0) + len(suyas)
                continue
            for f in suyas:
                resultado = await devolver(conexion, f)
                cuenta[resultado] = cuenta.get(resultado, 0) + 1
                if resultado in (DEVUELTO, YA_NO_ESTABA):
                    await db.execute(
                        "UPDATE snoozed_emails SET restored = TRUE WHERE id = $1",
                        f["id"],
                    )
                    logger.info("Pospuesto %d de %s: %s", f["id"], dueno, resultado)
                else:
                    # Se reintenta cada minuto: en nivel de depuración para no llenar el registro.
                    logger.debug("Pospuesto %d de %s: %s", f["id"], dueno, resultado)
        except Exception as e:
            cuenta[SIN_ACCESO] = cuenta.get(SIN_ACCESO, 0) + 1
            logger.error("Pospuestos de %s: no se pudo abrir o mover: %s", dueno, e)
        finally:
            if propia and conexion is not None:
                try:
                    await conexion.logout()
                except Exception:
                    pass
    return cuenta
