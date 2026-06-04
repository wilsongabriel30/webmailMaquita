"""Protección contra cuentas comprometidas.

Detecta y bloquea patrones de abuso:
- Envío masivo anómalo (spam desde cuentas comprometidas)
- Forwarding a dominios externos sospechosos
- Cambios de configuración peligrosos

Motivación: usuarios de Zimbra sufrían compromiso de cuenta → forwarding
a Gmail + envío masivo de spam → blacklist de IP del servidor.

Este módulo previene que eso ocurra desde el webmail de Maquita.
"""
import asyncio
import logging
import time
from datetime import datetime

logger = logging.getLogger("account_protection")

# ─── Dominios del organización (forwarding permitido sin restricción) ───
INTERNAL_DOMAINS = frozenset({
    "ejemplo.com",
    "ejemplo.com",
})

# ─── Umbrales de detección ───
# Si un usuario envía más de esto en ventana corta → cuenta bloqueada
SPIKE_THRESHOLD_5MIN = 15     # >15 correos en 5 min = anómalo
SPIKE_THRESHOLD_15MIN = 40    # >40 correos en 15 min = anómalo
UNIQUE_RECIPIENTS_1H = 50     # >50 destinatarios únicos en 1 hora = anómalo

# Tiempo de bloqueo automático (segundos)
AUTO_BLOCK_DURATION = 7200  # 2 horas


async def check_send_anomaly(redis, username: str, recipients: list[str]) -> dict:
    """Verificar si el patrón de envío es anómalo. Llamar ANTES de enviar.

    Returns:
        {"allowed": True} si OK
        {"allowed": False, "reason": "..."} si bloqueado
    """
    # 1. ¿Cuenta ya bloqueada por anomalía previa?
    blocked = await redis.get(f"account_blocked:{username}")
    if blocked:
        ttl = await redis.ttl(f"account_blocked:{username}")
        return {
            "allowed": False,
            "reason": f"Cuenta bloqueada por actividad sospechosa. Se desbloquea en {ttl // 60} minutos. Contacte al administrador."
        }

    now = time.time()

    # 2. Registrar este envío en la ventana deslizante (sorted set por timestamp)
    send_key = f"send_history:{username}"
    await redis.zadd(send_key, {f"{now}:{','.join(recipients[:5])}": now})
    await redis.expire(send_key, 3600)  # mantener 1 hora

    # Limpiar entradas viejas (>1h)
    await redis.zremrangebyscore(send_key, 0, now - 3600)

    # 3. Contar envíos en ventanas
    count_5min = await redis.zcount(send_key, now - 300, now)
    count_15min = await redis.zcount(send_key, now - 900, now)

    # 4. Contar destinatarios únicos en 1 hora
    rcpt_key = f"send_recipients:{username}"
    for r in recipients:
        await redis.sadd(rcpt_key, r.lower())
    await redis.expire(rcpt_key, 3600)
    unique_rcpts = await redis.scard(rcpt_key)

    # 5. Evaluar anomalías
    anomaly = None
    if count_5min > SPIKE_THRESHOLD_5MIN:
        anomaly = f"Spike: {count_5min} correos en 5 minutos (límite: {SPIKE_THRESHOLD_5MIN})"
    elif count_15min > SPIKE_THRESHOLD_15MIN:
        anomaly = f"Spike: {count_15min} correos en 15 minutos (límite: {SPIKE_THRESHOLD_15MIN})"
    elif unique_rcpts > UNIQUE_RECIPIENTS_1H:
        anomaly = f"Destinatarios únicos: {unique_rcpts} en 1 hora (límite: {UNIQUE_RECIPIENTS_1H})"

    if anomaly:
        # BLOQUEAR CUENTA
        await redis.setex(f"account_blocked:{username}", AUTO_BLOCK_DURATION, anomaly)

        # Limpiar sesión para forzar re-login
        await redis.delete(f"imap_pass:{username}")

        logger.critical(
            f"ACCOUNT BLOCKED: {username} — {anomaly}"
        )

        # Registrar incidente para admin
        await _log_security_incident(redis, username, "mass_send_blocked", anomaly)

        return {
            "allowed": False,
            "reason": f"Actividad anómala detectada: {anomaly}. Cuenta bloqueada por {AUTO_BLOCK_DURATION // 60} minutos."
        }

    return {"allowed": True}


