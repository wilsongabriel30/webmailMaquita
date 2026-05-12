"""Nextcloud integration — guardar adjuntos en Nextcloud via WebDAV.

Permite a los usuarios del webmail guardar archivos adjuntos directamente
en su cuenta de Nextcloud para editarlos online con OnlyOffice.

Autor: IA Code — 2026-04-13
"""
import logging
import urllib.parse
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user, encrypt_password, decrypt_password
from app.mail.clients.imap_client import get_imap_connection, fetch_attachment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nextcloud", tags=["nextcloud"])

# Configuracion Nextcloud desde settings (securizado)
from app.config import get_settings as _nc_settings

def _nc_config():
    s = _nc_settings()
    return s.nc_base_url, s.nc_admin_user, s.nc_admin_pass, s.nc_public_url


class SaveAttachmentRequest(BaseModel):
    folder: str
    uid: int
    part_number: str
    filename: str
    nc_path: str = ""


async def _get_nc_credentials(request: Request, username: str):
    """Obtener credenciales Nextcloud del usuario desde DB."""
    db = request.app.state.db_pool
    try:
        row = await db.fetchrow(
            "SELECT nc_userid, nc_password FROM nextcloud_accounts WHERE mail_username = $1 AND active = true",
            username,
        )
        if row:
            try:
                nc_pass = decrypt_password(row["nc_password"])
            except Exception:
                nc_pass = row["nc_password"]  # Legacy sin cifrar
            return row["nc_userid"], nc_pass
    except Exception:
        pass
    return None


async def _find_nc_userid_by_email(email: str) -> str | None:
    """Buscar userid de Nextcloud que tenga este email."""
    nc_base, nc_user, nc_pass, _ = _nc_config()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                nc_base + "/ocs/v1.php/cloud/users",
                params={"search": email, "limit": 5},
                auth=(nc_user, nc_pass),
                headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
            )
            if r.status_code != 200:
                return None
            users = r.json().get("ocs", {}).get("data", {}).get("users", [])
            for nc_user in users[:5]:
                detail_r = await client.get(
                    nc_base + "/ocs/v1.php/cloud/users/" + urllib.parse.quote(nc_user),
                    auth=(nc_user, nc_pass),
                    headers={"OCS-APIREQUEST": "true", "Accept": "application/json"},
                )
                if detail_r.status_code == 200:
                    detail = detail_r.json().get("ocs", {}).get("data", {})
                    if detail.get("email", "").lower() == email.lower():
                        return detail.get("id", nc_user)
    except Exception as e:
        logger.warning("Error buscando NC userid para %s: %s", email, e)
    return None


async def _nc_webdav_upload(userid: str, password: str, remote_path: str, data: bytes, filename: str) -> bool:
    """Subir archivo a Nextcloud via WebDAV."""
    nc_base, _, _, _ = _nc_config()
    folder_url = nc_base + "/remote.php/dav/files/" + urllib.parse.quote(userid) + remote_path
    file_url = folder_url + urllib.parse.quote(filename)

    async with httpx.AsyncClient(timeout=30) as client:
        # Crear carpeta si no existe (MKCOL ignora si ya existe)
        await client.request("MKCOL", folder_url, auth=(userid, password))
        # Subir archivo
        r = await client.put(
            file_url,
            content=data,
            auth=(userid, password),
            headers={"Content-Type": "application/octet-stream"},
        )
        if r.status_code in (200, 201, 204):
            return True
        logger.error("WebDAV upload failed: %s %s", r.status_code, r.text[:200])
        return False


