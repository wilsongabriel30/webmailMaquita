"""Autenticación de git del sitio (repositorios privados): la del despliegue del sitio PHP y la de la aplicación
Node.js, Python o estática.

Métodos: clave de despliegue generada en el servidor (recomendada, de solo lectura), clave SSH propia, token de acceso
por HTTPS, usuario y contraseña por HTTPS, o ninguno (repositorio público). El secreto va al intermediario por su
socket y no vuelve nunca: la respuesta trae solo el método, la huella de la clave o los cuatro últimos caracteres del
token. En la auditoría queda solo el método.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
METODOS = ("clave-generada", "clave-propia", "token-https", "usuario-contrasena", "ninguna")
TEXTOS = {"repo": 400, "clave_privada": 16384, "token": 512, "usuario": 100, "contrasena": 512}


@router.get("/{sitio}/git/credencial")
async def estado(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "git-credencial", sitio)


@router.put("/{sitio}/git/credencial")
async def guardar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    if datos.get("metodo") not in METODOS or set(datos) - set(TEXTOS) - {"metodo", "regenerar"}:
        raise HTTPException(400, "Elige un método de autenticación válido")
    credencial = {"metodo": datos["metodo"], "regenerar": datos.get("regenerar") is True}
    for campo, maximo in TEXTOS.items():
        valor = datos.get(campo)
        if valor in (None, ""):
            continue
        if not isinstance(valor, str) or len(valor) > maximo:
            raise HTTPException(400, f"Dato no válido: {campo}")
        credencial[campo] = valor
    return await llamar(request, admin, "git-credencial-guardar", sitio, {"credencial": credencial},
                        "sitio_git_credencial", {"metodo": credencial["metodo"]})


@router.delete("/{sitio}/git/credencial")
async def borrar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "git-credencial-borrar", sitio, {}, "sitio_git_credencial_borrar")
