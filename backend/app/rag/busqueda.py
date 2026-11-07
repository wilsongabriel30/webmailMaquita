"""Búsqueda de los k correos más parecidos a la pregunta, en todas las carpetas del buzón.

Con millones de filas de 261 buzones, el índice HNSW (rag_chunks_emb_idx) por sí solo
devuelve los ~40 vecinos más cercanos de TODA la tabla y LUEGO filtra por usuario: un buzón
pequeño se quedaba sin resultados. Por eso:
- buzón con pocos correos (<= RAG_BUSQUEDA_EXACTA, 5.000): búsqueda exacta por el índice de
  usuario (el `+ 0` impide que el planificador use el HNSW). Medido en VM 130 (04/11/2026):
  34.000 filas en 0,27 s con la caché caliente pero 47 s en frío (ZFS), por eso el umbral es bajo.
- buzón grande: HNSW con barrido iterativo de pgvector 0.8 (`hnsw.iterative_scan`), que sigue
  buscando hasta reunir k filas del usuario; si aun así faltan, exacta.
"""

import os

from app.rag import store

_COLUMNAS = "subject, sender, content, folder, msg_uid"


async def _exacta(con, username, vec, k):
    return await con.fetch(
        f"SELECT {_COLUMNAS}, 1-(embedding <=> $1::vector) sim FROM rag_chunks "
        "WHERE username=$2 ORDER BY (embedding <=> $1::vector) + 0 LIMIT $3",
        vec,
        username,
        k,
    )


async def _hnsw(con, username, vec, k):
    async with con.transaction():
        try:
            async with con.transaction():  # punto de guardado: pgvector < 0.8 no lo conoce
                await con.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
        except Exception:
            pass
        await con.execute("SET LOCAL hnsw.ef_search = 100")
        try:
            async with con.transaction():
                await con.execute("SET LOCAL hnsw.max_scan_tuples = 50000")
        except Exception:
            pass
        return await con.fetch(
            "WITH c AS MATERIALIZED ("
            f" SELECT {_COLUMNAS}, embedding <=> $1::vector AS d FROM rag_chunks"
            " WHERE username=$2 ORDER BY embedding <=> $1::vector LIMIT $3)"
            f" SELECT {_COLUMNAS}, 1-d AS sim FROM c ORDER BY d",
            vec,
            username,
            k,
        )


async def buscar(db, username, query_emb, k=6):
    vec = str(query_emb)
    umbral = int(os.getenv("RAG_BUSQUEDA_EXACTA", "5000"))
    async with db.acquire() as con:
        if await store.count(con, username) <= umbral:
            return await _exacta(con, username, vec, k)
        filas = await _hnsw(con, username, vec, k)
        if len(filas) < k:
            filas = await _exacta(con, username, vec, k)
        return filas
