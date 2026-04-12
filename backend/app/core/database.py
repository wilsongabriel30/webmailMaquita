"""Proxy — canonical source is app.database (Fase 2 cleanup)."""
from app.database import *  # noqa: F401,F403
from app.database import create_db_pool  # explicit re-export
