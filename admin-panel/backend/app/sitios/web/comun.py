"""Común a las funciones web por sitio: guardar una función (JSON en base64url) y registrarlo en auditoría.

El ayudante valida cada valor y aplica el cambio con copia previa y `nginx -t` (si nginx lo rechaza, deja la
configuración anterior y devuelve el motivo, que llega aquí como error 400).
"""

from fastapi import HTTPException, Request

from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio


async def guardar(r: Request, admin: dict, dominio: str, orden: str, datos, accion: str, tope: int = 8000) -> dict:
    dominio = _dominio(dominio)
    texto = b64(datos)
    if len(texto) > tope:
        raise HTTPException(400, "Demasiados datos")
    res = await _ayudante(orden, dominio, texto, tiempo=120)
    await _auditar(r, admin, accion, dominio, datos if isinstance(datos, dict) else {"lista": datos})
    return res


def b64_corto(valor: str, que: str) -> str:
    """Carpeta, subcarpeta o contraseña: un solo valor de hasta 200 caracteres en base64url."""
    valor = valor or ""
    if not valor or "\x00" in valor:
        raise HTTPException(400, f"{que} no válida")
    texto = b64(valor)
    if len(texto) > 200:
        raise HTTPException(400, f"{que} demasiado larga")
    return texto
