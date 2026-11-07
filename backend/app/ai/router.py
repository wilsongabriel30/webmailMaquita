"""
Smart Compose / Reply / Summarize / Subject Suggestion — Maquita Webmail
=========================================================================
Usa el servidor IA de VM 170 (LLM local con GPU P40) para generar
respuestas inteligentes, autocompletado, resumenes y sugerencias de asunto.
"""

import json
import logging
import re
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.ai import alfabeto
from app.ai import estilo_institucional as estilo
from app.ai import idioma, medicion_llm, textos_en
from app.ai import union_palabra as union
from app.ai.contenido_hostil import (
    INSTRUCCION_DATOS,
    bloque_correo,
    json_de_cadenas,
    texto_valido,
)
from app.ai.llm_calidad import config_calidad, config_respaldo
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


# --- Configuracion del servidor IA ---
# URLs permitidas para el proxy IA (whitelist anti-SSRF)
# Hosts permitidos se construyen dinamicamente desde la config
def _get_allowed_ia_hosts():
    from urllib.parse import urlparse

    s = get_settings()
    hosts = {"127.0.0.1", "localhost"}
    parsed = urlparse(s.ollama_url)
    if parsed.hostname:
        hosts.add(parsed.hostname)
    return hosts


IA_TIMEOUT = 45.0

import os as _os

# Contexto institucional PARAMETRIZABLE (el repo NO fija ninguna organizacion):
#  - AI_ORG_CONTEXT: identidad/mision de tu organizacion (frase libre); si no se define,
#    se usa una identidad neutra con ORG_NAME, para no atribuir los correos a otra org.
_AI_ORG_CONTEXT = _os.getenv("AI_ORG_CONTEXT", "").strip()
_AI_ORG_NAME = _os.getenv("ORG_NAME", "tu organizacion").strip()
MAQUITA_CONTEXT = (
    "Contexto: "
    + (
        _AI_ORG_CONTEXT
        or ("Eres el asistente de redaccion de correos de " + _AI_ORG_NAME + ".")
    )
    + " "
    "Trata SIEMPRE al destinatario de USTED (formal, nunca tutees). "
    "Tono profesional, cercano, respetuoso e inclusivo. "
    "NUNCA agregues firma, nombre, cargo, logotipos ni datos de contacto: cada persona ya tiene su firma personalizada. "
    "Si el correo se despide, cierra unicamente con un saludo cordial y variado "
    "(por ejemplo: Saludos cordiales, Un cordial saludo, Reciba un cordial saludo, Quedamos atentos), sin nombre ni firma. "
    "No inventes datos, cifras, fechas, precios ni compromisos que no aparezcan en el texto del usuario. "
)
# El estilo institucional (estilo.instrucciones) lo añade cada función con su alcance:
# reglas largas confunden al modelo pequeño y lo hacen cambiar de idioma (04/11/2026).


async def _get_ia_config():
    """Config de IA ENCHUFABLE. Lee la config central (.env: IA_PROVIDER/IA_BASE_URL/
    IA_MODEL/IA_API_KEY) y, opcionalmente, el override del panel (tabla ai_config).
    Por defecto OpenAI-compatible; adapters finos para ollama/gateway."""
    s = get_settings()
    provider = (s.ia_provider or "openai").lower()
    base = (s.ia_base_url or s.ollama_url or "").rstrip("/")
    api_key = s.ia_api_key
    model = s.ia_model
    timeout = s.ia_timeout or 60
    try:
        from app.database import connect_db

        conn = await connect_db()
        try:
            row = await conn.fetchrow(
                "SELECT provider, base_url, api_key, model FROM ai_config WHERE id = 1 AND enabled = true"
            )
        finally:
            await conn.close()
        if row and (row["base_url"] or row["provider"]):
            provider = (row["provider"] or provider).lower()
            base = (row["base_url"] or base).rstrip("/")
            api_key = row["api_key"] or api_key
            model = row["model"] or model
    except Exception:
        pass  # tabla inexistente / sin conexion -> usar el .env (fail-open)
    if not model:
        logger.warning(
            "IA_MODEL no configurado: define IA_MODEL en .env o activa el panel de IA"
        )
    if provider == "ollama":
        generate_url = f"{base}/api/generate"
        headers = {"Content-Type": "application/json"}
    elif provider in ("gateway", "custom"):
        generate_url = f"{base}/api/v1/ia/generate"
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    else:  # openai-compatible (vLLM, LM Studio, OpenRouter, LocalAI, ...)
        generate_url = f"{base or 'https://api.openai.com'}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    return {
        "provider": provider,
        "base_url": base,
        "api_key": api_key,
        "model": model,
        "generate_url": generate_url,
        "headers": headers,
        "timeout": timeout,
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
    # Idioma del corrector del redactor («es-EC», «en»…): decide si el texto escrito es corto o
    # ambiguo. Si lo escrito es claramente de un idioma, manda lo escrito.
    idioma: Optional[str] = ""


