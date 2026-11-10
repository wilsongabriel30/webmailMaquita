"""Modelos de la respuesta automática y de las reglas de correo (Sieve).

Reglas avanzadas (10/11/2026): varias condiciones («todas» o «alguna»), negaciones, cuerpo,
tamaño, encabezado a elegir, expresiones regulares; varias acciones por regla (mover, copiar,
marcar, marcar como leído, eliminar, reenviar, reenviar copia) y «detener» opcional.

Compatibilidad: el cliente antiguo manda `condition` y `action` en singular; se aceptan y se
convierten en listas de un elemento. En la salida siempre van también `condition` y `action`
(la primera condición y la primera acción) para quien aún los lea.
"""

import re
from typing import Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.sieve.escapado import sanear

# La bandera IMAP «con bandera», tal y como la entiende Sieve (una sola barra).
BANDERA_POR_DEFECTO = "\\Flagged"

_CORREO = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_NOMBRE_ENCABEZADO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")

MAX_CONDICIONES = 10
MAX_ACCIONES = 5

CAMPOS = ("from", "to", "cc", "recipients", "subject", "body", "header", "size", "list")
OPERADORES = (
    "contains",
    "is",
    "matches",
    "regex",
    "not_contains",
    "not_is",
    "not_matches",
    "not_regex",
    "exists",
    "not_exists",
    "over",
    "under",
)
ACCIONES = ("move", "copy", "flag", "read", "delete", "forward", "forward_copy")

# Operadores válidos por campo.
_OPERADORES_POR_CAMPO = {
    "size": {"over", "under"},
    "body": {"contains", "not_contains", "regex", "not_regex"},
}
_OPERADORES_ENCABEZADO = set(OPERADORES) - {"over", "under"}


class VacationSettings(BaseModel):
    enabled: bool = False
    subject: str = ""
    body: str = ""
    start_date: Optional[str] = None  # ISO date YYYY-MM-DD
    end_date: Optional[str] = None


class FilterCondition(BaseModel):
    field: str = Field(..., pattern="^(" + "|".join(CAMPOS) + ")$")
    operator: str = Field(..., pattern="^(" + "|".join(OPERADORES) + ")$")
    value: str = ""
    # Nombre del encabezado cuando field == "header" (p. ej. X-Mailer, List-Id, Reply-To).
    header: Optional[str] = None

    @model_validator(mode="after")
    def _coherente(self):
        permitidos = _OPERADORES_POR_CAMPO.get(self.field, _OPERADORES_ENCABEZADO)
        if self.operator not in permitidos:
            raise ValueError(
                f"el operador «{self.operator}» no vale para el campo «{self.field}»"
            )
        if self.field == "header":
            nombre = (self.header or "").strip()
            if not _NOMBRE_ENCABEZADO.match(nombre):
                raise ValueError("el nombre del encabezado no es válido")
            self.header = nombre
        else:
            self.header = None
        if self.field == "size":
            if not self.value.strip().isdigit() or int(self.value) <= 0:
                raise ValueError("el tamaño debe ser un número de KB mayor que cero")
            self.value = str(int(self.value))
        elif self.operator in ("exists", "not_exists"):
            self.value = ""
        elif not sanear(self.value).strip():
            raise ValueError("la condición necesita un valor")
        return self


class FilterAction(BaseModel):
    type: str = Field(..., pattern="^(" + "|".join(ACCIONES) + ")$")
    value: Optional[str] = None


class FilterRule(BaseModel):
    name: str
    match: str = Field("allof", pattern="^(allof|anyof)$")
    conditions: list[FilterCondition] = []
    actions: list[FilterAction] = []
    # Detener las reglas siguientes cuando esta se cumple. Si no se indica: sí, salvo que la
    # regla solo marque (la bandera no debe impedir que otra regla mueva el correo).
    stop: Optional[bool] = None
    enabled: bool = True
    # Forma antigua (una condición y una acción). Se rellenan siempre en la salida.
    condition: Optional[FilterCondition] = None
    action: Optional[FilterAction] = None

    @model_validator(mode="after")
    def _normalizar_listas(self):
        if not self.conditions and self.condition is not None:
            self.conditions = [self.condition]
        if not self.actions and self.action is not None:
            self.actions = [self.action]
        if not self.conditions:
            raise ValueError("la regla necesita al menos una condición")
        if not self.actions:
            raise ValueError("la regla necesita al menos una acción")
        if len(self.conditions) > MAX_CONDICIONES:
            raise ValueError(f"máximo {MAX_CONDICIONES} condiciones por regla")
        if len(self.actions) > MAX_ACCIONES:
            raise ValueError(f"máximo {MAX_ACCIONES} acciones por regla")
        if self.stop is None:
            self.stop = any(a.type not in ("flag", "read") for a in self.actions)
        self.condition = self.conditions[0]
        self.action = self.actions[0]
        return self


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
