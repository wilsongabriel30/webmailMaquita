"""Asistente «Nuevo dominio» (panel → Hospedaje → Nuevo dominio).

Con el dominio y el nombre de la institución deja listo, en un paso:
1. el dominio de correo en este servidor (acepta y envía correo),
2. su clave DKIM y la zona DNS completa (NS propios con sus IP, A, www, mail, MX, SPF, DKIM, DMARC,
   TLS-RPT, autoconfiguración de clientes y CAA),
3. el sitio web con la página «en construcción» con el nombre de la institución.
El primer buzón y el alias postmaster@ los crea la pantalla con las rutas de Buzones y Alias.
Cada paso es idempotente: si el dominio, la zona o el sitio ya existen, se respetan y se informa.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.dns.ayudante import auditar, ayudante, b64
from app.dns.router import _zona

router = APIRouter(prefix="/api/dominio-nuevo", tags=["dns"])


class NuevoDominio(BaseModel):
    dominio: str
    nombre: str
    con_web: bool = True


@router.post("")
async def crear(body: NuevoDominio, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _zona(body.dominio.removeprefix("www."))
    nombre = (body.nombre or "").strip()
    if not 2 <= len(nombre) <= 100 or any(c in nombre for c in "<>"):
        raise HTTPException(400, "Escriba el nombre de la institución (2 a 100 caracteres, sin < ni >)")
    pasos = []

    db = r.app.state.db
    existe = await db.fetchval("SELECT 1 FROM domain WHERE domain = $1", dominio)
    if existe:
        pasos.append({"paso": "correo", "estado": "ya existía"})
    else:
        await db.execute(
            "INSERT INTO domain (domain, description, aliases, mailboxes, maxquota, quota, active) "
            "VALUES ($1, $2, 0, 0, 0, 0, true)",
            dominio,
            nombre,
        )
        pasos.append({"paso": "correo", "estado": "creado"})

    zonas = {z["zona"] for z in (await ayudante("dns", "listar"))["zonas"]}
    if dominio in zonas:
        pasos.append({"paso": "dns", "estado": "ya existía"})
    else:
        await ayudante("dns", "crear", dominio, *([] if body.con_web else ["sin-web"]))
        pasos.append({"paso": "dns", "estado": "creado"})

    if body.con_web:
        try:
            sitios = {s["dominio"] for s in (await ayudante("sitios", "listar"))["sitios"]}
        except HTTPException as e:
            if e.status_code != 503:
                raise
            sitios = None
        if sitios is None:
            pasos.append({"paso": "web", "estado": "no instalado (instalar-app.sh sitios)"})
        elif dominio in sitios:
            pasos.append({"paso": "web", "estado": "ya existía"})
        else:
            await ayudante("sitios", "crear", dominio, "con-www", b64(nombre))
            pasos.append({"paso": "web", "estado": "creado"})

    zona = await ayudante("dns", "ver", dominio)
    servidor = await ayudante("dns", "servidor-ver")
    await auditar(r, admin, "dominio_nuevo", dominio, {"nombre": nombre, "pasos": pasos})
    return {
        "dominio": dominio,
        "pasos": pasos,
        "registrador": [{"servidor": f"{n['nombre']}.{dominio}", "ip": n["ip"]} for n in servidor.get("ns", [])],
        "registros": zona["registros"],
    }
