"""
SpamGuard IA — Detección inteligente de spam, phishing y estafas.
=================================================================
Usa el LLM de VM 170 para analizar patrones sospechosos:
- Publicidad no solicitada
- Phishing y estafas (Nigeria, lotería, herencias)
- Links sospechosos (acortadores, dominios raros)
- Urgencia artificial ("actúa ahora", "tu cuenta será bloqueada")
- Suplantación de identidad (bancos, gobierno)
- Archivos adjuntos sospechosos (.exe, .scr, .zip con contraseña)

Integrado con el flujo de prioridad existente — se ejecuta en paralelo.
"""

import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user, get_user_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail", tags=["spam"])

from app.config import get_settings as _gs
IA_URL = f"{_gs().ollama_url}/api/v1/email-assistant/classify/batch"
IA_TIMEOUT = 60.0
IA_HEADERS = {"X-API-Key": get_settings().ia_api_key}  # Securizado Fase 3

# ── Patrones heurísticos (pre-filtro rápido sin IA) ──

SUSPICIOUS_TLDS = {
    ".xyz", ".top", ".buzz", ".click", ".loan", ".work", ".gq", ".cf",
    ".tk", ".ml", ".ga", ".cam", ".icu", ".monster", ".rest", ".cyou",
}

SUSPICIOUS_EXTENSIONS = {
    ".exe", ".scr", ".bat", ".cmd", ".pif", ".com", ".vbs", ".js",
    ".wsf", ".msi", ".ps1", ".hta",
}

PHISHING_KEYWORDS = [
    r"verif(?:y|ica)\s+(?:your|tu|su)\s+(?:account|cuenta)",
    r"(?:cuenta|account)\s+(?:será|will be)\s+(?:bloqueada|suspended|closed)",
    r"(?:click|haz clic|ingresa)\s+(?:here|aquí|ahora|inmediatamente)",
    r"(?:urgent|urgente|inmediato|immediate)\s+(?:action|acción|respuesta)",
    r"(?:ganaste|you won|congratulations|felicidades)\s+",
    r"(?:lottery|lotería|herencia|inheritance|prince|príncipe)",
    r"(?:wire transfer|transferencia|western union|bitcoin|crypto)",
    r"(?:password|contraseña)\s+(?:expired|expirada|reset|cambiar)",
    r"(?:irs|sat|sri|dian|sunat|impuestos).*(?:refund|reembolso|devolución)",
    r"(?:free|gratis)\s+(?:iphone|gift card|regalo|prize|premio)",
    r"(?:nigerian?|from africa)\s+",
    r"(?:unsubscribe|darse de baja).{0,20}(?:click|clic)",
]

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "shorturl.at", "rb.gy", "cutt.ly",
}

COMPILED_PHISHING = [re.compile(p, re.IGNORECASE) for p in PHISHING_KEYWORDS]


def _heuristic_score(subject: str, snippet: str, from_addr: str, 
                      has_attachments: bool = False, attachment_names: list[str] | None = None) -> dict:
    """
    Analiza heurísticamente un correo. Retorna score 0-100 y razones.
    Score >= 70: spam probable
    Score >= 50: sospechoso
    Score < 50: probablemente legítimo
    """
    score = 0
    reasons = []
    text = f"{subject} {snippet}".lower()
    from_lower = from_addr.lower()

    # 1. TLD sospechoso
    email_match = re.search(r"@[\w.-]+\.(\w+)", from_lower)
    if email_match:
        domain = from_lower.split("@")[-1] if "@" in from_lower else ""
        tld = "." + domain.split(".")[-1] if "." in domain else ""
        if tld in SUSPICIOUS_TLDS:
            score += 25
            reasons.append(f"TLD sospechoso: {tld}")

    # 2. Keywords de phishing/estafa
    for pattern in COMPILED_PHISHING:
        if pattern.search(text):
            score += 20
            reasons.append(f"Patrón sospechoso: {pattern.pattern[:40]}")
            break  # Solo contar una vez

    # 3. Muchos links
    url_count = len(re.findall(r"https?://", text))
    if url_count > 5:
        score += 15
        reasons.append(f"Muchos enlaces ({url_count})")

    # 4. Links acortados
    for shortener in URL_SHORTENERS:
        if shortener in text:
            score += 15
            reasons.append(f"Enlace acortado: {shortener}")
            break

    # 5. Archivos adjuntos sospechosos
    if attachment_names:
        for name in attachment_names:
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext in SUSPICIOUS_EXTENSIONS:
                score += 30
                reasons.append(f"Adjunto sospechoso: {name}")
                break

    # 6. From genérico / no-reply masivo
    if re.search(r"(noreply|no-reply|mailer-daemon|bounce)", from_lower):
        score += 5
        reasons.append("Remitente automático")

    # 7. Asunto todo en mayúsculas
    if subject == subject.upper() and len(subject) > 10:
        score += 10
        reasons.append("Asunto en MAYÚSCULAS")

    # 8. Caracteres unicode sospechosos (homoglyphs)
    if re.search(r"[\u0400-\u04FF\u0370-\u03FF]", subject):
        if not re.search(r"[\u0400-\u04FF]{3,}", subject):  # No es texto real en cirílico
            score += 15
            reasons.append("Caracteres homoglifos sospechosos")

    # 9. Urgencia excesiva
    urgency_words = len(re.findall(r"\b(urgente|urgent|ahora|now|inmediato|immediate|último aviso|last chance|final warning)\b", text, re.IGNORECASE))
    if urgency_words >= 2:
        score += 15
        reasons.append(f"Urgencia artificial ({urgency_words} palabras)")

    return {"score": min(score, 100), "reasons": reasons}


