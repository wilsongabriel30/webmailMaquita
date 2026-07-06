"""
Configuración centralizada de conexión a Base de Datos
Fundación Maquita - Sistema FARO

Uso:
    from services.db_config import get_db_url, get_db_engine

En producción configurar:
    USE_PGBOUNCER=true (o NOMINA_DB_PORT=6432)
"""

import os
import logging
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

# Cache del engine para reutilizar conexiones
_engine_cache = {}


def get_db_config():
    """
    Obtiene la configuración de la base de datos.
    En producción usa PgBouncer (puerto 6432) si está configurado.
    """
    use_pgbouncer = os.getenv('USE_PGBOUNCER', 'false').lower() == 'true'

    # Si USE_PGBOUNCER está activo, usar 6432; sino usar lo que diga NOMINA_DB_PORT o 5432
    default_port = '6432' if use_pgbouncer else '5432'

    config = {
        'host': os.getenv('NOMINA_DB_HOST', '193.16.0.132'),
        'port': os.getenv('NOMINA_DB_PORT', default_port),
        'database': os.getenv('NOMINA_DB_NAME', 'nomina'),
        'username': os.getenv('NOMINA_DB_USER', 'sistemas'),
        'password': os.getenv('NOMINA_DB_PASSWORD')
    }

    return config


def get_db_url():
    """
    Genera la URL de conexión a la base de datos.
    """
    config = get_db_config()
    url = (
        f"postgresql://{config['username']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    return url


def get_db_engine(pool_size=2, max_overflow=3, pool_recycle=1800, pool_timeout=10):
    """
    Obtiene un engine SQLAlchemy con connection pooling optimizado.
    Reutiliza el engine si ya existe (singleton pattern).

    NOTA: Valores reducidos para evitar agotamiento de conexiones PostgreSQL
    con múltiples workers de gunicorn.

    Args:
        pool_size: Número de conexiones en el pool (default: 2, reducido)
        max_overflow: Conexiones adicionales permitidas (default: 3, reducido)
        pool_recycle: Segundos para reciclar conexiones (default: 1800)
        pool_timeout: Timeout para obtener conexión (default: 30)

    Returns:
        SQLAlchemy Engine
    """
    global _engine_cache

    cache_key = f"{pool_size}_{max_overflow}_{pool_recycle}"

    if cache_key not in _engine_cache:
        db_url = get_db_url()
        config = get_db_config()

        safe_url = f"postgresql://{config['username']}:***@{config['host']}:{config['port']}/{config['database']}"
        logger.info(f"Creando engine de BD: {safe_url}")

        _engine_cache[cache_key] = create_engine(
            db_url,
            pool_size=pool_size,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            connect_args={
                'connect_timeout': 3,        # fallar rapido si la BD es inalcanzable
                'tcp_user_timeout': 3000,    # cortar conexion stale sin ACK en 3s (ms)
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 3,
            }
        )

    return _engine_cache[cache_key]


def get_safe_db_url():
    """
    Retorna la URL de BD con la contraseña oculta (para logs).
    """
    config = get_db_config()
    return f"postgresql://{config['username']}:***@{config['host']}:{config['port']}/{config['database']}"
