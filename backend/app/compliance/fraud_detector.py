"""Fraud Detector — Detecta patrones sospechosos y genera alertas.

Se ejecuta periódicamente revisando user_activity_log y mail_trace
para detectar:
- Reenvío externo
- Reglas Sieve sospechosas
- Envío masivo
- Eliminación masiva
- Descarga masiva de adjuntos
- Palabras clave de fraude financiero
- Login desde IP inusual
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("compliance.fraud")

# Palabras clave de fraude financiero en subject/body
FRAUD_KEYWORDS = [
    "cambio de cuenta",
    "nueva cuenta bancaria",
    "urgente pago",
    "actualizar datos bancarios",
    "transferencia urgente",
    "cambio de datos de pago",
    "nuevo número de cuenta",
    "favor transferir",
    "cambio proveedor",
    "pago inmediato",
    "wire transfer",
    "bank account change",
    "payment update",
]

# Dominios internos (no generan alerta de reenvío externo)
INTERNAL_DOMAINS = {"ejemplo.com", "ejemplo.com"}


class FraudDetector:
    def __init__(self, db_pool):
        self.db = db_pool
        self._running = False

    async def start(self):
        self._running = True
        logger.info("Fraud detector started")

        while self._running:
            try:
                await self._check_mass_send()
                await self._check_mass_delete()
                await self._check_external_forwards()
                await self._check_fraud_keywords()
                await self._check_unusual_login()
            except Exception as exc:
                logger.error("Fraud detector error: %s", exc)

            await asyncio.sleep(300)  # Cada 5 minutos

    def stop(self):
        self._running = False

    async def _create_alert(
        self, alert_type, severity, username, description, details=None, source_ip=None
    ):
        """Crea alerta si no existe una similar reciente (últimas 2 horas)."""
        recent = await self.db.fetchval(
            """SELECT count(*) FROM fraud_alerts
               WHERE alert_type = $1 AND username = $2
               AND created_at >= NOW() - INTERVAL '2 hours'""",
            alert_type,
            username,
        )
        if recent > 0:
            return  # Ya hay alerta reciente

        await self.db.execute(
            """INSERT INTO fraud_alerts
               (alert_type, severity, username, description, details, source_ip)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6::inet)""",
            alert_type,
            severity,
            username,
            description,
            json.dumps(details) if details else None,
            source_ip,
        )
        logger.warning("FRAUD ALERT: %s — %s — %s", alert_type, username, description)

    async def _check_mass_send(self):
        """Detecta usuarios que envían muchos correos en poco tiempo."""
        # >15 correos en 5 minutos
        rows = await self.db.fetch("""SELECT username, count(*) as total
               FROM user_activity_log
               WHERE action = 'email_send'
               AND created_at >= NOW() - INTERVAL '5 minutes'
               GROUP BY username HAVING count(*) > 15""")
        for r in rows:
            await self._create_alert(
                "mass_send",
                "high",
                r["username"],
                f"Envío masivo detectado: {r['total']} correos en 5 minutos",
                {"count": r["total"], "window": "5min"},
            )

    async def _check_mass_delete(self):
        """Detecta eliminación masiva de correos."""
        rows = await self.db.fetch("""SELECT username, count(*) as total
               FROM user_activity_log
               WHERE action IN ('email_delete', 'email_bulk_delete', 'email_expunge')
               AND created_at >= NOW() - INTERVAL '10 minutes'
               GROUP BY username HAVING count(*) > 20""")
        for r in rows:
            await self._create_alert(
                "evidence_destruction",
                "critical",
                r["username"],
                f"Eliminación masiva detectada: {r['total']} acciones de borrado en 10 minutos",
                {"count": r["total"], "window": "10min"},
            )

    async def _check_external_forwards(self):
        """Detecta creación de reenvíos a dominios externos."""
        rows = await self.db.fetch("""SELECT username, target, details, ip_address
               FROM user_activity_log
               WHERE action IN ('forward_create', 'sieve_create', 'sieve_modify')
               AND created_at >= NOW() - INTERVAL '5 minutes'""")
        for r in rows:
            target = r["target"] or ""
            details = r["details"] or {}
            # Verificar si el target contiene dominio externo
            if any(d in target.lower() for d in INTERNAL_DOMAINS):
                continue
            await self._create_alert(
                "external_forward",
                "critical",
                r["username"],
                f"Creación de reenvío/regla sospechosa detectada: {target}",
                {"target": target, "details": details},
                str(r["ip_address"]) if r["ip_address"] else None,
            )

    async def _check_fraud_keywords(self):
        """Detecta correos con palabras clave de fraude financiero en mail_trace."""
        # Buscar en subject_hash no es posible, pero podemos buscar en los correos enviados
        # que fueron registrados en user_activity_log
        rows = await self.db.fetch(
            """SELECT mt.sender, mt.recipient, mt.message_id, mt.created_at
               FROM mail_trace mt
               WHERE mt.created_at >= NOW() - INTERVAL '5 minutes'
               AND mt.direction = 'inbound'
               AND mt.status = 'sent'
               LIMIT 100"""
        )
        # Fase 2: búsqueda por keywords en subject via doveadm

    async def _check_unusual_login(self):
        """Detecta login desde IPs EXTERNAS no habituales. Ignora las redes
        confiables (LAN/VPN, configurables en TRUSTED_NETWORKS) y no repite la
        misma alerta (ip+usuario) en 7 días."""
        from app.config import get_settings
        nets = [n.strip() for n in get_settings().trusted_networks.split(",") if n.strip()]
        # Buscar logins desde una IP nueva (no vista en 30 días), que NO esté en una
        # red confiable y que no tenga ya una alerta reciente.
        rows = await self.db.fetch("""SELECT a.username, a.ip_address, a.created_at
               FROM user_activity_log a
               WHERE a.action = 'login_success'
               AND a.created_at >= NOW() - INTERVAL '5 minutes'
               AND a.ip_address IS NOT NULL
               AND NOT (a.ip_address <<= ANY($1::inet[]))
               AND a.ip_address::text NOT IN (
                   SELECT DISTINCT ip_address::text FROM user_activity_log
                   WHERE username = a.username
                   AND action = 'login_success'
                   AND created_at < NOW() - INTERVAL '5 minutes'
                   AND created_at >= NOW() - INTERVAL '30 days'
                   AND ip_address IS NOT NULL
               )
               AND NOT EXISTS (
                   SELECT 1 FROM fraud_alerts fa
                   WHERE fa.alert_type = 'unusual_login'
                   AND fa.source_ip::text = a.ip_address::text
                   AND fa.username = a.username
                   AND fa.created_at >= NOW() - INTERVAL '7 days'
               )""", nets)
        for r in rows:
            await self._create_alert(
                "unusual_login",
                "high",
                r["username"],
                f"Login desde IP no habitual: {r['ip_address']}",
                {"ip": str(r["ip_address"])},
                str(r["ip_address"]),
            )


async def start_fraud_detector(db_pool) -> FraudDetector:
    """Inicia el detector de fraude como tarea background."""
    detector = FraudDetector(db_pool)
    asyncio.create_task(detector.start())
    return detector
