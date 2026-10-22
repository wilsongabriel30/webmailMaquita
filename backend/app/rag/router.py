"""API RAG del webmail — 'pregúntale a tu correo' para el usuario logueado. Gated por dominio."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.rag import config as rag_config
from app.rag import ingest, store
from app.rag.ask import ask as rag_ask

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _db(r: Request):
    return r.app.state.db_pool


def _redis(r: Request):
    return getattr(r.app.state, "redis", None)


class AskReq(BaseModel):
    question: str


@router.get("/status")
async def status(request: Request):
    user = await get_current_user(request)
    db = _db(request)
    return {
        "enabled": await rag_config.domain_enabled(db, user),
        "indexed": await store.count(db, user),
        # Progreso de la sincronización en segundo plano (ver ingest.lanzar_en_segundo_plano)
        "sync": await ingest.progreso_compartido(user, _redis(request)),
    }


@router.post("/ask")
async def ask_ep(request: Request, body: AskReq):
    user = await get_current_user(request)
    return await rag_ask(_db(request), user, (body.question or "").strip()[:500])


@router.post("/sync")
async def sync_ep(request: Request):
    """Arranca la sincronización en segundo plano y responde al instante.

    Antes esperaba a indexar hasta 3000 correos en la misma petición: superaba el tiempo
    de espera del proxy y del IMAP y la pantalla recibía un 500 sin explicación. La pantalla
    consulta /status cada pocos segundos para mostrar el avance.
    """
    user = await get_current_user(request)
    db = _db(request)
    if not await rag_config.domain_enabled(db, user):
        return {
            "started": False,
            "error": "El asistente no está habilitado para tu dominio.",
        }
    redis = _redis(request)
    started = await ingest.lanzar_en_segundo_plano(db, user, redis)
    return {"started": started, "sync": await ingest.progreso_compartido(user, redis)}
