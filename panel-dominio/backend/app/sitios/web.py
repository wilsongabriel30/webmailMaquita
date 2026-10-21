"""Funciones web del sitio (v1.10): redirecciones, carpetas con contraseña, páginas de error, hotlinking, IP
bloqueadas y optimización para conexiones lentas (compresión, caché del navegador y caché de página).

Cada cambio afecta solo a este sitio; maquita-sitios lo aplica con copia previa y `nginx -t` y, si nginx lo
rechaza, deja lo anterior y devuelve el motivo. Las reglas propias de nginx siguen siendo del administrador
general. La contraseña de una carpeta (la que pone la persona o la que genera el servidor) no se audita: la
generada vuelve una sola vez en la respuesta.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


def _lista(valor, maximo: int, que: str) -> list:
    if not isinstance(valor, list) or len(valor) > maximo:
        raise HTTPException(400, f"{que}: se admiten hasta {maximo}")
    return valor


def _diccionario(valor, que: str) -> dict:
    if not isinstance(valor, dict):
        raise HTTPException(400, f"{que} no válidos")
    return valor


@router.get("/{sitio}/web")
async def ver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "web", sitio)


async def _guardar(request: Request, admin: dict, sitio: str, orden: str, clave: str, valor, accion: str):
    return await llamar(request, admin, orden, sitio, {clave: valor}, accion,
                        valor if isinstance(valor, dict) else {"lista": valor})


@router.put("/{sitio}/web/redirecciones")
async def redirecciones(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    lista = _lista((await cuerpo(request)).get("redirecciones"), 200, "Redirecciones")
    return await _guardar(request, admin, sitio, "web-redirecciones", "redirecciones", lista, "sitio_web_redirecciones")


@router.put("/{sitio}/web/errores")
async def errores(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    paginas = _diccionario((await cuerpo(request)).get("paginas"), "Páginas de error")
    if set(paginas) - {"403", "404", "500", "502", "503"}:
        raise HTTPException(400, "Solo se admiten los códigos 403, 404, 500, 502 y 503")
    return await _guardar(request, admin, sitio, "web-errores", "paginas", paginas, "sitio_web_errores")


@router.put("/{sitio}/web/hotlink")
async def hotlink(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = _diccionario(await cuerpo(request), "Datos del hotlinking")
    return await _guardar(request, admin, sitio, "web-hotlink", "hotlink", datos, "sitio_web_hotlink")


@router.put("/{sitio}/web/bloqueo")
async def bloqueo(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    redes = _lista((await cuerpo(request)).get("redes"), 500, "IP bloqueadas")
    if not all(isinstance(r, str) for r in redes):
        raise HTTPException(400, "IP o red no válida")
    redes = [r.strip() for r in redes if r.strip()]
    return await _guardar(request, admin, sitio, "web-bloqueo", "redes", redes, "sitio_web_bloqueo")


@router.put("/{sitio}/web/optimizacion")
async def optimizacion(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = _diccionario(await cuerpo(request), "Datos de la optimización")
    return await _guardar(request, admin, sitio, "web-optimizacion", "optimizacion", datos, "sitio_web_optimizacion")


@router.post("/{sitio}/web/purgar")
async def purgar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "web-purgar", sitio, None, "sitio_web_purgar")


@router.post("/{sitio}/web/privacidad")
async def privado_agregar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Añade un usuario a una carpeta (la protege si no lo estaba). Sin «clave», la genera el servidor."""
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    carpeta, usuario, clave = datos.get("carpeta"), datos.get("usuario"), datos.get("clave")
    if not isinstance(carpeta, str) or not isinstance(usuario, str) or (clave is not None and not isinstance(clave, str)):
        raise HTTPException(400, "Carpeta, usuario o contraseña no válidos")
    args = {"carpeta": carpeta.strip(), "usuario": usuario.strip()}
    if clave:
        args["clave"] = clave
    return await llamar(request, admin, "web-privado-agregar", sitio, args, "sitio_web_privado_agregar",
                        {"carpeta": args["carpeta"], "usuario": args["usuario"], "clave_propia": bool(clave)})


@router.delete("/{sitio}/web/privacidad")
async def privado_quitar(sitio: str, request: Request, carpeta: str, usuario: str = "", admin: dict = Depends(admin_actual)):
    """Sin usuario, quita la protección de la carpeta entera."""
    sitio, _ = exigir_sitio(admin, sitio)
    args = {"carpeta": carpeta.strip(), **({"usuario": usuario.strip()} if usuario.strip() else {})}
    return await llamar(request, admin, "web-privado-quitar", sitio, args, "sitio_web_privado_quitar", args)
