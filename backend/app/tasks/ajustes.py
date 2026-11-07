"""Configuración personal de Tareas (la ⚙ de la barra, como en To Do; F6 29/10/2026).

Va en `task_preferencias.ajustes` (JSONB) junto a `avisos_correo` (F4), que se muestra en el mismo diálogo.
Las claves que falten toman su valor por defecto y las desconocidas se ignoran.

Al guardar solo se tocan las opciones que cambiaron (05/11/2026): «Avisos por correo» también se cambia desde
«Compartir lista», y antes la ⚙ reenviaba su copia vieja y lo desactivaba sin aviso; lo mismo entre dos pestañas.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.tasks import avisos_listas

# Listas inteligentes que se pueden ocultar (Mi día y Tareas siempre se ven). «Asignado a mí» tampoco se oculta
# desde el 05/11/2026: ahí llegan también las tareas de Seguimiento y ocultarla dejaría a la persona sin verlas.
OCULTABLES = ("important", "planned", "flagged")


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


class CambioAjustes(BaseModel):
    """Solo las opciones que cambian; las que no vienen (o vienen nulas) quedan como estaban."""

    confirmar_eliminar: bool | None = None
    importantes_arriba: bool | None = None
    sonido_completar: bool | None = None
    listas_ocultas: list[str] | None = Field(default=None, max_length=len(OCULTABLES))
    avisos_correo: bool | None = None


async def cambiar(db, user: str, cambio: CambioAjustes) -> Ajustes:
    datos = cambio.model_dump(exclude_none=True)
    avisos_correo = datos.pop("avisos_correo", None)
    if "listas_ocultas" in datos:
        datos["listas_ocultas"] = [
            v for v in OCULTABLES if v in set(datos["listas_ocultas"])
        ]
    # `||` une el JSONB guardado con lo nuevo en una sola sentencia: dos cambios a la vez no se pisan.
    await db.execute(
        """INSERT INTO task_preferencias (user_email, ajustes) VALUES ($1, $2::jsonb)
           ON CONFLICT (user_email) DO UPDATE
           SET ajustes = task_preferencias.ajustes || EXCLUDED.ajustes, cambiado_en = NOW()""",
        user,
        json.dumps(datos),
    )
    if avisos_correo is not None:
        await avisos_listas.guardar_preferencia(db, user, avisos_correo)
    return await leer(db, user)
