"""Política de este servidor ante un pedido de retirada que llega de OTRO servidor.

Entre organizaciones distintas decide el servidor del destinatario (acordado con otra instalación
de la suite tras la prueba cruzada del 16/11/2026):

- Por defecto NO se retira un correo que el destinatario ya leyó: el servidor que lo pidió recibe
  «leido_no_retirado» y le envía el aviso de «enviado por error», como a cualquier externo.
- Cada instalación puede permitirlo para todos (`RECALL_FEDERADO_RETIRAR_LEIDOS=true`) o solo para
  una lista de dominios de confianza (`RECALL_FEDERADO_DOMINIOS_CONFIANZA`).

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
