"""Inventario de aplicaciones y aviso de apps de riesgo (fase 4).

El teléfono envía la lista de apps con firma, origen de instalación y permisos peligrosos; el
servidor la cruza con las reglas de Tecnología (lista de bloqueo, instaladores de confianza, permisos
de riesgo) y devuelve, para las que corresponda, un aviso con la acción y un texto amable. Con
control completo la app puede bloquear o desinstalar en silencio; en modo limitado solo avisa.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.dispositivos.seguridad import equipo_actual, limitar

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_PAQUETE = re.compile(r"^[A-Za-z0-9_.]{1,255}$")


class App(BaseModel):
    paquete: str = Field(..., max_length=255)
    nombre: Optional[str] = Field(None, max_length=255)
    version: Optional[str] = Field(None, max_length=80)
    instalador: Optional[str] = Field(None, max_length=120)
    firma_sha256: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")
    permisos: list[str] = Field(default_factory=list, max_length=80)
    sistema: bool = False


class Inventario(BaseModel):
    apps: list[App] = Field(..., min_length=1, max_length=1000)


def _texto_aviso(nombre: str, nota: str | None) -> str:
    base = f"Seguridad Maquita detectó en este teléfono una aplicación que puede poner en riesgo tu información: {nombre}."
    if nota:
        base += f" Motivo: {nota}."
    return (
        base
        + " Por favor, tócala para desinstalarla. Si crees que es un error, escribe a Tecnología."
    )


async def _reglas(db) -> dict:
    filas = await db.fetch(
        "SELECT tipo, lower(valor) AS valor, accion, nota FROM disp_apps_reglas"
    )
    r = {"paquete": {}, "firma": {}, "permiso": {}, "instalador": {}}
    for f in filas:
        r[f["tipo"]][f["valor"]] = (f["accion"], f["nota"])
    return r


def _evaluar(app: App, reglas: dict) -> tuple[str, str, str | None]:
    """Devuelve (veredicto, accion, motivo). Una regla de bloqueo manda sobre todo."""
    inst = (app.instalador or "").lower()
    for clave, (accion, nota) in (
        (
            (app.paquete.lower(), reglas["paquete"].get(app.paquete.lower()))
            if app.paquete.lower() in reglas["paquete"]
            else (None, (None, None))
        ),
    ):
        if accion == "bloquear":
            return "bloqueada", "desinstalar", nota or "En la lista de bloqueo"
        if accion == "permitir":
            return "ok", "ninguna", None
    if app.firma_sha256 and app.firma_sha256 in reglas["firma"]:
        accion, nota = reglas["firma"][app.firma_sha256]
        if accion == "bloquear":
            return "bloqueada", "desinstalar", nota or "Firma en la lista de bloqueo"
    if app.sistema:
        return "ok", "ninguna", None
    # Instalador de confianza: se acepta salvo que una regla de paquete/firma lo haya bloqueado antes.
    if inst and reglas["instalador"].get(inst, (None,))[0] == "permitir":
        return "ok", "ninguna", None
    motivos = []
    for permiso in app.permisos:
        r = reglas["permiso"].get(permiso.lower())
        if r and r[0] in ("avisar", "bloquear"):
            motivos.append(r[1] or permiso)
    # App de fuera de una tienda conocida: señal de riesgo.
    conocidos = {k for k, v in reglas["instalador"].items() if v[0] == "permitir"}
    if (
        inst
        and inst not in conocidos
        and inst
        not in ("com.google.android.packageinstaller", "com.android.packageinstaller")
    ):
        motivos.append("Instalada desde fuera de una tienda de confianza")
    elif not inst:
        motivos.append("Origen de instalación desconocido")
    if motivos:
        return "sospechosa", "avisar", "; ".join(dict.fromkeys(motivos))[:255]
    return "ok", "ninguna", None


@router.post("/apps")
async def inventario(
    request: Request, body: Inventario, equipo: dict = Depends(equipo_actual)
):
    await limitar(request, f"apps:{equipo['id']}", 20, 3600)
    db = request.app.state.db_pool
    reglas = await _reglas(db)
    avisos, nuevas_riesgo = [], 0
    async with db.acquire() as con, con.transaction():
        vistos = [a.paquete for a in body.apps if _PAQUETE.match(a.paquete)]
        previas = {
            r["paquete"]: r["veredicto"]
            for r in await con.fetch(
                "SELECT paquete, veredicto FROM disp_apps WHERE equipo_id = $1",
                equipo["id"],
            )
        }
        for app in body.apps:
            if not _PAQUETE.match(app.paquete):
                continue
            veredicto, accion, motivo = _evaluar(app, reglas)
            await con.execute(
                """INSERT INTO disp_apps (equipo_id, paquete, nombre, version, instalador, firma_sha256, permisos, sistema, veredicto, motivo, vista_en)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10, NOW())
                   ON CONFLICT (equipo_id, paquete) DO UPDATE SET nombre=EXCLUDED.nombre, version=EXCLUDED.version,
                       instalador=EXCLUDED.instalador, firma_sha256=EXCLUDED.firma_sha256, permisos=EXCLUDED.permisos,
                       sistema=EXCLUDED.sistema, veredicto=EXCLUDED.veredicto, motivo=EXCLUDED.motivo, vista_en=NOW()""",
                equipo["id"],
                app.paquete,
                app.nombre,
                app.version,
                app.instalador,
                app.firma_sha256,
                json.dumps(app.permisos[:80]),
                app.sistema,
                veredicto,
                motivo,
            )
            if veredicto != "ok":
                if previas.get(app.paquete) in (None, "ok"):
                    nuevas_riesgo += 1
                # En modo limitado nunca se desinstala en silencio: como mucho se avisa.
                if accion == "desinstalar" and equipo.get("modo") != "propietario":
                    accion = "avisar"
                avisos.append(
                    {
                        "paquete": app.paquete,
                        "veredicto": veredicto,
                        "accion": accion,
                        "texto": _texto_aviso(app.nombre or app.paquete, motivo),
                    }
                )
        # Apps que ya no están: se olvidan (nunca si el lote no trajo ningún paquete válido).
        if vistos:
            await con.execute(
                "DELETE FROM disp_apps WHERE equipo_id = $1 AND paquete <> ALL($2::text[])",
                equipo["id"],
                vistos,
            )
        if nuevas_riesgo:
            await con.execute(
                "INSERT INTO disp_eventos (equipo_id, tipo, detalle) VALUES ($1, 'app_riesgo', $2::jsonb)",
                equipo["id"],
                json.dumps(
                    {"nuevas": nuevas_riesgo, "avisos": [a["paquete"] for a in avisos]}
                ),
            )
            logger.warning(
                "apps_de_riesgo | equipo=%s | nuevas=%d", equipo["id"], nuevas_riesgo
            )
    return {"avisos": avisos}
