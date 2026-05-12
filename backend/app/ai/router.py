"""
Smart Compose / Reply / Summarize / Subject Suggestion — Maquita Webmail
=========================================================================
Usa el servidor IA de VM 170 (LLM local con GPU P40) para generar
respuestas inteligentes, autocompletado, resumenes y sugerencias de asunto.
"""

import json
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

# --- Configuracion del servidor IA (VM 170) ---
# URLs permitidas para el proxy IA (whitelist anti-SSRF)
_ALLOWED_IA_HOSTS = frozenset({"10.16.0.170", "127.0.0.1", "localhost"})
IA_TIMEOUT = 45.0


def _get_ia_config():
    """Obtener config IA con validación de URL (anti-SSRF)."""
    from urllib.parse import urlparse
    s = get_settings()
    parsed = urlparse(s.ollama_url)
    if parsed.hostname not in _ALLOWED_IA_HOSTS:
        raise ValueError(f"URL de IA no permitida: {s.ollama_url}")
    base = s.ollama_url.rstrip("/")
    return {
        "base_url": base,
        "generate_url": f"{base}/api/v1/ia/generate",
        "headers": {"X-API-Key": s.ia_api_key, "Content-Type": "application/json"},
    }


# --- Schemas de request/response ---
class SmartReplyRequest(BaseModel):
    message_id: str
    folder: str = "INBOX"

class SmartReplyResponse(BaseModel):
    suggestions: list[str]

class SmartComposeRequest(BaseModel):
    context: str
    subject: Optional[str] = ""
    to: Optional[str] = ""

class SmartComposeResponse(BaseModel):
    suggestion: str

class SummarizeRequest(BaseModel):
    message_ids: list[str]
    folder: str = "INBOX"

class SummarizeResponse(BaseModel):
    summary: str

class SuggestSubjectRequest(BaseModel):
    body: str

class SuggestSubjectResponse(BaseModel):
    suggestions: list[str]


# --- Utilidad: llamar al LLM ---
async def _call_llm(prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 800) -> str:
    """Llama al endpoint /api/v1/ia/generate del servidor IA."""
    payload = {
        "prompt": prompt,
        "system": system,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "usar_rag": False,
        "preferir_gpu": "local",
    }
    try:
        ia = _get_ia_config()
        async with httpx.AsyncClient(timeout=IA_TIMEOUT) as client:
            resp = await client.post(ia["generate_url"], json=payload, headers=ia["headers"])
            resp.raise_for_status()
            data = resp.json()
            # El campo puede ser "response", "text" o "output" segun la API
            raw_resp = data.get("respuesta", data.get("response", data.get("text", data.get("output", ""))))
            # Sanitizar respuesta: truncar a 5000 chars, eliminar tags HTML potenciales
            import re as _re
            if raw_resp:
                raw_resp = _re.sub(r'<script[^>]*>.*?</script>', '', raw_resp, flags=_re.DOTALL | _re.IGNORECASE)
                raw_resp = raw_resp[:5000]
            return raw_resp
    except httpx.TimeoutException:
        logger.error("LLM timeout")
        raise HTTPException(status_code=504, detail="El servicio de IA no respondio a tiempo")
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail="Error al comunicarse con el servicio de IA")


