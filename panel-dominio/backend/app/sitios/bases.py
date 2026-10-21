"""Bases de datos adicionales del sitio (MariaDB o PostgreSQL) y entrada a phpMyAdmin o Adminer
con un usuario temporal. La cuota de bases del dominio la aplica el intermediario (409)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{sitio}/bases")
async def ver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "bases", sitio)


@router.post("/{sitio}/bases", status_code=201)
async def crear(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """La contraseña de la base nueva vuelve una sola vez."""
    sitio, _ = exigir_sitio(admin, sitio)
    motor = str((await cuerpo(request)).get("motor") or "")
    if motor not in ("mariadb", "postgresql"):
        raise HTTPException(400, "Motor no disponible")
    return await llamar(request, admin, "base-crear", sitio, {"motor": motor}, "sitio_base_crear", {"motor": motor})


@router.post("/{sitio}/bases/{base}/entrar")
async def entrar(sitio: str, base: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    base = v.con_forma(v.RE_BASE, base, "Base de datos no válida")
    herramienta = str((await cuerpo(request)).get("herramienta") or "")
    if herramienta not in ("phpmyadmin", "adminer"):
        raise HTTPException(400, "Herramienta no válida")
    return await llamar(request, admin, "base-entrar", sitio, {"base": base, "herramienta": herramienta},
                        "sitio_base_entrar", {"base": base, "herramienta": herramienta})


@router.delete("/{sitio}/bases/{base}")
async def borrar(sitio: str, base: str, request: Request, admin: dict = Depends(admin_actual)):
    """Antes de borrarla se guarda una copia (.sql) en la carpeta privada del sitio."""
    sitio, _ = exigir_sitio(admin, sitio)
    base = v.con_forma(v.RE_BASE_ADICIONAL, base, "Solo se pueden borrar las bases adicionales")
    return await llamar(request, admin, "base-borrar", sitio, {"base": base}, "sitio_base_borrar", {"base": base})