class SmartComposeResponse(BaseModel):
    suggestion: str
    # True: la sugerencia continúa la palabra que la persona dejó a medias y se pega sin espacio.
    continua_palabra: bool = False


class SummarizeRequest(BaseModel):
    message_ids: list[str]
    folder: str = "INBOX"
    # Idioma de la persona (no del correo): el resumen sale en español salvo que pida «en».
    idioma: Optional[str] = ""


class SummarizeResponse(BaseModel):
    summary: str


class SuggestSubjectRequest(BaseModel):
    body: str


class SuggestSubjectResponse(BaseModel):
    suggestions: list[str]


# --- Utilidad: llamar al LLM ---
async def _call_llm(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 800,
    calidad: bool = False,
) -> str:
    """Llama al servidor IA con retry automático.

    `calidad=True` (redactar, resumir, «Conversa con tu correo») usa IA_MODEL_CALIDAD en
    IA_GPU_CALIDAD si está definido; si falla o vuelve vacío, reintenta UNA vez con el modelo
    normal (ver app/ai/llm_calidad.py)."""
    ia = await _get_ia_config()
    ia_cal = config_calidad(ia, get_settings()) if calidad else None
    if not ia_cal:
        return await _generar(ia, prompt, system, temperature, max_tokens)
    inicio = time.monotonic()
    try:
        return await _generar(ia_cal, prompt, system, temperature, max_tokens, 1)
    except HTTPException as e:
        logger.warning(
            "IA_CALIDAD_RESPALDO modelo=%s gpu=%s motivo=%s: se reintenta con %s",
            ia_cal["model"],
            ia_cal["preferir_gpu"],
            e.detail,
            ia.get("model"),
        )
    respaldo = config_respaldo(ia, inicio)
    return await _generar(respaldo, prompt, system, temperature, max_tokens, 1)


