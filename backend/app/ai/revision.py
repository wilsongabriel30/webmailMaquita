"""Revisión del borrador con la IA de la instalación: `POST /api/ai/review` (botón «Editor» del redactor).

El botón llamaba a `/api/ia/review`, que solo existe donde nginx publica una pasarela de IA externa; en las
demás instalaciones respondía 404 con o sin IA configurada (informe de Andes, 15/11/2026). Esta ruta usa
la misma IA configurable que el resto de `/api/ai/*` (`.env` o panel), sin depender de esa pasarela.

Devuelve una nota del 1 al 10, una valoración, sugerencias y, si el texto es corto, la versión corregida.
Sin IA configurada responde 503 con un motivo claro, sin llamar a ningún modelo.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.ai import alfabeto
from app.ai import estilo_institucional as estilo
from app.ai.disponibilidad import hay_modelo
from app.ai.revision_texto import instrucciones, leer_revision, pide_corregido
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

MINIMO_CARACTERES = 10


class RevisionRequest(BaseModel):
    text: str
    subject: Optional[str] = ""


class RevisionResponse(BaseModel):
    score: int
    feedback: str
    suggestions: list[str]
    corrected_text: Optional[str] = None


@router.post("/review", response_model=RevisionResponse)
async def revisar_borrador(
    body: RevisionRequest, user: str = Depends(get_current_user)
):
    from app.ai.router import MAQUITA_CONTEXT, _call_llm, _get_ia_config

    texto = (body.text or "").strip()
    if len(texto) < MINIMO_CARACTERES:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren al menos {MINIMO_CARACTERES} caracteres de texto",
        )
    if not hay_modelo(await _get_ia_config()):
        raise HTTPException(
            status_code=503, detail="No hay un asistente de IA configurado"
        )

    peticion, sistema = instrucciones(texto, body.subject or "")
    con_corregido = pide_corregido(texto)
    raw = await alfabeto.generar(
        lambda t: _call_llm(
            peticion,
            system=MAQUITA_CONTEXT + sistema,
            temperature=t,
            max_tokens=1500 if con_corregido else 500,
            calidad=True,
        ),
        0.2,
        "review",
    )
    revision = leer_revision(raw, con_corregido)
    if revision is None:
        logger.warning("IA_SALIDA_RECHAZADA funcion=review user=%s", user)
        raise HTTPException(
            status_code=502, detail="La IA no devolvió una revisión válida"
        )
    if revision["corrected_text"]:
        revision["corrected_text"] = (
            estilo.institucionalizar(revision["corrected_text"], texto) or None
        )
    return RevisionResponse(**revision)