def _extract_json_array(text: str) -> list[str]:
    """Intenta extraer un JSON array de strings del texto del LLM."""
    # Buscar un JSON array en el texto
    match = re.search(r'\[\s*".*?"\s*(?:,\s*".*?"\s*)*\]', text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
    # Fallback: separar por lineas numeradas
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    results = []
    for line in lines:
        cleaned = re.sub(r"^\d+[.\)\-]\s*", "", line).strip().strip('"\'')
        if cleaned and len(cleaned) > 5:
            results.append(cleaned)
    return results[:3] if results else [text.strip()[:200]]


# --- Utilidad: obtener mensaje por UID ---
async def _fetch_message(request: Request, user: str, folder: str, uid: int) -> dict:
    """Obtiene un mensaje completo via IMAP."""
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import get_message

    redis = request.app.state.redis
    password = await redis.get(f"imap_pass:{user}")
    if not password:
        raise HTTPException(status_code=401, detail="Sesion IMAP expirada")

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        msg = await get_message(imap, folder, uid)
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        return msg
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


# =====================================================
# 1. SMART REPLY — Genera 3 respuestas sugeridas
# =====================================================
@router.post("/smart-reply", response_model=SmartReplyResponse)
async def smart_reply(
    body: SmartReplyRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Genera 3 respuestas breves y profesionales para un correo."""
    msg = await _fetch_message(request, user, body.folder, int(body.message_id))

    subject = msg.get("subject", "(sin asunto)")
    text = msg.get("text_body", "") or msg.get("snippet", "")
    text = text[:1500]
    sender = msg.get("from", "")

    prompt = (
        "Lee el siguiente correo y genera exactamente 3 respuestas DIFERENTES en espanol.\n"
        "Cada respuesta debe:\n"
        "- Ser especifica al contenido del mensaje, NO generica\n"
        "- Tener entre 2 y 5 oraciones\n"
        "- Ser profesional y cordial\n"
        "- Respuesta 1: aceptar o confirmar lo que pide el remitente\n"
        "- Respuesta 2: pedir mas detalles o aclaracion\n"
        "- Respuesta 3: declinar cortesmente o proponer alternativa\n\n"
        f"De: {sender}\n"
        f"Asunto: {subject}\n"
        f"Mensaje:\n{text}\n\n"
        'Responde UNICAMENTE con un JSON array de 3 strings. Sin explicaciones, sin markdown.\n'
        'Formato: ["respuesta1", "respuesta2", "respuesta3"]'
    )

    system = (
        "Eres un asistente experto en redaccion de correos empresariales en espanol. "
        "Generas respuestas contextualizadas basadas en el contenido real del mensaje. "
        "NUNCA generas respuestas genericas como 'Gracias por tu mensaje'. "
        "Respondes SOLO con JSON valido, sin texto adicional."
    )

    raw = await _call_llm(prompt, system=system, temperature=0.8, max_tokens=1200)
    suggestions = _extract_json_array(raw)

    # Asegurar que siempre haya 3 sugerencias
    # Fallbacks contextualizados si el LLM no genero suficientes
    fallbacks = [
        f"Gracias por tu correo sobre \"{subject}\". Lo revisare y te respondo a la brevedad.",
        f"Recibi tu mensaje sobre \"{subject}\". Podrias ampliar los detalles?",
        f"Agradezco la informacion. Coordinaremos internamente y te confirmo pronto.",
    ]
    fb_idx = 0
    while len(suggestions) < 3:
        suggestions.append(fallbacks[fb_idx % len(fallbacks)])
        fb_idx += 1

    return SmartReplyResponse(suggestions=suggestions[:3])


# =====================================================
# 2. SMART COMPOSE — Autocompletado de texto
# =====================================================
@router.post("/smart-compose", response_model=SmartComposeResponse)
async def smart_compose(
    body: SmartComposeRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Genera una continuacion sugerida del texto que el usuario esta escribiendo."""
    if not body.context or len(body.context.strip()) < 3:
        raise HTTPException(status_code=400, detail="Se requiere al menos 3 caracteres de contexto")

    to_field = body.to or "(destinatario)"
    subject_field = body.subject or "(sin asunto)"

    prompt = (
        "Completa este correo empresarial en espanol de forma profesional y breve. "
        "Solo devuelve la continuacion, no repitas lo que ya esta escrito.\n\n"
        f"Para: {to_field}\n"
        f"Asunto: {subject_field}\n"
        f"Texto hasta ahora: {body.context}\n\n"
        "Continuacion:"
    )

    system = "Eres un asistente de redaccion de correos empresariales. Solo devuelves la continuacion del texto, sin repetir lo escrito."

    raw = await _call_llm(prompt, system=system, temperature=0.6, max_tokens=200)
    suggestion = raw.strip()

    # Limpiar si el LLM repitio el contexto
    ctx_prefix = body.context.strip().lower()[:30]
    if suggestion.lower().startswith(ctx_prefix):
        suggestion = suggestion[len(body.context):].strip()

    return SmartComposeResponse(suggestion=suggestion)


# =====================================================
# 3. SUMMARIZE — Resumen de hilo de correos
# =====================================================
@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_thread(
    body: SummarizeRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Resume un hilo de correos en 2-3 oraciones."""
    if not body.message_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un message_id")

    # Obtener mensajes (max 10 para no sobrecargar)
    messages_text = []
    for mid in body.message_ids[:10]:
        try:
            msg = await _fetch_message(request, user, body.folder, int(mid))
            sender = msg.get("from", "Desconocido")
            subject = msg.get("subject", "")
            text = (msg.get("text_body", "") or msg.get("snippet", ""))[:300]
            messages_text.append(f"De: {sender}\nAsunto: {subject}\n{text}")
        except Exception:
            continue

    if not messages_text:
        raise HTTPException(status_code=404, detail="No se pudieron obtener los mensajes")

    thread_content = "\n\n---\n\n".join(messages_text)

    prompt = (
        "Resume este hilo de correos en 2-3 oraciones concisas en espanol. "
        "Incluye los puntos clave y cualquier accion pendiente.\n\n"
        f"{thread_content}\n\n"
        "Resumen:"
    )

    system = "Eres un asistente que resume hilos de correo de forma concisa en espanol."

    raw = await _call_llm(prompt, system=system, temperature=0.3, max_tokens=800)
    logger.info(f"Summarize LLM response: {repr(raw[:200])}")
    return SummarizeResponse(summary=raw.strip())


# =====================================================
# 4. SUGGEST SUBJECT — Sugerencias de asunto
# =====================================================
@router.post("/suggest-subject", response_model=SuggestSubjectResponse)
async def suggest_subject(
    body: SuggestSubjectRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Sugiere 2-3 asuntos apropiados para el cuerpo del correo."""
    if not body.body or len(body.body.strip()) < 10:
        raise HTTPException(status_code=400, detail="Se requiere al menos 10 caracteres de texto")

    prompt = (
        "Genera exactamente 3 asuntos breves y profesionales en espanol para este correo. "
        "Cada asunto debe tener maximo 60 caracteres.\n\n"
        f"Contenido del correo:\n{body.body[:500]}\n\n"
        'Responde SOLO con un JSON array de 3 strings. Ejemplo:\n'
        '["Asunto 1", "Asunto 2", "Asunto 3"]'
    )

    system = "Eres un asistente que sugiere asuntos de correo profesionales en espanol. Solo respondes con JSON."

    raw = await _call_llm(prompt, system=system, temperature=0.7, max_tokens=200)
    suggestions = _extract_json_array(raw)

    while len(suggestions) < 2:
        suggestions.append("Informacion importante")

    return SuggestSubjectResponse(suggestions=suggestions[:3])


# =====================================================
# HEALTH CHECK
# =====================================================
@router.get("/health")
async def ai_health():
    """Verifica conectividad con el servidor IA."""
    try:
        ia = _get_ia_config()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{ia['base_url']}/api/v1/email-assistant/health",
                headers=ia["headers"],
            )
            resp.raise_for_status()
            return {"status": "ok", "ia_server": "connected", "detail": resp.json()}
    except Exception as e:
        return {"status": "degraded", "ia_server": "unreachable", "detail": str(e)}
