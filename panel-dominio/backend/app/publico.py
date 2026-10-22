"""Rutas SIN sesión del portal (v1.11): el gancho de git de los sitios y la actualización del DNS dinámico.

nginx las publica en el servidor del correo (https://<servidor>/git-despliegue/<sitio> y /nic/update, ver
deploy/sitios/nginx/sitios-publico.conf), con su propio límite de peticiones por IP. El portal no comprueba
nada que dependa de un secreto (no los tiene): reenvía la petición al intermediario root, que comprueba la firma
del gancho o la contraseña de la ficha del DNS dinámico con lo que solo él puede leer.

- Gancho: el cuerpo se guarda tal cual en la carpeta de subidas (hasta 1 MB), porque la firma es del cuerpo
  exacto; viajan las cabeceras de firma y de evento de GitHub, Gitea/Forgejo, Gogs y GitLab.
- DNS dinámico: protocolo dyndns2 (ddclient, routers, inadyn): GET con autenticación básica, hostname y myip
  (sin myip, la IP desde la que llega la petición). La respuesta es texto: good, nochg, badauth, nohost…
"""

import base64
import binascii
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.sitios import cliente
from app.sitios import subidas
from app.sitios.comun import RE_SITIO

router = APIRouter(prefix="/api/publico", tags=["publico"])
TOPE_GANCHO = 1024 * 1024
NO_VALE = "Firma no válida o gancho sin activar"
FIRMAS = ("x-hub-signature-256", "x-gitea-signature", "x-gogs-signature")
EVENTOS = ("x-github-event", "x-gitea-event", "x-gogs-event", "x-gitlab-event")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _cabecera(request: Request, nombres) -> str | None:
    for n in nombres:
        valor = request.headers.get(n)
        if valor and len(valor) <= 300 and not _CONTROL.search(valor):
            return valor.strip()
    return None


@router.post("/git/{sitio}")
async def gancho_git(sitio: str, request: Request):
    sitio = (sitio or "").strip().lower()
    if not RE_SITIO.fullmatch(sitio):
        raise HTTPException(403, NO_VALE)
    firma = _cabecera(request, FIRMAS)
    ficha_gitlab = _cabecera(request, ("x-gitlab-token",))
    if not firma and not ficha_gitlab:
        raise HTTPException(403, NO_VALE)
    nombre, _ = await subidas.recibir(request, "gancho", TOPE_GANCHO)
    args = {"subida": nombre, "evento": _cabecera(request, EVENTOS) or ""}
    if firma:
        args["firma"] = firma
    else:
        args["ficha_gitlab"] = ficha_gitlab
    try:
        datos = await cliente.pedir("", "gancho-git", sitio, args)
    finally:
        subidas.quitar(nombre)  # el intermediario ya la leyó y la borró; si no llegó a hacerlo, aquí
    datos = datos if isinstance(datos, dict) else {}
    codigo = datos.get("http") if datos.get("http") in (200, 202, 409) else 202
    return JSONResponse({"estado": str(datos.get("estado") or ""), "detalle": str(datos.get("detalle") or "")[:300]},
                        status_code=codigo)


def _basica(request: Request) -> tuple[str, str] | None:
    cabecera = request.headers.get("authorization") or ""
    if not cabecera[:6].lower() == "basic ":
        return None
    try:
        usuario, _, clave = base64.b64decode(cabecera[6:].strip(), validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if not usuario or not clave or len(usuario) > 64 or len(clave) > 200:
        return None
    return usuario, clave


def _texto(respuesta: str, codigo: int = 200) -> PlainTextResponse:
    cabeceras = {"WWW-Authenticate": 'Basic realm="DNS dinamico"'} if respuesta == "badauth" else None
    return PlainTextResponse(respuesta + "\n", status_code=codigo, headers=cabeceras)


@router.get("/nic/update")
async def ddns(request: Request, hostname: str = "", myip: str = ""):
    credenciales = _basica(request)
    if not credenciales:
        return _texto("badauth", 401)
    if len(hostname) > 1000 or len(myip) > 64:
        return _texto("notfqdn")
    ip_cliente = (request.headers.get("x-real-ip") or (request.client.host if request.client else "") or "")[:64]
    args = {"usuario": credenciales[0], "clave": credenciales[1], "hostname": hostname, "myip": myip.strip(),
            "ip_cliente": ip_cliente}
    try:
        datos = await cliente.pedir("", "ddns-actualizar", None, args)
    except HTTPException as e:
        return _texto("911", 503 if e.status_code >= 500 else 200)
    respuesta = str((datos or {}).get("respuesta") or "911")[:100]
    return _texto(respuesta, 401 if respuesta == "badauth" else 200)
