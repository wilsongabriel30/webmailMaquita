"""Contexto que reciben los agentes (recursos compartidos)."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    db: Any
    redis: Any
    settings: Any
    params: dict = field(default_factory=dict)
