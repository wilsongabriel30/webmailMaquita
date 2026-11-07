"""Ingesta RAG incremental de todos los buzones (tarea nocturna rag-indexacion.service).

Uso: python -m app.rag.run [--user correo] [--ask "pregunta" --user correo]
     [--max-minutos N] [--limite N] [--ronda N]

Para que avancen TODOS los buzones y no solo los primeros de la lista, se trabaja por rondas:
en cada ronda cada buzón indexa como mucho `--ronda` correos (RAG_LIMITE_RONDA, 5000; del
más reciente al más antiguo y todas sus carpetas); los que quedan a medias pasan a la
siguiente ronda. Se para al llegar a la hora tope (RAG_MAX_MINUTOS, 570 = 9 h 30 min, antes
del TimeoutStartSec=10h del servicio) o al límite de correos (RAG_LIMITE_EJECUCION, 0 = sin
límite). Lo que falte sigue la noche siguiente: no se pierde nada al cortar.
"""

import asyncio
import json
import logging
import os
import sys
import time

import asyncpg

from app.config import get_settings
from app.database import opciones_pool
from app.rag.ingest import ingest_user
from app.rag.plan import Presupuesto

logger = logging.getLogger("app.rag.run")


def _arg(nombre: str, defecto=None):
    if nombre in sys.argv and sys.argv.index(nombre) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(nombre) + 1]
    return defecto


async def _redis():
    """Redis (si hay) para que el panel vea el avance nocturno y no lance otra a la vez."""
    try:
        from app.redis_client import create_redis

        r = await create_redis()
        await r.ping()
        return r
    except Exception:
        return None


async def _buzones(db) -> list[str]:
    doms = [
        r["domain"]
        for r in await db.fetch("SELECT domain FROM rag_domains WHERE enabled=true")
    ]
    if not doms:
        return []
    return [
        r["username"]
        for r in await db.fetch(
            "SELECT username FROM mailbox WHERE active=true AND split_part(username,'@',2)=ANY($1::text[]) "
            "ORDER BY username",
            doms,
        )
    ]


async def todos(
    db,
    buzones,
    ingesta,
    presupuesto: Presupuesto,
    ronda: int,
    redis=None,
    registrar=print,
) -> dict:
    """Rondas sobre `buzones` hasta terminar o agotar el presupuesto."""
    pendientes, tot, rondas, fallidos = list(buzones), 0, 0, 0
    while pendientes and not presupuesto.agotado():
        rondas += 1
        siguientes = []
        for u in pendientes:
            if presupuesto.agotado():
                siguientes.append(u)
                continue
            try:
                r = await ingesta(
                    db, u, limit=ronda, redis=redis, presupuesto=presupuesto
                )
            except Exception as e:  # un buzón con problemas no detiene a los demás
                fallidos += 1
                registrar(f"  {u}: falló ({e})")
                continue
            tot += r.get("indexed", 0)
            if r.get("embeddings_caidos"):
                registrar("servicio de embeddings caído: se detiene la ejecución")
                return {
                    "rondas": rondas,
                    "indexados": tot,
                    "pendientes": len(pendientes),
                    "fallidos": fallidos,
                    "detenido": "embeddings",
                }
            if r.get("indexed") or r.get("error"):
                registrar(
                    f"  ronda {rondas} {u}: +{r.get('indexed', 0)} (total {r.get('total', 0)}, "
                    f"pendientes {r.get('pendientes', 0)}){' ERROR ' + r['error'] if r.get('error') else ''}"
                )
            # Sigue en la próxima ronda solo si avanzó (si no, es un fallo: queda para mañana)
            if r.get("incompleto") and not r.get("error") and r.get("indexed"):
                siguientes.append(u)
        pendientes = siguientes
    return {
        "rondas": rondas,
        "indexados": tot,
        "pendientes": len(pendientes),
        "fallidos": fallidos,
    }


async def _main():
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s"
    )
    s = get_settings()
    db = await asyncpg.create_pool(
        s.database_url, **opciones_pool(s, min_size=1, max_size=3)
    )
    redis = await _redis()
    try:
        if "--ask" in sys.argv and "--user" in sys.argv:
            from app.rag.ask import ask

            print(
                json.dumps(
                    await ask(db, _arg("--user"), _arg("--ask")), ensure_ascii=False
                )
            )
            return
        minutos = float(_arg("--max-minutos", os.getenv("RAG_MAX_MINUTOS", "570")))
        limite = int(_arg("--limite", os.getenv("RAG_LIMITE_EJECUCION", "0")))
        ronda = int(_arg("--ronda", os.getenv("RAG_LIMITE_RONDA", "5000")))
        presupuesto = Presupuesto.con_minutos(limite, minutos)
        if _arg("--user"):
            r = await ingest_user(
                db, _arg("--user"), limit=limite, redis=redis, presupuesto=presupuesto
            )
            print(json.dumps(r, ensure_ascii=False))
            return
        buzones = await _buzones(db)
        if not buzones:
            print("sin dominios RAG habilitados")
            return
        t0 = time.time()
        print(
            f"{time.strftime('%F %T')} ingesta RAG: {len(buzones)} buzones, tope {minutos:.0f} min, "
            f"ronda {ronda}, límite {limite or 'sin límite'}",
            flush=True,
        )
        r = await todos(
            db,
            buzones,
            ingest_user,
            presupuesto,
            ronda,
            redis,
            registrar=lambda m: print(m, flush=True),
        )
        print(
            f"{time.strftime('%F %T')} ingesta RAG: {len(buzones)} buzones, {r['indexados']} correos "
            f"nuevos en {r['rondas']} rondas y {(time.time() - t0) / 60:.0f} min; "
            f"{r['pendientes']} buzones siguen mañana; {r['fallidos']} fallidos",
            flush=True,
        )
    finally:
        await db.close()
        if redis is not None:
            try:
                await redis.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(_main())