async def ensure_spam_table(db):
    # Tabla creada por migrations/init_tables.sql (Fase 3)
    # spam_analysis + índice
    pass


@router.get("/spam/scan")
async def scan_for_spam(
    request: Request,
    folder: str = "INBOX",
    limit: int = 50,
    auto_move: bool = False,
    uid: Optional[int] = None,
    user: str = Depends(get_current_user),
):
    """
    Escanea el folder buscando spam. Combina heurísticas + IA.
    Si uid se proporciona, escanea solo ese mensaje específico.
    Si auto_move=true, mueve automáticamente los detectados a Junk.
    """
    db = request.app.state.db_pool
    await ensure_spam_table(db)

    # 1) Obtener mensajes
    from app.mail.clients.imap_client import get_imap_connection, fetch_message_headers
    from app.mail.services.message_service import list_messages

    password = await get_user_password(request, user)

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        if uid:
            # Escaneo de un solo mensaje por UID
            await imap.select(folder)
            headers = await fetch_message_headers(imap, [uid])
            messages = []
            for h in headers:
                msg = h if isinstance(h, dict) else {
                    "uid": getattr(h, "uid", uid),
                    "subject": getattr(h, "subject", ""),
                    "from": getattr(h, "from_addr", getattr(h, "sender", "")),
                    "snippet": getattr(h, "snippet", ""),
                    "has_attachments": getattr(h, "has_attachments", False),
                }
                if isinstance(h, dict):
                    msg.setdefault("uid", uid)
                messages.append(msg)
            if not messages:
                messages = [{"uid": uid, "subject": "", "from": "", "snippet": ""}]
        else:
            result = await list_messages(imap, folder, page=1, per_page=limit)
            messages = result.get("messages", [])
    except Exception as e:
        logger.warning(f"SpamGuard fetch error: {e}")
        messages = []

    if not messages:
        if imap:
            try: await imap.logout()
            except: pass
        return {"scanned": 0, "spam_found": 0, "moved": 0, "details": []}

    # 2) Verificar cache
    uids = [m["uid"] for m in messages]
    placeholders = ", ".join(f"${i+3}" for i in range(len(uids)))
    cached = await db.fetch(
        f"SELECT message_uid, is_spam, spam_score, reasons, user_override FROM spam_analysis "
        f"WHERE owner=$1 AND folder=$2 AND message_uid IN ({placeholders})",
        user, folder, *uids
    )
    cache_map = {r["message_uid"]: dict(r) for r in cached}

    # 3) Analizar los no cacheados
    uncached_msgs = [m for m in messages if m["uid"] not in cache_map]
    
    # Paso A: Heurísticas rápidas
    heuristic_results = {}
    for m in uncached_msgs:
        h = _heuristic_score(
            m.get("subject", ""),
            m.get("snippet", ""),
            m.get("from", ""),
            m.get("has_attachments", False),
        )
        heuristic_results[m["uid"]] = h

    # Paso B: Los sospechosos (score >= 30) los enviamos a la IA para confirmación
    suspects = [m for m in uncached_msgs if heuristic_results[m["uid"]]["score"] >= 30]
    ia_results = {}

    if suspects:
        try:
            batch = []
            for m in suspects[:10]:
                batch.append({
                    "subject": m.get("subject", ""),
                    "from_addr": m.get("from", ""),
                    "snippet": m.get("snippet", m.get("text_body", ""))[:300],
                    "to_addr": user,
                    "task": "spam_detection",
                    "instructions": (
                        "Analiza si este correo es SPAM, phishing o estafa. "
                        "Busca: publicidad no solicitada, ofertas falsas, suplantación de identidad, "
                        "links sospechosos, urgencia artificial, solicitudes de datos personales/bancarios, "
                        "premios falsos, herencias ficticias. "
                        "Responde con priority=low si es spam, normal si es legítimo, "
                        "y en reason explica por qué."
                    ),
                })

            async with httpx.AsyncClient(timeout=IA_TIMEOUT) as client:
                resp = await client.post(IA_URL, json={"emails": batch}, headers=IA_HEADERS)
                resp.raise_for_status()
                data = resp.json()

            for i, m in enumerate(suspects[:10]):
                if i < len(data.get("results", [])):
                    r = data["results"][i]
                    is_spam_ia = r.get("priority") == "low" or "spam" in r.get("reason", "").lower()
                    ia_results[m["uid"]] = {
                        "is_spam": is_spam_ia,
                        "reason": r.get("reason", ""),
                        "confidence": r.get("confidence", 0.5),
                    }
        except Exception as e:
            logger.warning(f"SpamGuard IA failed: {e}")

    # Paso C: Combinar resultados y guardar
    spam_uids = []
    details = []

    for m in uncached_msgs:
        uid = m["uid"]
        h = heuristic_results[uid]
        ia = ia_results.get(uid)

        # Decisión final
        if ia and ia["is_spam"]:
            is_spam = True
            final_score = max(h["score"], 70)
            method = "ia+heuristic"
            reasons = h["reasons"] + [f"IA: {ia[reason]}"]
        elif h["score"] >= 70:
            is_spam = True
            final_score = h["score"]
            method = "heuristic"
            reasons = h["reasons"]
        elif ia and not ia["is_spam"] and h["score"] >= 50:
            is_spam = False
            final_score = h["score"]
            method = "ia_cleared"
            reasons = h["reasons"] + [f"IA descartó: {ia[reason]}"]
        else:
            is_spam = False
            final_score = h["score"]
            method = "heuristic"
            reasons = h["reasons"]

        # Guardar en cache
        await db.execute(
            """INSERT INTO spam_analysis (owner, folder, message_uid, is_spam, spam_score, method, reasons)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (owner, folder, message_uid) DO UPDATE
               SET is_spam=$4, spam_score=$5, method=$6, reasons=$7, analyzed_at=now()
               WHERE spam_analysis.user_override IS NULL""",
            user, folder, uid, is_spam, final_score, method, reasons
        )

        if is_spam:
            spam_uids.append(uid)

        details.append({
            "uid": uid,
            "from": m.get("from", ""),
            "subject": m.get("subject", ""),
            "is_spam": is_spam,
            "score": final_score,
            "method": method,
            "reasons": reasons,
        })

    # También agregar los cacheados al resultado
    for m in messages:
        if m["uid"] in cache_map:
            c = cache_map[m["uid"]]
            if c.get("user_override") == "not_spam":
                continue
            if c["is_spam"]:
                spam_uids.append(m["uid"])
            details.append({
                "uid": m["uid"],
                "from": m.get("from", ""),
                "subject": m.get("subject", ""),
                "is_spam": c["is_spam"],
                "score": c["spam_score"],
                "method": "cached",
                "reasons": c.get("reasons", []),
            })

    # 4) Auto-mover a Junk si se solicitó
    moved = 0
    if auto_move and spam_uids:
        try:
            from app.mail.clients.imap_client import uid_bulk_action
            ok = await uid_bulk_action(imap, folder, spam_uids, "move", "Junk")
            if ok:
                moved = len(spam_uids)
                logger.info(f"SpamGuard: moved {moved} spam messages to Junk for {user}")
        except Exception as e:
            logger.warning(f"SpamGuard auto-move failed: {e}")

    try:
        await imap.logout()
    except:
        pass

    # Solo retornar los spam en details
    spam_details = [d for d in details if d["is_spam"]]

    return {
        "scanned": len(messages),
        "spam_found": len(spam_uids),
        "moved": moved,
        "details": spam_details,
    }


