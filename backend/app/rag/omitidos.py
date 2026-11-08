"""Correos que el índice del asistente decidió NO indexar (spam, servidor, publicidad; 08/11/2026).

Se anotan por buzón, carpeta y UID para que la pasada siguiente no vuelva a leerlos del IMAP:
`formatos()` los devuelve con el formato vigente y `plan.pendientes` los da por hechos. Si el
correo desaparece de la carpeta (se borró o se movió), la fila se quita igual que en rag_chunks.
"""

from app.rag import texto

_LISTO = False


async def asegurar(db) -> None:
    global _LISTO
    if _LISTO or db is None:
        return
    await db.execute(
        "CREATE TABLE IF NOT EXISTS rag_omitidos (username varchar NOT NULL, folder varchar NOT NULL, "
        "msg_uid varchar NOT NULL, motivo varchar NOT NULL, formato smallint NOT NULL DEFAULT 0, "
        "creado timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (username, folder, msg_uid))"
    )
    _LISTO = True


async def guardar(db, username: str, folder: str, lista) -> None:
    """lista: [(uid, motivo)]."""
    if not lista or db is None:
        return
    await db.executemany(
        "INSERT INTO rag_omitidos (username, folder, msg_uid, motivo, formato) VALUES ($1,$2,$3,$4,$5) "
        "ON CONFLICT (username, folder, msg_uid) DO UPDATE SET motivo=EXCLUDED.motivo, formato=EXCLUDED.formato, creado=now()",
        [(username, folder, str(uid), motivo, texto.FORMATO) for uid, motivo in lista],
    )


async def formatos(db, username: str, folder: str) -> dict[int, int]:
    """UID -> formato de los correos omitidos de la carpeta (para darlos por hechos)."""
    if db is None:  # pruebas sin base de datos
        return {}
    filas = await db.fetch(
        "SELECT msg_uid, formato FROM rag_omitidos WHERE username=$1 AND folder=$2",
        username,
        folder,
    )
    salida = {}
    for f in filas:
        try:
            salida[int(f["msg_uid"])] = int(f["formato"] or 0)
        except (TypeError, ValueError):
            continue
    return salida


async def borrar_uids(db, username: str, folder: str, lista_uids) -> None:
    if not lista_uids or db is None:
        return
    await db.execute(
        "DELETE FROM rag_omitidos WHERE username=$1 AND folder=$2 AND msg_uid = ANY($3::varchar[])",
        username,
        folder,
        [str(u) for u in lista_uids],
    )


async def borrar_carpeta(db, username: str, folder: str) -> None:
    if db is None:
        return
    await db.execute(
        "DELETE FROM rag_omitidos WHERE username=$1 AND folder=$2", username, folder
    )


async def borrar_ausentes(db, username: str, vigentes: list[str]) -> None:
    if db is None:
        return
    await db.execute(
        "DELETE FROM rag_omitidos WHERE username=$1 AND NOT (folder = ANY($2::varchar[]))",
        username,
        vigentes,
    )


async def resumen(db, username: str) -> dict[str, int]:
    """Cuántos correos se dejaron fuera y por qué (para el panel y los informes)."""
    try:
        filas = await db.fetch(
            "SELECT motivo, count(*) AS n FROM rag_omitidos WHERE username=$1 GROUP BY motivo",
            username,
        )
        return {str(f["motivo"]): int(f["n"]) for f in filas}
    except Exception:
        return {}
