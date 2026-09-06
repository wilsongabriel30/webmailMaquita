"""Registro de agentes disponibles. Para agregar uno: crear el archivo en
agents/ y añadir su instancia aquí."""

from app.agents.agents.bandeja import InboxTriageAgent
from app.agents.agents.briefing import BriefingAgent
from app.agents.agents.postura import PostureAgent
from app.agents.agents.seguridad import SecurityAgent

AGENTS = {
    a.name: a
    for a in (SecurityAgent(), PostureAgent(), BriefingAgent(), InboxTriageAgent())
}
