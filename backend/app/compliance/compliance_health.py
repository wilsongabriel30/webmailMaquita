"""
Compliance Healthcheck Module
Verifica estado de PostgreSQL, tablas, tareas en background y metricas clave.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("compliance.health")

# Las 8 tablas del modulo de compliance
COMPLIANCE_TABLES = [
    "compliance_cases",
    "compliance_search_queries",
    "compliance_search_results",
    "mail_trace_log",
    "user_activity_log",
    "compliance_alerts",
    "legal_holds",
    "compliance_evidence_exports",
]


async def _check_table_exists(db_pool, table_name: str) -> bool:
    """Verifica si una tabla existe en la BD."""
    try:
        row = await db_pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            table_name,
        )
        return bool(row)
    except Exception:
        return False


async def _get_record_count(db_pool, table_name: str) -> int:
    """Cuenta registros de una tabla. Retorna -1 si hay error."""
    try:
        count = await db_pool.fetchval(
            f'SELECT COUNT(*) FROM "{table_name}"'
        )  # noqa: S608
        return count or 0
    except Exception:
        return -1


async def _get_latest_timestamp(db_pool, table_name: str, column: str) -> str | None:
    """Obtiene el timestamp mas reciente de una columna."""
    try:
        ts = await db_pool.fetchval(
            f'SELECT MAX("{column}") FROM "{table_name}"'  # noqa: S608
        )
        if ts is None:
            return None
        if hasattr(ts, "isoformat"):
            return ts.isoformat()
        return str(ts)
    except Exception:
        return None


def _check_background_task(task_name: str) -> str:
    """
    Verifica si una tarea en background esta activa.
    Busca en las tareas de asyncio corriendo en el event loop actual.
    """
    try:
        loop = asyncio.get_running_loop()
        for task in asyncio.all_tasks(loop):
            name = task.get_name() if hasattr(task, "get_name") else str(task)
            if task_name.lower() in name.lower() and not task.done():
                return "running"
        return "stopped"
    except RuntimeError:
        return "unknown"


async def get_compliance_health(db_pool) -> dict:
    """
    Retorna un diccionario con el estado completo del modulo de compliance.

    Args:
        db_pool: Pool de conexiones asyncpg a PostgreSQL.

    Returns:
        dict con todas las metricas de salud.
    """
    result = {
        "version": "v1.0-compliance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "postgresql": "error",
        "tables_exist": [],
        "record_counts": {},
        "last_mail_trace": None,
        "last_activity": None,
        "log_ingestor": "unknown",
        "fraud_detector": "unknown",
        "legal_holds_active": 0,
        "alerts_open": 0,
    }

    # --- PostgreSQL connectivity ---
    try:
        test = await db_pool.fetchval("SELECT 1")
        if test == 1:
            result["postgresql"] = "ok"
    except Exception as exc:
        logger.error("Healthcheck: PostgreSQL no responde — %s", exc)
        result["postgresql"] = f"error: {exc}"
        return result  # sin BD no tiene sentido seguir

    # --- Verificar tablas existentes ---
    tables_exist = []
    for table in COMPLIANCE_TABLES:
        if await _check_table_exists(db_pool, table):
            tables_exist.append(table)
    result["tables_exist"] = tables_exist

    # --- Conteo de registros (en paralelo) ---
    count_tasks = {table: _get_record_count(db_pool, table) for table in tables_exist}
    if count_tasks:
        counts = await asyncio.gather(*count_tasks.values())
        result["record_counts"] = dict(zip(count_tasks.keys(), counts))

    # --- Timestamps mas recientes ---
    if "mail_trace_log" in tables_exist:
        result["last_mail_trace"] = await _get_latest_timestamp(
            db_pool, "mail_trace_log", "timestamp"
        )

    if "user_activity_log" in tables_exist:
        result["last_activity"] = await _get_latest_timestamp(
            db_pool, "user_activity_log", "timestamp"
        )

    # --- Background tasks ---
    result["log_ingestor"] = _check_background_task("log_ingestor")
    result["fraud_detector"] = _check_background_task("fraud_detect")

    # --- Legal holds activos ---
    if "legal_holds" in tables_exist:
        try:
            active = await db_pool.fetchval(
                "SELECT COUNT(*) FROM legal_holds WHERE released_at IS NULL"
            )
            result["legal_holds_active"] = active or 0
        except Exception as exc:
            logger.warning("Healthcheck: error contando legal_holds — %s", exc)

    # --- Alertas abiertas (no acknowledged) ---
    if "compliance_alerts" in tables_exist:
        try:
            open_alerts = await db_pool.fetchval(
                "SELECT COUNT(*) FROM compliance_alerts WHERE acknowledged = false"
            )
            result["alerts_open"] = open_alerts or 0
        except Exception as exc:
            logger.warning("Healthcheck: error contando alertas — %s", exc)

    return result