@router.post("/spam/report")
async def report_spam(
    request: Request,
    user: str = Depends(get_current_user),
):
    """
    El usuario reporta un correo como spam → mover a Junk + guardar para mejorar detección.
    Body: {folder, uid} o {folder, uids: []}
    """
    body = await request.json()
    folder = body.get("folder", "INBOX")
    uids = body.get("uids", [])
    if body.get("uid"):
        uids = [body["uid"]]
    
    if not uids:
        raise HTTPException(400, "uid o uids requerido")

    db = request.app.state.db_pool
    await ensure_spam_table(db)

    # Guardar como spam confirmado por usuario
    for uid in uids:
        await db.execute(
            """INSERT INTO spam_analysis (owner, folder, message_uid, is_spam, spam_score, method, reasons, user_override)
               VALUES ($1, $2, $3, true, 100, 'user_report', ARRAY['Reportado como spam por el usuario'], 'spam')
               ON CONFLICT (owner, folder, message_uid) DO UPDATE
               SET is_spam=true, spam_score=100, method='user_report',
                   reasons=ARRAY['Reportado como spam por el usuario'],
                   user_override='spam', analyzed_at=now()""",
            user, folder, uid
        )

    # Mover a Junk
    password = await get_user_password(request, user)
    moved = 0
    if password:
        from app.mail.clients.imap_client import get_imap_connection, uid_bulk_action
        login_user = await get_imap_login_user(request, user)
        imap = await get_imap_connection(login_user, password)
        try:
            try:
                from app.phishsim import service as _phsvc
                await _phsvc.mark_reports_from_imap(imap, folder, uids, db)
            except Exception:
                pass
            ok = await uid_bulk_action(imap, folder, uids, "move", "Junk")
            if ok:
                moved = len(uids)
        except:
            pass
        finally:
            try: await imap.logout()
            except: pass

    return {"status": "reported", "moved": moved}


