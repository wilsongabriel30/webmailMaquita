"""Portales por empresa: qué nombre de servidor pertenece a qué dominio, y la marca
(nombre, colores, logo, icono) que ve cada empresa en su pantalla de entrada.

Las tablas `portal_empresa` y `branding_empresa` las creó la migración
2026-09-14-portales-por-empresa.sql del webmail. El webmail solo las LEE
(app/portales/resolucion.py y app/branding/router.py); este panel es quien las ESCRIBE.
Lo que una empresa no defina se hereda de la marca general (pantalla Personalización).

Dar de alta un portal aquí NO lo publica en internet: además hacen falta el registro DNS
del nombre, el certificado y el bloque de nginx. La pantalla lo explica.
"""

import json
import logging
import os
import re
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/portales", tags=["portales"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = "/opt/maquita-webmail/uploads/branding/empresas"

# Mismas claves que la marca general. Lo que no esté aquí no se guarda.
CLAVES_MARCA = (
    "org_name",
    "org_slogan",
    "org_email",
    "org_website",
    "org_phone",
    "primary_color",
    "footer_text",
)
TIPOS_ARCHIVO = ("favicon", "logo")
_HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_BYTES = 2 * 1024 * 1024


def _db(r: Request):
    return r.app.state.db


async def _audit(r: Request, admin: dict, action: str, target: str, details: dict | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], action, target,
        json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


def _dominio_seguro(dominio: str) -> str:
    d = os.path.basename(dominio.strip().lower())
    if not _HOST_RE.match(d):
        raise HTTPException(400, "Dominio inválido")
    return d


def _archivos(dominio: str) -> dict:
    """URLs del logo e icono propios, si existen."""
    urls = {}
    for tipo in TIPOS_ARCHIVO:
        carpeta = os.path.join(UPLOAD_DIR, dominio, tipo)
        if os.path.isdir(carpeta):
            nombres = sorted(os.listdir(carpeta))
            if nombres:
                urls[f"{tipo}_url"] = f"/api/portales/marca/{dominio}/file/{tipo}/{nombres[0]}"
    return urls


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    """Todos los dominios del servidor con sus portales y su marca propia."""
    db = _db(request)
    dominios = await db.fetch("SELECT domain, active FROM domain ORDER BY domain")
    portales = await db.fetch(
        "SELECT host, dominio, activo, creado_en FROM portal_empresa ORDER BY host"
    )
    marcas = await db.fetch("SELECT dominio, clave, valor FROM branding_empresa")

    por_dominio: dict[str, dict] = {}
    for d in dominios:
        por_dominio[d["domain"]] = {
            "dominio": d["domain"],
            "activo": d["active"],
            "portales": [],
            "marca": {},
            **_archivos(d["domain"]),
        }
    for p in portales:
        if p["dominio"] in por_dominio:
            por_dominio[p["dominio"]]["portales"].append(
                {"host": p["host"], "activo": p["activo"], "creado_en": p["creado_en"]}
            )
    for m in marcas:
        if m["dominio"] in por_dominio and m["clave"] in CLAVES_MARCA and m["valor"]:
            por_dominio[m["dominio"]]["marca"][m["clave"]] = m["valor"]
    return list(por_dominio.values())


