"""Quién puede pedir respaldo y con qué cliente UrBackup.

Reglas (contrato T-74):
- Solo cuentas de persona: buzón activo, que no sea un buzón compartido (`mail_delegation`) ni esté
  marcado `habilitado = false` en `respaldos_vinculos`.
- Un `machine_guid` ya vinculado a otra persona → conflicto (lo decide soporte).
- Con vínculo cargado: el primer equipo usa SU cliente de siempre (misma clave, mismo nombre); un
  segundo equipo de la misma persona → cliente nuevo `NombreApellido-2`.
- Sin vínculo: no se crea nada mientras soporte no haya cargado la tabla, salvo que
  `RESPALDOS_ALTA_SIN_VINCULO=true` (organizacion.env). Así no nacen duplicados de los clientes actuales.
"""

from __future__ import annotations

import re
import unicodedata

from app import organizacion


class CuentaNoHabilitada(Exception):
    pass


class EquipoDeOtraPersona(Exception):
    pass


def _limpio(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", t)


def nombre_base(nombre: str, user_email: str) -> str:
    """`NombreApellido` desde la ficha del buzón: primer nombre + primer apellido, sin tildes ni espacios.
    Con 4 palabras o más se asume «Nombre1 Nombre2 Apellido1 Apellido2»; con 2-3, «Nombre Apellido…».
    """
    partes = [p for p in (nombre or "").split() if _limpio(p)]
    if len(partes) >= 4:
        elegidas = [partes[0], partes[2]]
    elif len(partes) >= 2:
        elegidas = partes[:2]
    else:
        elegidas = partes or [user_email.split("@")[0]]
    base = "".join(_limpio(p).capitalize() for p in elegidas)
    return (base or "Equipo")[:60]


async def comprobar_cuenta(db, user_email: str) -> dict:
    fila = await db.fetchrow(
        "SELECT name FROM mailbox WHERE username = $1 AND active", user_email
    )
    if fila is None:
        raise CuentaNoHabilitada("buzón inexistente o inactivo")
    if await db.fetchval(
        "SELECT 1 FROM mail_delegation WHERE mailbox = $1 LIMIT 1", user_email
    ):
        raise CuentaNoHabilitada("buzón compartido")
    v = await db.fetchrow(
        "SELECT clientid, cliente, habilitado FROM respaldos_vinculos WHERE user_email = $1",
        user_email,
    )
    if v is not None and not v["habilitado"]:
        raise CuentaNoHabilitada("cuenta excluida de respaldos")
    return {"nombre": fila["name"] or "", "vinculo": v}


async def _clientes_de(db, user_email: str) -> set[int]:
    filas = await db.fetch(
        "SELECT clientid FROM respaldos_vinculos WHERE user_email = $1 AND clientid IS NOT NULL "
        "UNION SELECT clientid FROM respaldos_equipos WHERE user_email = $1 AND clientid IS NOT NULL",
        user_email,
    )
    return {f["clientid"] for f in filas}


async def _nombre_libre(db, base: str, desde: int) -> str:
    usados = {
        (f["cliente"] or "").lower()
        for f in await db.fetch(
            "SELECT cliente FROM respaldos_vinculos UNION SELECT cliente FROM respaldos_equipos "
            "UNION SELECT cliente FROM respaldos_codigos WHERE usado_en IS NULL AND anulado_en IS NULL "
            "AND caduca_en > NOW()"
        )
    }
    n = desde
    while True:
        nombre = base if n == 1 else f"{base}-{n}"
        if nombre.lower() not in usados:
            return nombre
        n += 1


async def decidir_cliente(db, user_email: str, machine_guid: str, cuenta: dict) -> dict:
    """{'clientid', 'cliente', 'nuevo'} para este equipo, o una de las excepciones de arriba."""
    eq = await db.fetchrow(
        "SELECT user_email, clientid, cliente FROM respaldos_equipos WHERE machine_guid = $1",
        machine_guid,
    )
    propios = await _clientes_de(db, user_email)
    if eq is not None:
        if eq["user_email"] != user_email and eq["clientid"] not in propios:
            raise EquipoDeOtraPersona(eq["user_email"])
        return {"clientid": eq["clientid"], "cliente": eq["cliente"], "nuevo": False}

    v = cuenta["vinculo"]
    base = nombre_base(cuenta["nombre"], user_email)
    if v is not None and v["clientid"] is not None:
        ocupado = await db.fetchval(
            "SELECT 1 FROM respaldos_equipos WHERE clientid = $1 AND machine_guid <> $2 LIMIT 1",
            v["clientid"],
            machine_guid,
        )
        if not ocupado:
            return {"clientid": v["clientid"], "cliente": v["cliente"], "nuevo": False}
        return {
            "clientid": None,
            "cliente": await _nombre_libre(db, base, 2),
            "nuevo": True,
        }

    if organizacion.valor("RESPALDOS_ALTA_SIN_VINCULO", "false").lower() != "true":
        raise CuentaNoHabilitada("sin vínculo cargado por soporte")
    return {
        "clientid": None,
        "cliente": await _nombre_libre(db, base, 1),
        "nuevo": True,
    }