async def _generar(
    ia: dict,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    intentos: int = 2,
) -> str:
    """Una petición de generación con la config `ia` (hasta `intentos` veces)."""
    prov = ia["provider"]
    if prov == "ollama":
        payload = {
            "model": ia["model"],
            "prompt": prompt,
            "system": system,
            "stream": False,
            # Modelos «pensantes» (Qwen3 y similares) devuelven el razonamiento en `thinking` y
            # `response` vacío: sin esto, dos intentos vacíos y 502 (informe de Andes, 07/09).
            # Los modelos que no piensan ignoran el campo.
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
    elif prov == "openai":
        payload = {
            "model": ia["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    else:  # gateway / custom
        payload = {
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usar_rag": False,
            "model": ia["model"],
            "preferir_gpu": ia.get("preferir_gpu") or "remota",
        }
    last_error = None

    for intento in range(intentos):  # max 2 intentos
        crono = medicion_llm.Cronometro(ia, intento + 1)
        try:
            async with httpx.AsyncClient(
                timeout=ia.get("timeout") or IA_TIMEOUT
            ) as client:
                resp = await client.post(
                    ia["generate_url"], json=payload, headers=ia["headers"]
                )
                resp.raise_for_status()
                data = resp.json()

                # Error explícito del gateway (ambas GPUs fallaron)
                if "error" in data:
                    crono.anotar("gateway_error", data)
                    logger.warning(
                        f"LLM gateway error (intento {intento+1}): {data['error']}"
                    )
                    last_error = data["error"]
                    continue

                # gateway/ollama: respuesta/response/text/output ; OpenAI: choices[].message.content
                raw_resp = (
                    data.get("respuesta")
                    or data.get("response")
                    or data.get("text")
                    or data.get("output")
                    or ""
                )
                if (
                    not raw_resp
                    and isinstance(data.get("choices"), list)
                    and data["choices"]
                ):
                    raw_resp = data["choices"][0].get("message", {}).get("content", "")

                # Validar respuesta vacía
                if not raw_resp or not raw_resp.strip():
                    crono.anotar("vacia", data)
                    logger.warning(
                        f"LLM respuesta vacia (intento {intento+1}, modelo={data.get('modelo', '?')})"
                    )
                    last_error = "Respuesta vacia del modelo"
                    continue

                # Sanitizar: truncar y eliminar scripts
                import re as _re

                raw_resp = _re.sub(
                    r"<script[^>]*>.*?</script>",
                    "",
                    raw_resp,
                    flags=_re.DOTALL | _re.IGNORECASE,
                )
                raw_resp = raw_resp[:5000]
                crono.anotar("ok", data)
                return raw_resp

        except httpx.TimeoutException:
            crono.anotar("timeout")
            logger.error(f"LLM timeout (intento {intento+1})")
            last_error = "timeout"
        except HTTPException:
            raise
        except Exception as e:
            crono.anotar("error")
            logger.error(f"LLM error (intento {intento+1}): {e}")
            last_error = str(e)

    # Ambos intentos fallaron
    if last_error == "timeout":
        raise HTTPException(
            status_code=504, detail="El servicio de IA no respondio a tiempo"
        )
    raise HTTPException(
        status_code=502, detail="El servicio de IA no pudo generar una respuesta"
    )


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
        cleaned = re.sub(r"^\d+[.\)\-]\s*", "", line).strip().strip("\"'")
        if cleaned and len(cleaned) > 5:
            results.append(cleaned)
    return results[:3] if results else [text.strip()[:200]]


# --- Utilidad: obtener mensaje por UID ---
async def _fetch_message(request: Request, user: str, folder: str, uid: int) -> dict:
    """Obtiene un mensaje completo via IMAP."""
    from app.core.session import get_user_password
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import get_message

    # IMPORTANTE: usar get_user_password() que descifra la contraseña Fernet.
    # NO leer directo de Redis — devuelve el token cifrado, no la contraseña real.
    password = await get_user_password(request, user)

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        msg = await get_message(imap, folder, uid, mark_seen=False)
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
    try:
        msg = await _fetch_message(request, user, body.folder, int(body.message_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"smart-reply: error obteniendo mensaje {body.message_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail="No se pudo obtener el mensaje para generar respuesta",
        )

    subject = msg.get("subject", "(sin asunto)")
    text = (
        msg.get("text_body", "") or msg.get("snippet", "") or msg.get("html_body", "")
    )
    # Si es una invitación de calendario, el text_body puede ser iCal puro
    if not text or text.strip().startswith("BEGIN:VCALENDAR"):
        # Extraer info útil del mensaje de invitación
        text = f"Invitación: {subject}"
    text = text[:1500]
    sender = msg.get("from", "")
    # Se responde en el idioma del correo (inglés o, por defecto, español).
    lengua = idioma.elegir(idioma.detectar(f"{subject}\n{text}"))

    prompt = (
        "Lee el siguiente correo y genera exactamente 3 respuestas DIFERENTES en espanol.\n"
        "Cada respuesta debe:\n"
        "- Ser especifica al contenido del mensaje, NO generica\n"
        "- Tener entre 2 y 5 oraciones\n"
        "- Ser profesional y cordial\n"
        "- Respuesta 1: aceptar o confirmar lo que pide el remitente\n"
        "- Respuesta 2: pedir mas detalles o aclaracion\n"
        "- Respuesta 3: declinar cortesmente o proponer alternativa\n\n"
        + bloque_correo(sender, subject, text)  # [S7-2] el correo es dato delimitado
        + "\n\n"
        "Responde UNICAMENTE con un JSON array de 3 strings. Sin explicaciones, sin markdown.\n"
        'Formato: ["respuesta1", "respuesta2", "respuesta3"]'
    )

    system = (
        MAQUITA_CONTEXT
        + estilo.instrucciones("redaccion")
        + "Generas respuestas de correo contextualizadas basadas en el contenido real del mensaje. "
        "NUNCA generas respuestas genericas como 'Gracias por tu mensaje'. "
        "Respondes SOLO con JSON valido, sin texto adicional." + INSTRUCCION_DATOS
    )
    if lengua == idioma.EN:
        prompt, system = textos_en.smart_reply(sender, subject, text)
        system = (
            textos_en.contexto() + estilo.instrucciones("redaccion", lengua) + system
        )

    raw = await alfabeto.generar(
        lambda t: _call_llm(
            # 700 tokens bastan para 3 respuestas de 2-5 oraciones (antes 1200: más espera, 05/11/2026)
            prompt,
            system=system,
            temperature=t,
            max_tokens=700,
            calidad=True,
        ),
        0.8,
        "smart_reply",
    )
    # [S7-2] Solo se acepta el JSON esperado; cualquier otra cosa se rechaza (reserva contextual)
    suggestions = json_de_cadenas(raw, 3)
    if suggestions is None:
        logger.warning("IA_SALIDA_RECHAZADA funcion=smart_reply user=%s", user)
        suggestions = []
    fuente = f"{sender}\n{subject}\n{text}"
    suggestions = [estilo.institucionalizar(s, fuente) for s in suggestions]
    suggestions = [s for s in suggestions if s]  # sin texto válido: se usa la reserva

    # Asegurar que siempre haya 3 sugerencias
    # Fallbacks contextualizados si el LLM no genero suficientes
    fallbacks = [
        f'Gracias por su correo sobre "{subject}". Lo revisaré y le responderé a la brevedad.',
        f'Recibí su mensaje sobre "{subject}". ¿Podría ampliar los detalles, por favor?',
        "Agradezco la información. Coordinaremos internamente y le confirmaré pronto.",
    ]
    if lengua == idioma.EN:
        fallbacks = textos_en.respuestas_reserva(subject)
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
        raise HTTPException(
            status_code=400, detail="Se requiere al menos 3 caracteres de contexto"
        )

    to_field = body.to or "(destinatario)"
    subject_field = body.subject or "(sin asunto)"

    prompt = (
        "Completa este correo institucional en espanol de forma profesional y breve. "
        "Solo devuelve la continuacion, no repitas lo que ya esta escrito.\n\n"
        f"Para: {to_field}\n"
        f"Asunto: {subject_field}\n"
        f"Texto hasta ahora: {body.context}\n\n"
        "Continuacion:"
    )

    system = (
        MAQUITA_CONTEXT
        + estilo.instrucciones("minimo")
        + "Tu tarea: continuar el correo. Solo devuelves la continuacion del texto, sin repetir lo ya escrito."
    )
    # Idioma: el de lo escrito; si es corto o ambiguo, el del corrector; si no, español.
    lengua = idioma.elegir(idioma.detectar(body.context), body.idioma)
    if lengua == idioma.EN:
        prompt, system = textos_en.smart_compose(
            body.context, body.to or "(recipient)", body.subject or "(no subject)"
        )
        system = textos_en.contexto() + estilo.instrucciones("minimo", lengua) + system

    raw = await alfabeto.generar(
        lambda t: _call_llm(prompt, system=system, temperature=t, max_tokens=64),
        0.6,
        "smart_compose",
    )
    con_espacio = raw[:1].isspace()
    suggestion = raw.strip()

    # Limpiar si el LLM repitio el contexto
    ctx_prefix = body.context.strip().lower()[:30]
    if suggestion.lower().startswith(ctx_prefix):
        resto = suggestion[len(body.context) :]
        con_espacio, suggestion = resto[:1].isspace(), resto.strip()
    # ¿Continúa la palabra a medias («Estimad» + «as»)? (antes: siempre con espacio delante)
    base, continua = union.unir(body.context, suggestion, con_espacio)
    suggestion = estilo.institucionalizar_continuacion(
        body.context, base, f"{body.context}\n{subject_field}", body.to or ""
    )
    continua = union.reevaluar(body.context, base, suggestion, continua)

    return SmartComposeResponse(suggestion=suggestion, continua_palabra=continua)


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
        raise HTTPException(
            status_code=400, detail="Se requiere al menos un message_id"
        )

    # Obtener mensajes (max 10 para no sobrecargar)
    messages_text = []
    for mid in body.message_ids[:10]:
        try:
            msg = await _fetch_message(request, user, body.folder, int(mid))
            sender = msg.get("from", "Desconocido")
            subject = msg.get("subject", "")
            text = (
                msg.get("text_body", "")
                or msg.get("snippet", "")
                or msg.get("html_body", "")
            )[:300]
            # Si es iCal puro, usar asunto como texto
            if not text or text.strip().startswith("BEGIN:VCALENDAR"):
                text = f"Invitación de calendario: {subject}"
            messages_text.append(bloque_correo(sender, subject, text, 300))  # [S7-2]
        except Exception as e:
            logger.warning(f"summarize: no se pudo obtener mensaje {mid}: {e}")
            continue

    if not messages_text:
        raise HTTPException(
            status_code=404, detail="No se pudieron obtener los mensajes"
        )

    thread_content = "\n\n---\n\n".join(messages_text)

    prompt = (
        "Resume este hilo de correos en 2-3 oraciones concisas en espanol. "
        "Incluye los puntos clave y cualquier accion pendiente.\n\n"
        f"{thread_content}\n\n"
        "Resumen:"
    )

    system = (
        MAQUITA_CONTEXT
        + estilo.instrucciones("analisis")
        + "Tu tarea ahora: resumir el hilo de correo de forma concisa en espanol. "
        "Aunque los correos estén en otro idioma, el resumen va en español."
        + INSTRUCCION_DATOS
    )
    # El resumen es para la persona: en su idioma (español por defecto), no en el del correo.
    if idioma.elegir(body.idioma) == idioma.EN:
        prompt, system = textos_en.summarize(thread_content)
        system = textos_en.contexto() + estilo.instrucciones("analisis", "en") + system

    raw = await alfabeto.generar(
        lambda t: _call_llm(
            prompt, system=system, temperature=t, max_tokens=800, calidad=True
        ),
        0.3,
        "summarize",
    )
    resumen = texto_valido(raw)  # [S7-2]
    if resumen is None:
        logger.warning("IA_SALIDA_RECHAZADA funcion=summarize user=%s", user)
        raise HTTPException(
            status_code=502, detail="La IA no devolvio un resumen valido"
        )
    resumen = estilo.institucionalizar(resumen, thread_content, modo="analisis")
    if not resumen:  # todo estaba en otro alfabeto
        raise HTTPException(
            status_code=502, detail="La IA no devolvio un resumen valido"
        )
    return SummarizeResponse(summary=resumen)


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
        raise HTTPException(
            status_code=400, detail="Se requiere al menos 10 caracteres de texto"
        )

    prompt = (
        "Genera exactamente 3 asuntos breves y profesionales en espanol para este correo. "
        "Cada asunto debe tener maximo 60 caracteres.\n\n"
        f"Contenido del correo:\n{body.body[:500]}\n\n"
        "Responde SOLO con un JSON array de 3 strings. Ejemplo:\n"
        '["Asunto 1", "Asunto 2", "Asunto 3"]'
    )

    system = (
        MAQUITA_CONTEXT
        + estilo.instrucciones("minimo")
        + "Tu tarea ahora: sugerir asuntos de correo profesionales en espanol. Solo respondes con JSON."
    )
    en_ingles = (
        idioma.detectar(body.body) == idioma.EN
    )  # asuntos en el idioma del correo
    if en_ingles:
        prompt, system = textos_en.suggest_subject(body.body)
        system = textos_en.contexto() + estilo.instrucciones("minimo", "en") + system

    raw = await alfabeto.generar(
        lambda t: _call_llm(prompt, system=system, temperature=t, max_tokens=200),
        0.7,
        "suggest_subject",
    )
    suggestions = json_de_cadenas(raw, 3) or []  # [S7-2] solo el JSON esperado
    suggestions = [estilo.institucionalizar(s, body.body) for s in suggestions]
    suggestions = [s for s in suggestions if s]

    while len(suggestions) < 2:
        suggestions.append(
            "Important information" if en_ingles else "Informacion importante"
        )

    return SuggestSubjectResponse(suggestions=suggestions[:3])


async def _quien_pregunta(request: Request):
    """(usuario, es_admin) sin exigir sesión: la ruta responde a todos, contando menos.

    No se usa `Depends(get_current_user)` porque eso devolvería 401 a los vigilantes que solo
    quieren saber si el servicio está vivo. Aquí se pregunta y, si no hay sesión, se sigue.
    """
    usuario = None
    try:
        usuario = await get_current_user(request)
    except Exception:
        return None, False
    try:
        from app.auth.dependencies import require_admin

        await require_admin(request)
        return usuario, True
    except Exception:
        return usuario, False


# =====================================================
# HEALTH CHECK
# =====================================================
@router.get("/health")
async def ai_health(request: Request):
    """Verifica que la IA configurada genera texto de verdad, con el adaptador de cada proveedor.

    Antes consultaba `/api/v1/ia/status` y el formato de la pasarela con cualquier proveedor, así
    que con Ollama u OpenAI siempre salía «degraded» aunque funcionaran (informe de Andes, 07/09).

    [N-31] Lo que se cuenta depende de quién pregunta. Sin sesión solo el estado: antes esta
    ruta publicaba en internet los servidores de IA con sus DIRECCIONES INTERNAS y puertos, el
    inventario de modelos de cada uno y cuáles estaban caídos. Para saber si el servicio vive
    basta con «ok» o «degradado»; el plano de la red es de los administradores.
    """
    quien, es_admin = await _quien_pregunta(request)
    try:
        ia = await _get_ia_config()
        detalle = {}
        if ia["provider"] in ("gateway", "custom"):
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{ia['base_url']}/api/v1/ia/status", headers=ia["headers"]
                )
                resp.raise_for_status()
                detalle = resp.json()
        try:
            texto = await _call_llm(
                "Responde solo: OK", system="", temperature=0.1, max_tokens=5
            )
            genera_ok = bool((texto or "").strip())
        except HTTPException:
            genera_ok = False
        estado = "ok" if genera_ok else "degraded"
        if not quien:
            return {"status": estado}
        respuesta = {
            "status": estado,
            "ia_server": "connected",
            "genera_texto": genera_ok,
            "provider": ia["provider"],
            "modelo": ia.get("model", "?"),
        }
        if es_admin:
            respuesta["detail"] = detalle
        return respuesta
    except Exception as e:
        if not quien:
            return {"status": "degraded"}
        # El texto de la excepción puede llevar la dirección del servidor de IA: solo al admin.
        return {
            "status": "degraded",
            "ia_server": "unreachable",
            **({"detail": str(e)} if es_admin else {}),
        }


async def embed_text(text: str) -> list:
    """Hook opcional de embeddings para RAG/grounding (futuro). Fail-open: [] si falla.
    Usa IA_EMBED_MODEL contra el backend (ollama /api/embeddings u OpenAI /v1/embeddings).
    """
    s = get_settings()
    base = (s.ia_base_url or s.ollama_url or "").rstrip("/")
    model = s.ia_embed_model
    if not base or not model:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if (s.ia_provider or "").lower() == "ollama":
                rr = await client.post(
                    f"{base}/api/embeddings",
                    json={"model": model, "prompt": text[:4000]},
                )
                rr.raise_for_status()
                return rr.json().get("embedding", [])
            rr = await client.post(
                f"{base}/v1/embeddings",
                json={"model": model, "input": text[:4000]},
                headers={"Authorization": f"Bearer {s.ia_api_key}"},
            )
            rr.raise_for_status()
            return (rr.json().get("data") or [{}])[0].get("embedding", [])
    except Exception as e:
        logger.warning("embedding (IA_EMBED_MODEL) fallo: %s", e)
        return []
