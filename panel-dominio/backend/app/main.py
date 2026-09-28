"""Portal de administradores de dominio.

Servicio aparte del panel general: otro proceso, otro puerto, otro usuario del sistema y
otro usuario de base de datos con permisos mínimos. Si este portal cae o lo atacan, el
panel general y el correo siguen como están.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.acceso import router as acceso_router
from app.alias import router as alias_router
from app.cuentas import router as cuentas_router
from app.dns import router as dns_router
from app.grupos import router as grupos_router
from app.marca import router as marca_router
from app.reenvios import router as reenvios_router
from app.solicitudes import router as solicitudes_router
from app.totp import router as totp_router
from app.db import crear_pool
from app.resumen import router as resumen_router

log = logging.getLogger("panel-dominio")


@asynccontextmanager
async def vida(app: FastAPI):
    app.state.db = await crear_pool()
    yield
    await app.state.db.close()


app = FastAPI(title="Portal de dominio", lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(Exception)
async def error_general(request: Request, exc: Exception):
    log.exception("error en %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Error interno"}, status_code=500)


@app.get("/api/salud")
async def salud():
    return {"ok": True}


app.include_router(totp_router)
app.include_router(acceso_router)
app.include_router(resumen_router)
app.include_router(cuentas_router)
app.include_router(alias_router)
app.include_router(reenvios_router)
app.include_router(grupos_router)
app.include_router(marca_router)
app.include_router(dns_router)
app.include_router(solicitudes_router)