async def _nc_webdav_test(userid: str, password: str) -> bool:
    """Verificar que credenciales WebDAV funcionan."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            nc_base, _, _, _ = _nc_config()
            r = await client.request(
                "PROPFIND",
                nc_base + "/remote.php/dav/files/" + urllib.parse.quote(userid) + "/",
                auth=(userid, password),
                headers={"Depth": "0"},
            )
            return r.status_code in (200, 207)
    except Exception:
        return False


@router.get("/status")
async def nextcloud_status(
    request: Request,
    username: str = Depends(get_current_user),
):
    """Verificar si el usuario tiene cuenta Nextcloud vinculada."""
    # 1. Buscar en tabla de cuentas vinculadas
    creds = await _get_nc_credentials(request, username)
    if creds:
        _, _, _, nc_pub = _nc_config()
        return {"linked": True, "nc_userid": creds[0], "nc_url": nc_pub}

    # 2. Buscar por email en Nextcloud
    nc_userid = await _find_nc_userid_by_email(username)
    if nc_userid:
        _, _, _, nc_pub = _nc_config()
        return {
            "linked": False,
            "nc_exists": True,
            "nc_userid": nc_userid,
            "nc_url": nc_pub,
            "message": "Cuenta Nextcloud encontrada. Al guardar un adjunto se usara su contraseña de correo.",
        }

    _, _, _, nc_pub = _nc_config()
    return {"linked": False, "nc_exists": False, "nc_url": nc_pub}


@router.post("/save-attachment")
async def save_attachment_to_nextcloud(
    body: SaveAttachmentRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Guardar un adjunto de correo directamente en Nextcloud."""

    # Determinar credenciales Nextcloud
    creds = await _get_nc_credentials(request, username)
    if creds:
        nc_userid, nc_password = creds
    else:
        nc_password = await get_user_password(request, username)
        nc_userid = await _find_nc_userid_by_email(username)
        if not nc_userid:
            raise HTTPException(
                404,
                "No se encontro cuenta Nextcloud vinculada a este correo. "
                "Contacte al administrador para que le asigne acceso a la nube."
            )
        # Verificar credenciales
        if not await _nc_webdav_test(nc_userid, nc_password):
            raise HTTPException(
                401,
                "Las credenciales del correo no coinciden con Nextcloud. "
                "Contacte al administrador para vincular su cuenta."
            )

    # Descargar adjunto via IMAP
    mail_password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, mail_password)
    try:
        data = await fetch_attachment(imap, body.folder, body.uid, body.part_number)
        if data is None:
            raise HTTPException(404, "Adjunto no encontrado")
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    # Determinar ruta destino
    nc_path = body.nc_path.strip() if body.nc_path else "/Correo/"
    if not nc_path.startswith("/"):
        nc_path = "/" + nc_path
    if not nc_path.endswith("/"):
        nc_path += "/"

    # Subir a Nextcloud via WebDAV
    ok = await _nc_webdav_upload(nc_userid, nc_password, nc_path, data, body.filename)
    if not ok:
        raise HTTPException(502, "Error al subir archivo a Nextcloud")

    _, _, _, nc_pub = _nc_config()
    nc_file_url = nc_pub + "/apps/files/?dir=" + urllib.parse.quote(nc_path) + "&openfile=true"

    logger.info("Adjunto guardado en NC: %s -> %s%s", username, nc_userid, nc_path + body.filename)

    return {
        "ok": True,
        "message": "Archivo guardado en Nextcloud: " + nc_path + body.filename,
        "nc_path": nc_path + body.filename,
        "nc_url": nc_file_url,
        "nc_userid": nc_userid,
    }


@router.post("/link-account")
async def link_nextcloud_account(
    request: Request,
    username: str = Depends(get_current_user),
):
    """Vincular cuenta Nextcloud manualmente (userid + password)."""
    body = await request.json()
    nc_userid = body.get("nc_userid", "").strip()
    nc_password = body.get("nc_password", "")

    if not nc_userid or not nc_password:
        raise HTTPException(400, "Se requiere usuario y contrasena de Nextcloud")

    if not await _nc_webdav_test(nc_userid, nc_password):
        raise HTTPException(401, "Credenciales de Nextcloud incorrectas")

    db = request.app.state.db_pool
    encrypted_nc_pass = encrypt_password(nc_password)
    await db.execute(
        "INSERT INTO nextcloud_accounts (mail_username, nc_userid, nc_password, active) "
        "VALUES ($1, $2, $3, true) "
        "ON CONFLICT (mail_username) DO UPDATE SET nc_userid=$2, nc_password=$3, active=true",
        username, nc_userid, encrypted_nc_pass,
    )

    return {"ok": True, "nc_userid": nc_userid, "message": "Cuenta Nextcloud vinculada correctamente"}
