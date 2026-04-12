"""Proxy — canonical source is app.config (Fase 2 cleanup)."""
from app.config import *  # noqa: F401,F403
from app.config import get_settings, Settings  # explicit re-export
