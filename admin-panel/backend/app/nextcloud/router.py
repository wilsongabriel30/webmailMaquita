import os
"""Nextcloud user management — crear/verificar usuarios via OCS API.

Permite al admin crear cuentas Nextcloud al crear buzones de correo.
Usa la OCS Provisioning API v1 de Nextcloud.

Autor:  Code — 2026-04-13
"""
import logging
import urllib.parse
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from app.auth.dependencies import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nextcloud", tags=["nextcloud"])

NC_BASE_URL = "http://localhost"
NC_ADMIN_USER = "gestiontecnologia@maquita.com.ec"
NC_ADMIN_PASS = os.getenv("NC_ADMIN_PASS", "")
NC_PUBLIC_URL = "https://nube.example.com"
NC_DEFAULT_QUOTA = "5 GB"


async def _ocs_get(path: str, params: dict = None) -> dict:
    """GET a la OCS API de Nextcloud."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            NC_BASE_URL + path,
            params=params,
            auth=(NC_ADMIN_USER, NC_ADMIN_PASS),
            headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
        )
        if r.status_code != 200:
            raise HTTPException(502, "Error de conexion con Nextcloud: HTTP " + str(r.status_code))
        return r.json()


async def _ocs_post(path: str, data: dict) -> dict:
    """POST a la OCS API de Nextcloud."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            NC_BASE_URL + path,
            data=data,
            auth=(NC_ADMIN_USER, NC_ADMIN_PASS),
            headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
        )
        return r.json()


async def _ocs_put(path: str, data: dict) -> dict:
    """PUT a la OCS API de Nextcloud."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.put(
            NC_BASE_URL + path,
            data=data,
            auth=(NC_ADMIN_USER, NC_ADMIN_PASS),
            headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
        )
        return r.json()


class CreateNCUserRequest(BaseModel):
    userid: str          # ID de usuario en Nextcloud (ej: nombre corto)
    password: str
    displayName: str = ""
    email: str = ""
    quota: str = NC_DEFAULT_QUOTA
    groups: list[str] = []


@router.get("/users")
async def list_nc_users(
    search: str = "",
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
):
    """Listar usuarios de Nextcloud."""
    data = await _ocs_get(
        "/ocs/v1.php/cloud/users",
        params={"search": search, "limit": limit} if search else {"limit": limit},
    )
    users = data.get("ocs", {}).get("data", {}).get("users", [])
    return {"users": users, "count": len(users)}


@router.get("/users/{userid}")
async def get_nc_user(
    userid: str,
    admin: dict = Depends(get_current_admin),
):
    """Obtener detalle de un usuario Nextcloud."""
    data = await _ocs_get("/ocs/v1.php/cloud/users/" + urllib.parse.quote(userid))
    meta = data.get("ocs", {}).get("meta", {})
    if meta.get("statuscode") != 100:
        raise HTTPException(404, "Usuario no encontrado en Nextcloud")
    user_data = data.get("ocs", {}).get("data", {})
    return {
        "id": user_data.get("id"),
        "displayname": user_data.get("displayname"),
        "email": user_data.get("email"),
        "enabled": user_data.get("enabled"),
        "quota": user_data.get("quota"),
        "groups": user_data.get("groups"),
        "lastLogin": user_data.get("lastLogin"),
    }


@router.get("/check/{email}")
async def check_nc_account_by_email(
    email: str,
    admin: dict = Depends(get_current_admin),
):
    """Verificar si existe cuenta Nextcloud para un email."""
    data = await _ocs_get(
        "/ocs/v1.php/cloud/users",
        params={"search": email, "limit": 10},
    )
    users = data.get("ocs", {}).get("data", {}).get("users", [])
    for nc_user in users[:10]:
        detail = await _ocs_get("/ocs/v1.php/cloud/users/" + urllib.parse.quote(nc_user))
        user_data = detail.get("ocs", {}).get("data", {})
        if user_data.get("email", "").lower() == email.lower():
            return {
                "exists": True,
                "nc_userid": user_data.get("id", nc_user),
                "displayname": user_data.get("displayname"),
                "enabled": user_data.get("enabled"),
                "quota": user_data.get("quota"),
            }
    return {"exists": False}


@router.post("/users")
async def create_nc_user(
    body: CreateNCUserRequest,
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    """Crear usuario en Nextcloud via OCS API."""
    # Verificar que no exista
    data = await _ocs_get("/ocs/v1.php/cloud/users/" + urllib.parse.quote(body.userid))
    if data.get("ocs", {}).get("meta", {}).get("statuscode") == 100:
        raise HTTPException(409, "El usuario " + body.userid + " ya existe en Nextcloud")

    # Crear usuario
    create_data = {
        "userid": body.userid,
        "password": body.password,
        "displayName": body.displayName or body.userid,
        "email": body.email,
        "quota": body.quota,
    }
    if body.groups:
        create_data["groups[]"] = body.groups

    result = await _ocs_post("/ocs/v1.php/cloud/users", create_data)
    meta = result.get("ocs", {}).get("meta", {})

    if meta.get("statuscode") != 100:
        msg = meta.get("message", "Error desconocido")
        raise HTTPException(400, "Error al crear usuario Nextcloud: " + msg)

    logger.info("Usuario Nextcloud creado: %s (email: %s) por admin %s", body.userid, body.email, admin["username"])

    return {
        "ok": True,
        "nc_userid": body.userid,
        "message": "Usuario Nextcloud creado exitosamente",
        "nc_url": NC_PUBLIC_URL,
    }


@router.get("/groups")
async def list_nc_groups(admin: dict = Depends(get_current_admin)):
    """Listar grupos de Nextcloud."""
    data = await _ocs_get("/ocs/v1.php/cloud/groups")
    groups = data.get("ocs", {}).get("data", {}).get("groups", [])
    return {"groups": groups}


@router.get("/status")
async def nc_server_status(admin: dict = Depends(get_current_admin)):
    """Verificar estado del servidor Nextcloud."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(NC_BASE_URL + "/status.php")
            if r.status_code == 200:
                info = r.json()
                return {
                    "online": True,
                    "version": info.get("versionstring"),
                    "maintenance": info.get("maintenance"),
                    "url": NC_PUBLIC_URL,
                }
    except Exception as e:
        return {"online": False, "error": str(e)}
    return {"online": False}