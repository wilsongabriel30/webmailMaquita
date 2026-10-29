"""Configuración personal de Tareas (la ⚙ de la barra, como en To Do; F6 29/10/2026).

Va en `task_preferencias.ajustes` (JSONB) junto a `avisos_correo` (F4), que se muestra en el mismo diálogo.
Las claves que falten toman su valor por defecto y las desconocidas se ignoran.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.tasks import avisos_listas

# Listas inteligentes que se pueden ocultar (Mi día y Tareas siempre se ven).
OCULTABLES = ("important", "planned", "assigned", "flagged")


class Ajustes(BaseModel):
    confirmar_eliminar: bool = True
    importantes_arriba: bool = False
    sonido_completar: bool = True
    listas_ocultas: list[str] = Field(default_factory=list, max_length=len(OCULTABLES))
    avisos_correo: bool = False

    def limpios(self) -> "Ajustes":
        self.listas_ocultas = [v for v in OCULTABLES if v in set(self.listas_ocultas)]
        return self


async def leer(db, user: str) -> Ajustes:
    fila = await db.fetchrow(
        "SELECT avisos_correo, ajustes FROM task_preferencias WHERE user_email = $1",
        user,
    )
    if fila is None:
        return Ajustes()
    guardados = fila["ajustes"]
    if isinstance(guardados, str):
        guardados = json.loads(guardados)
    conocidos = {
        k: v for k, v in (guardados or {}).items() if k in Ajustes.model_fields
    }
    conocidos["avisos_correo"] = bool(fila["avisos_correo"])
    try:
        return Ajustes(**conocidos).limpios()
    except ValueError:  # un valor guardado ya no es válido: se vuelve a lo de fábrica
        return Ajustes(avisos_correo=bool(fila["avisos_correo"]))


async def guardar(db, user: str, ajustes: Ajustes) -> Ajustes:
    ajustes = ajustes.limpios()
    await avisos_listas.guardar_preferencia(db, user, ajustes.avisos_correo)
    await db.execute(
        "UPDATE task_preferencias SET ajustes = $2::jsonb, cambiado_en = NOW() WHERE user_email = $1",
        user,
        json.dumps(ajustes.model_dump(exclude={"avisos_correo"})),
    )
    return ajustes
