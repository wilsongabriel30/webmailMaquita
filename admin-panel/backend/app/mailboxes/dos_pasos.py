"""Verificación en dos pasos de cada buzón, para la lista de buzones del panel.

De dónde sale el dato: el webmail guarda el segundo factor en `user_totp`. La fila se crea al
empezar la activación (`enabled = FALSE`) y solo pasa a `enabled = TRUE`, con `verified_at`,
cuando la persona confirma el primer código. Aquí «activa» es `enabled = TRUE`: una activación
empezada y sin confirmar cuenta como «sin activar».

Obligadas: las cuentas privilegiadas del webmail (`TOTP_OBLIGATORIO`, por omisión `admin` y
`postmaster`) no pueden usar el correo sin ella. La política general («exigida a todas» y su
fecha límite) está en `security_config` y se informa aparte en el resumen.

Una sola consulta con LEFT JOIN para la lista y otra agregada para el recuento.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])

FILTROS = ("todas", "con", "sin")

_ACTIVA = "COALESCE(t.enabled, FALSE)"
_OBLIGADA = (
    "(lower(m.local_part) = ANY($1::text[]) OR lower(m.username) = ANY($2::text[]))"
)
_DESDE = "FROM mailbox m LEFT JOIN user_totp t ON t.username = m.username"
_COLUMNAS = (
    "m.username, m.name, m.domain, m.quota, m.active, m.local_part, m.phone, m.email_other, "
    f"m.created, m.modified, {_ACTIVA} AS dos_pasos, "
    f"CASE WHEN {_ACTIVA} THEN t.verified_at END AS dos_pasos_desde, "
    f"{_OBLIGADA} AS dos_pasos_obligatoria"
)


def reglas_obligatorias(politica: str | None = None) -> tuple[list[str], list[str]]:
    """Partes locales y direcciones completas obligadas, con el mismo criterio que el webmail
    (`cuenta_privilegiada`): lista separada por comas, en minúsculas."""
    if politica is None:
        politica = os.getenv("WEBMAIL_TOTP_OBLIGATORIO")
    if politica is None:
        politica = os.getenv("TOTP_OBLIGATORIO", "admin,postmaster")
    reglas = [r.strip().lower() for r in politica.split(",") if r.strip()]
    return [r for r in reglas if "@" not in r], [r for r in reglas if "@" in r]


def validar_filtro(valor: str | None) -> str:
    filtro = (valor or "todas").strip().lower()
    if filtro not in FILTROS:
        raise HTTPException(
            400,
            "Filtro de verificación en dos pasos no válido: use «todas», «con» o «sin».",
        )
    return filtro


async def listar(
    db, dominio: str | None = None, dos_pasos: str | None = None
) -> list[dict]:
    """Buzones con su estado de verificación en dos pasos, filtrados por dominio y por estado."""
    filtro = validar_filtro(dos_pasos)
    locales, direcciones = reglas_obligatorias()
    args: list = [locales, direcciones]
    condiciones = []
    if dominio:
        args.append(dominio)
        condiciones.append(f"m.domain = ${len(args)}")
    if filtro == "con":
        condiciones.append(_ACTIVA)
    elif filtro == "sin":
        condiciones.append(f"NOT {_ACTIVA}")
    donde = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    orden = "m.username" if dominio else "m.domain, m.username"
    # Solo se interpolan fragmentos fijos de este módulo; los valores van como parámetros.
    filas = await db.fetch(
        f"SELECT {_COLUMNAS} {_DESDE}{donde} ORDER BY {orden}", *args
    )  # nosec B608
    return [dict(f) for f in filas]


async def resumen(db) -> dict:
    """Recuento sobre las cuentas activas: cuántas la tienen, cuántas no y cuántas obligadas faltan."""
    locales, direcciones = reglas_obligatorias()
    fila = await db.fetchrow(
        f"""SELECT count(*) FILTER (WHERE m.active) AS cuentas_activas,
                   count(*) FILTER (WHERE m.active AND {_ACTIVA}) AS con_dos_pasos,
                   count(*) FILTER (WHERE m.active AND {_OBLIGADA}) AS obligadas,
                   count(*) FILTER (WHERE m.active AND {_OBLIGADA} AND NOT {_ACTIVA}) AS obligadas_sin_activar
            {_DESDE}""",  # nosec B608
        locales,
        direcciones,
    )
    activas = int(fila["cuentas_activas"] or 0) if fila else 0
    con = int(fila["con_dos_pasos"] or 0) if fila else 0
    return {
        "cuentas_activas": activas,
        "con_dos_pasos": con,
        "sin_dos_pasos": activas - con,
        "obligadas": int(fila["obligadas"] or 0) if fila else 0,
        "obligadas_sin_activar": int(fila["obligadas_sin_activar"] or 0) if fila else 0,
        **await _politica_general(db),
    }


async def _politica_general(db) -> dict:
    """«Exigida a todas» y su fecha límite (Políticas de seguridad). Sin la tabla: no exigida."""
    try:
        fila = await db.fetchrow(
            "SELECT COALESCE(totp_required, FALSE) AS exigida, totp_deadline FROM security_config WHERE id = 1"
        )
    except Exception:
        fila = None
    limite = fila["totp_deadline"] if fila else None
    return {
        "exigida_a_todas": bool(fila and fila["exigida"]),
        "fecha_limite": limite.isoformat() if limite else None,
    }


@router.get("/dos-pasos/resumen")
async def resumen_dos_pasos(request: Request, admin: dict = Depends(get_current_admin)):
    return await resumen(request.app.state.db)
