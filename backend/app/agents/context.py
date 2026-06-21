"""Contexto que reciben los agentes (recursos compartidos)."""
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentContext:
    db: Any
    redis: Any
    settings: Any
