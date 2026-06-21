"""Interfaz común de un agente autónomo.

Cada agente es un archivo aparte que hereda de Agent e implementa `run`.
Devuelve un dict normalizado: {agent, descripcion, summary, actions, ai?}.
Seguro por defecto: con dry_run=True el agente NO aplica acciones, solo propone.
"""


class Agent:
    name = "base"
    descripcion = ""

    async def run(self, ctx, dry_run: bool = True) -> dict:
        raise NotImplementedError