@router.post("/spam/not-spam")
async def mark_not_spam(
    request: Request,
    user: str = Depends(get_current_user),
):
    """
    El usuario marca un correo como NO spam → mover de Junk a INBOX + guardar override.
    Body: {folder, uid} o {folder, uids: []}
    """
    body = await request.json()
    folder = body.get("folder", "Junk")
    uids = body.get("uids", [])
    if body.get("uid"):
        uids = [body["uid"]]

    if not uids:
        raise HTTPException(400, "uid o uids requerido")

    db = request.app.state.db_pool
    await ensure_spam_table(db)

    for uid in uids:
        await db.execute(
            """INSERT INTO spam_analysis (owner, folder, message_uid, is_spam, spam_score, method, reasons, user_override)
               VALUES ($1, $2, $3, false, 0, user_override, ARRAY[Marcado como NO spam por el usuario], not_spam)
               ON CONFLICT (owner, folder, message_uid) DO UPDATE
               SET is_spam=false, spam_score=0, user_override=not_spam,
                   reasons=ARRAY[Marcado como NO spam por el usuario], analyzed_at=now()""",
            user, folder, uid
        )

    # Mover a INBOX si está en Junk
    password = await get_user_password(request, user)
    moved = 0
    if password and folder == "Junk":
        from app.mail.clients.imap_client import get_imap_connection, uid_bulk_action
        login_user = await get_imap_login_user(request, user)
        imap = await get_imap_connection(login_user, password)
        try:
            ok = await uid_bulk_action(imap, folder, uids, "move", "INBOX")
            if ok:
                moved = len(uids)
        except:
            pass
        finally:
            try: await imap.logout()
            except: pass

    return {"status": "cleared", "moved": moved}


@router.get("/spam/stats")
async def spam_stats(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Estadísticas de spam del usuario."""
    db = request.app.state.db_pool
    await ensure_spam_table(db)

    total = await db.fetchval(
        "SELECT COUNT(*) FROM spam_analysis WHERE owner=$1 AND is_spam=true", user
    )
    by_method = await db.fetch(
        "SELECT method, COUNT(*) as cnt FROM spam_analysis WHERE owner=$1 AND is_spam=true GROUP BY method",
        user
    )
    recent = await db.fetch(
        """SELECT message_uid, spam_score, method, reasons, analyzed_at
           FROM spam_analysis WHERE owner=$1 AND is_spam=true
           ORDER BY analyzed_at DESC LIMIT 10""",
        user
    )

    return {
        "total_spam_detected": total,
        "by_method": {r["method"]: r["cnt"] for r in by_method},
        "recent": [dict(r) for r in recent],
    }
