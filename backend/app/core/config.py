"""Proxy — canonical source is app.config (Fase 2 cleanup)."""

from app.config import *  # noqa: F401,F403
from app.config import Settings, get_settings  # explicit re-export
