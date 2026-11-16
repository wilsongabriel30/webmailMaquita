"""Política de este servidor ante un pedido de retirada que llega de OTRO servidor.

Entre organizaciones distintas decide el servidor del destinatario (acordado con otra instalación
de la suite tras la prueba cruzada del 16/11/2026):

- Por defecto NO se retira un correo que el destinatario ya leyó: el servidor que lo pidió recibe
  «leido_no_retirado» y le envía el aviso de «enviado por error», como a cualquier externo.
- Cada instalación puede permitirlo para todos o solo para una lista de dominios de confianza.
  Se administra desde el panel (Seguridad → «Recuperación entre servidores», tabla
  `federacion_recuperacion_politica`) y rige en la siguiente solicitud, sin reiniciar. Mientras no
  se guarde nada desde el panel valen `RECALL_FEDERADO_RETIRAR_LEIDOS` y
  `RECALL_FEDERADO_DOMINIOS_CONFIANZA` del `.env`.

Dentro de una misma instalación la recuperación no pasa por aquí y sigue como estaba.
"""

from __future__ import annotations

from app.config import get_settings


def dominios_de_confianza() -> set[str]:
    crudo = getattr(get_settings(), "recall_federado_dominios_confianza", "") or ""
    return {d.strip().lower().lstrip("@") for d in crudo.split(",") if d.strip()}


def permite_retirar_leido(dominio_solicitante: str) -> bool:
    """¿Se retira un correo ya leído cuando lo pide el servidor de este dominio?"""
    if bool(getattr(get_settings(), "recall_federado_retirar_leidos", False)):
        return True
    return (dominio_solicitante or "").strip().lower() in dominios_de_confianza()


async def _del_panel(db):
    """Fila guardada desde el panel, o None si no hay (o la tabla aún no existe)."""
    try:
        return await db.fetchrow(
            "SELECT retirar_leidos, dominios_confianza FROM federacion_recuperacion_politica WHERE id = 1"
        )
    except Exception:
        return None


async def permitido(db, dominio_solicitante: str) -> bool:
    """Decisión vigente: lo guardado desde el panel manda; si no hay nada, el `.env`."""
    fila = await _del_panel(db)
    if fila is None:
        return permite_retirar_leido(dominio_solicitante)
    if bool(fila["retirar_leidos"]):
        return True
    confianza = {(d or "").strip().lower() for d in fila["dominios_confianza"] or []}
    return (dominio_solicitante or "").strip().lower() in confianza
