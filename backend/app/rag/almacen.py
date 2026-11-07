"""Escrituras por lotes en rag_chunks y estado por carpeta (rag_carpetas).

rag_carpetas guarda, por buzón y carpeta, el UIDVALIDITY/UIDNEXT/EXISTS vistos en la última
pasada: si no cambiaron y la carpeta quedó completa, la noche siguiente ni se pide la lista de
UID. Si cambia el UIDVALIDITY, los UID antiguos ya no valen y se reindexa la carpeta entera.
La columna rag_chunks.formato marca con qué versión del contenido se indexó cada correo
(1 = «De | Asunto | fragmento» de antes; 2 = con carpeta, fecha, destinatarios y cuerpo).
"""

import logging

from app.rag import store

logger = logging.getLogger(__name__)
_ESQUEMA_LISTO = False


async def asegurar_esquema(db) -> None:
    """Crea lo que falte. El ALTER solo se lanza si la columna no existe (toma un bloqueo
    exclusivo breve de la tabla; no conviene repetirlo en cada buzón)."""
    global _ESQUEMA_LISTO
    if _ESQUEMA_LISTO:
        return
    await store.ensure_schema(db)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS rag_carpetas (username varchar NOT NULL, folder varchar NOT NULL, "
        "uidvalidity bigint, uidnext bigint, mensajes integer NOT NULL DEFAULT 0, "
        "indexados integer NOT NULL DEFAULT 0, completa boolean NOT NULL DEFAULT false, "
        "formato smallint NOT NULL DEFAULT 0, actualizado timestamptz NOT NULL DEFAULT now(), "
        "PRIMARY KEY (username, folder))"
    )
    tiene = await db.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_name='rag_chunks' AND column_name='formato'"
    )
    if not tiene:
        # Con valor constante PostgreSQL no reescribe la tabla: es instantáneo.
        await db.execute(
            "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS formato smallint NOT NULL DEFAULT 1"
        )
    _ESQUEMA_LISTO = True


async def formatos(db, username: str, folder: str) -> dict[int, int]:
    """UID -> formato de los correos ya indexados de la carpeta."""
    filas = await db.fetch(
        "SELECT msg_uid, formato FROM rag_chunks WHERE username=$1 AND folder=$2",
        username,
        folder,
    )
    salida = {}
    for f in filas:
        try:
            salida[int(f["msg_uid"])] = int(f["formato"] or 1)
        except (TypeError, ValueError):
            continue
    return salida


async def guardar_lote(db, username: str, folder: str, filas: list[tuple]) -> None:
    """filas: (uid, asunto, remitente, contenido, embedding, formato)."""
    if not filas:
        return
    await db.executemany(
        "INSERT INTO rag_chunks (username,folder,msg_uid,subject,sender,content,embedding,formato) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8) ON CONFLICT (username,folder,msg_uid) DO UPDATE SET "
        "subject=EXCLUDED.subject, sender=EXCLUDED.sender, content=EXCLUDED.content, "
        "embedding=EXCLUDED.embedding, formato=EXCLUDED.formato, created_at=now()",
        [
            (
                username,
                folder,
                str(uid),
                asunto,
                remitente,
                contenido,
                str(emb),
                formato,
            )
            for uid, asunto, remitente, contenido, emb, formato in filas
        ],
    )


async def borrar_uids(db, username: str, folder: str, lista_uids) -> int:
    lista = [str(u) for u in lista_uids]
    if not lista:
        return 0
    r = await db.execute(
        "DELETE FROM rag_chunks WHERE username=$1 AND folder=$2 AND msg_uid = ANY($3::varchar[])",
        username,
        folder,
        lista,
    )
    return _filas(r)


async def borrar_carpeta(db, username: str, folder: str) -> int:
    r = await db.execute(
        "DELETE FROM rag_chunks WHERE username=$1 AND folder=$2", username, folder
    )
    await db.execute(
        "DELETE FROM rag_carpetas WHERE username=$1 AND folder=$2", username, folder
    )
    return _filas(r)


async def borrar_ausentes(db, username: str, vigentes: list[str]) -> int:
    """Quita del índice las carpetas que ya no existen o que ahora se excluyen."""
    r = await db.execute(
        "DELETE FROM rag_chunks WHERE username=$1 AND NOT (folder = ANY($2::varchar[]))",
        username,
        vigentes,
    )
    await db.execute(
        "DELETE FROM rag_carpetas WHERE username=$1 AND NOT (folder = ANY($2::varchar[]))",
        username,
        vigentes,
    )
    return _filas(r)


async def contar(db, username: str, folder: str) -> int:
    return int(
        await db.fetchval(
            "SELECT count(*) FROM rag_chunks WHERE username=$1 AND folder=$2",
            username,
            folder,
        )
        or 0
    )


async def estado(db, username: str, folder: str) -> dict | None:
    f = await db.fetchrow(
        "SELECT uidvalidity, uidnext, mensajes, indexados, completa, formato FROM rag_carpetas "
        "WHERE username=$1 AND folder=$2",
        username,
        folder,
    )
    return dict(f) if f else None


async def guardar_estado(
    db,
    username: str,
    folder: str,
    info: dict,
    indexados: int,
    completa: bool,
    formato: int,
) -> None:
    await db.execute(
        "INSERT INTO rag_carpetas (username,folder,uidvalidity,uidnext,mensajes,indexados,completa,formato,actualizado) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now()) ON CONFLICT (username,folder) DO UPDATE SET "
        "uidvalidity=EXCLUDED.uidvalidity, uidnext=EXCLUDED.uidnext, mensajes=EXCLUDED.mensajes, "
        "indexados=EXCLUDED.indexados, completa=EXCLUDED.completa, formato=EXCLUDED.formato, actualizado=now()",
        username,
        folder,
        info.get("uidvalidity"),
        info.get("uidnext"),
        int(info.get("mensajes") or 0),
        indexados,
        completa,
        formato,
    )


async def resumen(db, username: str) -> dict:
    """Para el panel: correos del buzón (según la última pasada) y carpetas completas."""
    try:
        f = await db.fetchrow(
            "SELECT coalesce(sum(mensajes),0) AS mensajes, count(*) AS carpetas, "
            "count(*) FILTER (WHERE completa) AS completas FROM rag_carpetas WHERE username=$1",
            username,
        )
    except Exception:  # tabla aún no creada (antes de la primera indexación)
        return {}
    if not f or not f["carpetas"]:
        return {}
    return {
        "en_buzon": int(f["mensajes"]),
        "carpetas": int(f["carpetas"]),
        "carpetas_completas": int(f["completas"]),
    }


def _filas(resultado: str) -> int:
    try:
        return int(str(resultado).split()[-1])
    except (ValueError, IndexError):
        return 0
