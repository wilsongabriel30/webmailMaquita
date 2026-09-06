"""API RAG del webmail — 'pregúntale a tu correo' para el usuario logueado. Gated por dominio."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.rag import config as rag_config
from app.rag import store
from app.rag.ask import ask as rag_ask
from app.rag.ingest import ingest_user

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _db(r: Request):
    return r.app.state.db_pool


class AskReq(BaseModel):
    question: str


@router.get("/status")
async def status(request: Request):
    user = await get_current_user(request)
    db = _db(request)
    return {
        "enabled": await rag_config.domain_enabled(db, user),
        "indexed": await store.count(db, user),
    }


@router.post("/ask")
async def ask_ep(request: Request, body: AskReq):
    user = await get_current_user(request)
    return await rag_ask(_db(request), user, (body.question or "").strip()[:500])


@router.post("/sync")
async def sync_ep(request: Request):
    user = await get_current_user(request)
    return await ingest_user(_db(request), user)
