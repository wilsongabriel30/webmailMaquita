"""Modelos de las reglas de correo y de la respuesta automática (API y script Sieve)."""

import re
from typing import Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.sieve.escapado import sanear

# La bandera IMAP «con bandera», tal y como la entiende Sieve (una sola barra).
BANDERA_POR_DEFECTO = "\\Flagged"

_CORREO = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class VacationSettings(BaseModel):
    enabled: bool = False
    subject: str = ""
    body: str = ""
    start_date: Optional[str] = None  # ISO date YYYY-MM-DD
    end_date: Optional[str] = None


class FilterCondition(BaseModel):
    field: str = Field(..., pattern="^(from|to|subject)$")
    operator: str = Field(..., pattern="^(contains|is|matches)$")
    value: str


class FilterAction(BaseModel):
    type: str = Field(..., pattern="^(move|flag|delete|forward)$")
    value: Optional[str] = None


class FilterRule(BaseModel):
    name: str
    condition: FilterCondition
    action: FilterAction


class FilterRuleOut(FilterRule):
    index: int


def validar_correo_reenvio(direccion: str) -> str:
    """La dirección de reenvío saneada, o 422 si no tiene forma de correo."""
    direccion = sanear(direccion)
    if not _CORREO.match(direccion):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dirección de reenvío inválida: {direccion}",
        )
    return direccion


def bandera_canonica(valor: Optional[str]) -> str:
    """La bandera con UNA barra inicial (`\\Flagged`), venga como venga del cliente.

    El cliente antiguo mandaba `\\\\Flagged` (dos barras, que antes se copiaban tal cual al
    script); al escapar correctamente eso daría cuatro barras y una bandera inexistente.
    """
    limpio = sanear(valor or "").lstrip("\\")
    return "\\" + (limpio or BANDERA_POR_DEFECTO.lstrip("\\"))