@router.post("/hosts", status_code=201)
async def crear_host(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    host = str(data.get("host", "")).strip().lower().rstrip(".")
    dominio = _dominio_seguro(str(data.get("dominio", "")))
    if not _HOST_RE.match(host):
        raise HTTPException(400, "Nombre de servidor inválido (ejemplo: mail.empresa.com)")
    db = _db(request)
    if not await db.fetchrow("SELECT 1 FROM domain WHERE domain = $1", dominio):
        raise HTTPException(404, "El dominio no existe en el servidor")
    if await db.fetchrow("SELECT 1 FROM portal_empresa WHERE host = $1", host):
        raise HTTPException(409, "Ese nombre de servidor ya está asignado")
    await db.execute(
        "INSERT INTO portal_empresa (host, dominio, activo) VALUES ($1, $2, true)", host, dominio
    )
    await _audit(request, admin, "portal_create", host, {"dominio": dominio})
    return {"host": host, "dominio": dominio, "activo": True}


@router.put("/hosts/{host}")
async def cambiar_host(host: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    activo = bool(data.get("activo", True))
    db = _db(request)
    fila = await db.fetchrow(
        "UPDATE portal_empresa SET activo = $2 WHERE host = $1 RETURNING host, dominio, activo",
        host.strip().lower(), activo,
    )
    if not fila:
        raise HTTPException(404, "Portal no encontrado")
    await _audit(request, admin, "portal_update", host, {"activo": activo})
    return dict(fila)


@router.delete("/hosts/{host}")
async def borrar_host(host: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    fila = await db.fetchrow(
        "DELETE FROM portal_empresa WHERE host = $1 RETURNING dominio", host.strip().lower()
    )
    if not fila:
        raise HTTPException(404, "Portal no encontrado")
    await _audit(request, admin, "portal_delete", host, {"dominio": fila["dominio"]})
    return {"success": True}


@router.put("/marca/{dominio}")
async def guardar_marca(dominio: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Textos y color propios de la empresa. Un valor vacío borra la clave (vuelve a heredar)."""
    dominio = _dominio_seguro(dominio)
    data = await request.json()
    db = _db(request)
    if not await db.fetchrow("SELECT 1 FROM domain WHERE domain = $1", dominio):
        raise HTTPException(404, "El dominio no existe en el servidor")
    cambios = {}
    for clave, valor in data.items():
        if clave not in CLAVES_MARCA:
            continue
        valor = str(valor or "").strip()[:500]
        if clave == "primary_color" and valor and not _COLOR_RE.match(valor):
            raise HTTPException(400, "El color debe ir en formato #RRGGBB")
        if valor:
            await db.execute(
                "INSERT INTO branding_empresa (dominio, clave, valor) VALUES ($1, $2, $3) "
                "ON CONFLICT (dominio, clave) DO UPDATE SET valor = EXCLUDED.valor",
                dominio, clave, valor,
            )
        else:
            await db.execute(
                "DELETE FROM branding_empresa WHERE dominio = $1 AND clave = $2", dominio, clave
            )
        cambios[clave] = valor
    await _audit(request, admin, "portal_marca_update", dominio, cambios)
    return {"success": True}


@router.post("/marca/{dominio}/upload/{tipo}")
async def subir_archivo(
    dominio: str,
    tipo: str,
    request: Request,
    file: UploadFile = File(...),
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    dominio = _dominio_seguro(dominio)
    if tipo not in TIPOS_ARCHIVO:
        raise HTTPException(400, "Tipo debe ser 'favicon' o 'logo'")
    nombre = file.filename or ""
    es_imagen = (file.content_type or "").startswith("image/")
    if not es_imagen and not (tipo == "favicon" and nombre.lower().endswith(".ico")):
        raise HTTPException(400, "Solo se permiten archivos de imagen")
    contenido = await file.read()
    if len(contenido) > _MAX_BYTES:
        raise HTTPException(400, "Archivo demasiado grande (máximo 2 MB)")

    carpeta = os.path.join(UPLOAD_DIR, dominio, tipo)
    os.makedirs(carpeta, mode=0o755, exist_ok=True)
    for viejo in os.listdir(carpeta):
        os.remove(os.path.join(carpeta, viejo))
    ext = os.path.splitext(nombre)[1].lower() or ".png"
    if not re.match(r"^\.[a-z0-9]{2,5}$", ext):
        ext = ".png"
    destino = os.path.join(carpeta, f"{tipo}{ext}")
    with open(destino, "wb") as f:
        f.write(contenido)
    os.chmod(destino, 0o644)  # el webmail (otro usuario) tiene que poder leerlo

    logger.info("Portales: %s de %s subido por %s (%d bytes)", tipo, dominio, admin["username"], len(contenido))
    await _audit(request, admin, "portal_marca_archivo", dominio, {"tipo": tipo, "bytes": len(contenido)})
    return {"success": True, "url": f"/api/portales/marca/{dominio}/file/{tipo}/{tipo}{ext}"}


@router.delete("/marca/{dominio}/file/{tipo}")
async def borrar_archivo(dominio: str, tipo: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    dominio = _dominio_seguro(dominio)
    if tipo not in TIPOS_ARCHIVO:
        raise HTTPException(400)
    carpeta = os.path.join(UPLOAD_DIR, dominio, tipo)
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta)
    await _audit(request, admin, "portal_marca_archivo_borrado", dominio, {"tipo": tipo})
    return {"success": True}


@router.get("/marca/{dominio}/file/{tipo}/{nombre}")
async def ver_archivo(dominio: str, tipo: str, nombre: str):
    """Vista previa en el panel. Es el mismo archivo que el webmail muestra en público."""
    if tipo not in TIPOS_ARCHIVO:
        raise HTTPException(404)
    ruta = os.path.join(UPLOAD_DIR, os.path.basename(dominio), tipo, os.path.basename(nombre))
    if not os.path.isfile(ruta):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(ruta)
