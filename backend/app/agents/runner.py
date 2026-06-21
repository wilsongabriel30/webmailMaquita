"""Orquestador: ejecuta un agente con su contexto."""
from app.agents.context import AgentContext
from app.agents.registry import AGENTS


async def run_agent(name: str, db, redis, settings, dry_run: bool = True) -> dict:
    agent = AGENTS.get(name)
    if not agent:
        raise ValueError(f"agente desconocido: {name}")
    ctx = AgentContext(db=db, redis=redis, settings=settings)
    return await agent.run(ctx, dry_run=dry_run)


def list_agents() -> list[dict]:
    return [{"name": a.name, "descripcion": a.descripcion} for a in AGENTS.values()]
