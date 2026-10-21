"""Lista de sitios con las cuotas de cada dominio, catálogo, sitio nuevo y ficha de un sitio."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import config
from app.sitios.comun import NO_ENCONTRADO, cuerpo, exigir_sitio, listar, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


async def bajas_pendientes(request: Request, admin: dict) -> list[dict]:
    filas = await request.app.state.db.fetch(
        """SELECT id, objetivo, dominio, motivo, creado_en FROM pd_solicitudes
            WHERE tipo = 'baja_sitio' AND estado = 'pendiente' AND dominio = ANY($1::varchar[])
            ORDER BY creado_en DESC LIMIT 100""", admin["dominios"])
    return [dict(f) for f in filas]


@router.get("")
async def lista(request: Request, admin: dict = Depends(admin_actual)):
    datos = await listar(request, admin)
    return {"sitios": datos.get("sitios") or [], "dominios": datos.get("dominios") or [],
            "dns": bool(datos.get("dns")), "solicitudes": await bajas_pendientes(request, admin)}


@router.get("/catalogo")
async def catalogo(request: Request, admin: dict = Depends(admin_actual)):
    return await llamar(request, admin, "catalogo")


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    datos = await cuerpo(request)
    sitio, _ = exigir_sitio(admin, str(datos.get("sitio") or "").strip().lower().removeprefix("www."))
    www = bool(datos.get("www", True))
    return await llamar(request, admin, "crear", sitio, {"www": www}, "sitio_crear", {"www": www})


@router.get("/{sitio}/estado")
async def estado(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Lo que necesita la ficha al abrirse, en una sola petición. Lo lento (revisar la aplicación,
    versiones de PHP) lo pide cada pestaña cuando se abre."""
    sitio, dominio = exigir_sitio(admin, sitio)
    datos = await listar(request, admin)
    ficha = next((s for s in datos.get("sitios") or [] if isinstance(s, dict) and s.get("dominio") == sitio), None)
    if ficha is None:
        raise HTTPException(404, NO_ENCONTRADO)
    del_dominio = next((d for d in datos.get("dominios") or [] if isinstance(d, dict) and d.get("dominio") == dominio), {})
    baja = any(s["objetivo"] == sitio for s in await bajas_pendientes(request, admin))
    return {"sitio": ficha, "dominio": dominio, "cuota": del_dominio.get("cuota"), "uso": del_dominio.get("uso"),
            "dns": bool(datos.get("dns")), "baja_pendiente": baja, "subida_max_mb": config.SUBIDA_MAX_BYTES // 1048576}
