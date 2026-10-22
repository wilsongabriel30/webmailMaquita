import asyncpg

from app.config import get_settings


def _dsn(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgres://", 1)
    return url


def opciones_pool(
    settings=None, min_size: int | None = None, max_size: int | None = None
) -> dict:
    """Opciones de asyncpg según la configuración.

    Con PGBOUNCER=true (modo «transaction») la caché de sentencias preparadas tiene que
    ir apagada: cada transacción puede caer en otra conexión del servidor y una sentencia
    preparada con nombre no existiría allí («prepared statement does not exist»).
    Sin PgBouncer se dejan los valores de siempre.
    """
    s = settings or get_settings()
    op = {
        "min_size": s.db_pool_min if min_size is None else min_size,
        "max_size": s.db_pool_max if max_size is None else max_size,
    }
    if op["max_size"] < op["min_size"]:
        op["max_size"] = op["min_size"]
    if s.pgbouncer:
        op["statement_cache_size"] = 0
        op["max_cached_statement_lifetime"] = 0
    return op


async def create_db_pool(
    min_size: int | None = None, max_size: int | None = None
) -> asyncpg.Pool:
    settings = get_settings()
    return await asyncpg.create_pool(
        _dsn(settings.database_url), **opciones_pool(settings, min_size, max_size)
    )


async def create_read_pool() -> asyncpg.Pool | None:
    """Pool hacia la réplica de lectura (DATABASE_URL_LECTURA). None si no hay réplica."""
    settings = get_settings()
    url = (settings.database_url_lectura or "").strip()
    if not url:
        return None
    return await asyncpg.create_pool(_dsn(url), **opciones_pool(settings))


async def connect_db(url: str | None = None, **kw) -> asyncpg.Connection:
    """Conexión suelta (scripts y tareas puntuales) con las mismas reglas de PgBouncer."""
    settings = get_settings()
    if settings.pgbouncer:
        kw.setdefault("statement_cache_size", 0)
    return await asyncpg.connect(_dsn(url or settings.database_url), **kw)


def pool_lectura(app_state):
    """Pool para consultas que toleran unos segundos de retraso (informes, directorio).
    Sin réplica configurada devuelve el pool principal."""
    return getattr(app_state, "db_pool_lectura", None) or app_state.db_pool