async def check_forward_policy(redis, username: str, forward_address: str, db=None) -> dict:
    """Verificar si un forwarding externo está permitido.

    Política:
    - Forward a dominios internos (ejemplo.com, ejemplo.com): PERMITIDO
    - Forward a dominios externos: REQUIERE APROBACIÓN ADMIN

    Returns:
        {"allowed": True} si OK
        {"allowed": False, "reason": "..."} si bloqueado
    """
    if not forward_address or "@" not in forward_address:
        return {"allowed": False, "reason": "Dirección de reenvío inválida"}

    domain = forward_address.lower().split("@")[1]

    # Dominios internos: siempre permitido
    if domain in INTERNAL_DOMAINS:
        return {"allowed": True}

    # Verificar si este forward fue aprobado por admin
    if db:
        approved = await db.fetchval(
            "SELECT 1 FROM approved_forwards WHERE username = $1 AND forward_address = $2 AND is_active = TRUE",
            username, forward_address.lower()
        )
        if approved:
            return {"allowed": True}

    # También verificar en Redis (cache de aprobaciones)
    approved_cache = await redis.sismember(f"approved_forwards:{username}", forward_address.lower())
    if approved_cache:
        return {"allowed": True}

    # BLOQUEAR forwarding externo no aprobado
    logger.warning(
        f"FORWARD BLOCKED: {username} → {forward_address} (dominio externo no aprobado)"
    )
    await _log_security_incident(
        redis, username, "external_forward_blocked",
        f"Intento de forwarding a {forward_address} (dominio: {domain})"
    )

    return {
        "allowed": False,
        "reason": f"El reenvío a dominios externos ({domain}) requiere aprobación del administrador. "
                  f"Contacte a soporte técnico para habilitar el reenvío a {forward_address}."
    }


async def audit_sieve_change(redis, username: str, change_type: str, details: str):
    """Registrar cambios en filtros sieve para auditoría.

    change_type: "forward_created", "forward_deleted", "vacation_changed", "filter_created", etc.
    """
    await _log_security_incident(redis, username, f"sieve_{change_type}", details)


async def _log_security_incident(redis, username: str, event_type: str, details: str):
    """Registrar incidente de seguridad en Redis (lista para consulta admin)."""
    incident = {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "event": event_type,
        "details": details,
    }
    import json
    await redis.lpush("security_incidents", json.dumps(incident))
    await redis.ltrim("security_incidents", 0, 999)  # mantener últimos 1000

    # También incrementar contador de incidentes del usuario
    inc_key = f"incidents:{username}"
    await redis.incr(inc_key)
    await redis.expire(inc_key, 86400)


async def get_account_status(redis, username: str) -> dict:
    """Obtener estado de seguridad de una cuenta (para admin panel)."""
    blocked = await redis.get(f"account_blocked:{username}")
    blocked_ttl = await redis.ttl(f"account_blocked:{username}") if blocked else 0
    incidents_today = int(await redis.get(f"incidents:{username}") or 0)

    send_key = f"send_history:{username}"
    sends_1h = await redis.zcount(send_key, time.time() - 3600, time.time())

    rcpt_key = f"send_recipients:{username}"
    unique_rcpts = await redis.scard(rcpt_key)

    return {
        "username": username,
        "is_blocked": bool(blocked),
        "block_reason": blocked.decode() if isinstance(blocked, bytes) else blocked,
        "block_ttl_seconds": max(0, blocked_ttl),
        "incidents_today": incidents_today,
        "sends_last_hour": sends_1h,
        "unique_recipients_last_hour": unique_rcpts,
    }


async def admin_unblock_account(redis, username: str):
    """Admin desbloquea una cuenta manualmente."""
    await redis.delete(f"account_blocked:{username}")
    await redis.delete(f"send_history:{username}")
    await redis.delete(f"send_recipients:{username}")
    logger.info(f"ACCOUNT UNBLOCKED by admin: {username}")


async def admin_approve_forward(redis, db, username: str, forward_address: str, approved_by: str):
    """Admin aprueba un forwarding externo."""
    # Guardar en DB
    await db.execute("""
        INSERT INTO approved_forwards (username, forward_address, approved_by, is_active)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (username, forward_address) DO UPDATE SET is_active = TRUE, approved_by = $3
    """, username, forward_address.lower(), approved_by)

    # Cache en Redis
    await redis.sadd(f"approved_forwards:{username}", forward_address.lower())

    logger.info(f"FORWARD APPROVED: {username} → {forward_address} (by {approved_by})")
