"""Aplicaciones Node.js, Python y estáticas del sitio (v1.11), las mismas del panel general.

Corren con el usuario del sitio, encerradas en su unidad de systemd con límites de memoria, CPU y tareas, y solo
escuchan en 127.0.0.1: nginx las publica. Desde el portal no se abren puertos públicos (eso lo hace el
administrador general). Las variables de entorno pueden llevar claves: en la auditoría van solo sus nombres.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
TIPOS = ("estatico", "python", "node")
ACCIONES = ("iniciar", "detener", "reiniciar", "desplegar")
CAMPOS = {"git": str, "rama": str, "carpeta": str, "spa": bool, "modo": str, "entrada": str}
RE_VARIABLE = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")


def _conf(datos: dict) -> dict:
    if datos.get("puerto_publico") or datos.get("protocolo"):
        raise HTTPException(403, "Abrir un puerto del servidor lo hace el administrador general: pídeselo")
    conf = {}
    for clave, tipo in CAMPOS.items():
        valor = datos.get(clave)
        if valor in (None, ""):
            continue
        if not isinstance(valor, tipo) or (isinstance(valor, str) and len(valor) > 300):
            raise HTTPException(400, f"Dato no válido: {clave}")
        conf[clave] = valor.strip() if isinstance(valor, str) else valor
    return conf


@router.post("/{sitio}/propia", status_code=201)
async def crear(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    if datos.get("tipo") not in TIPOS:
        raise HTTPException(400, "Tipo de aplicación no válido (estática, Python o Node.js)")
    conf = _conf(datos)
    return await llamar(request, admin, "propia-crear", sitio, {"tipo": datos["tipo"], "conf": conf}, "sitio_propia_crear",
                        {"tipo": datos["tipo"], "git": conf.get("git")})


@router.get("/{sitio}/propia")
async def estado(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "propia-estado", sitio)


@router.post("/{sitio}/propia/accion")
async def accion(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    que = (await cuerpo(request)).get("accion")
    if que not in ACCIONES:
        raise HTTPException(400, "Acción no válida")
    return await llamar(request, admin, "propia-accion", sitio, {"accion": que}, f"sitio_propia_{que}")


@router.put("/{sitio}/propia/entorno")
async def entorno(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """{"variables": {"CLAVE": "valor" | null}}: null conserva el valor guardado; las que no vienen se quitan."""
    sitio, _ = exigir_sitio(admin, sitio)
    variables = (await cuerpo(request)).get("variables")
    if not isinstance(variables, dict) or len(variables) > 50 or any(not RE_VARIABLE.fullmatch(str(k)) for k in variables):
        raise HTTPException(400, "Nombres de variable: mayúsculas, números y _ (máximo 50 variables)")
    if any(v is not None and not isinstance(v, str) for v in variables.values()):
        raise HTTPException(400, "Cada valor es un texto de una línea")
    return await llamar(request, admin, "propia-entorno", sitio, {"variables": variables}, "sitio_propia_entorno",
                        {"variables": sorted(variables)})


@router.delete("/{sitio}/propia")
async def quitar(sitio: str, request: Request, confirmacion: str = "", admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if confirmacion.strip().lower() != sitio:
        raise HTTPException(400, "Escribe el nombre del sitio para confirmar")
    return await llamar(request, admin, "propia-quitar", sitio, {"confirmacion": sitio}, "sitio_propia_quitar")
