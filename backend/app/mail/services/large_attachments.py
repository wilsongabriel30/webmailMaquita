import os
"""Large attachment service — upload to Nextcloud and return share link.

When an attachment exceeds SIZE_THRESHOLD, upload it to the user's
Nextcloud folder and create a public share link instead of attaching inline.
"""
import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

SIZE_THRESHOLD = 25 * 1024 * 1024  # 25 MB

from app.config import get_settings as _gs

def _nc_base():
    return _gs().nc_base_url

# Nextcloud server — uses settings.onlyoffice_url base
def _nc_public():
    return _gs().nc_public_url


async def upload_and_share(
    username: str,
    password: str,
    filename: str,
    content: bytes,
) -> str | None:
    """Upload file to user's Nextcloud and return public share URL.

    Returns None on failure (caller should fall back to normal attachment).
    The file is placed in /Adjuntos-Correo/{filename}.
    """
    settings = get_settings()
    # Nextcloud credentials: same as mail (synced via FARO)
    nc_user = username.split("@")[0] if "@" in username else username
    nc_pass = password

    folder = "/Adjuntos-Correo"
    remote_path = f"{folder}/{filename}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Ensure folder exists (MKCOL — ignore 405 if exists)
            await client.request(
                "MKCOL",
                f"{_nc_base()}/remote.php/dav/files/{nc_user}{folder}",
                auth=(nc_user, nc_pass),
            )

            # Upload file via WebDAV PUT
            resp = await client.put(
                f"{_nc_base()}/remote.php/dav/files/{nc_user}{remote_path}",
                content=content,
                auth=(nc_user, nc_pass),
                headers={"Content-Type": "application/octet-stream"},
            )
            if resp.status_code not in (200, 201, 204):
                logger.error("Nextcloud upload failed: %s %s", resp.status_code, resp.text[:200])
                return None

            # Create public share via OCS API
            share_resp = await client.post(
                f"{_nc_base()}/ocs/v2.php/apps/files_sharing/api/v1/shares",
                auth=(nc_user, nc_pass),
                headers={
                    "OCS-APIRequest": "true",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "path": remote_path,
                    "shareType": "3",  # public link
                    "permissions": "1",  # read-only
                },
            )
            if share_resp.status_code not in (200, 201):
                logger.error("Nextcloud share failed: %s %s", share_resp.status_code, share_resp.text[:200])
                return None

            # Parse XML response for token/url
            text = share_resp.text
            # Extract <url>...</url>
            import re
            url_match = re.search(r"<url>([^<]+)</url>", text)
            if url_match:
                share_url = url_match.group(1)
                # Replace internal URL with public
                share_url = share_url.replace(_nc_base(), _nc_public())
                return share_url

            token_match = re.search(r"<token>([^<]+)</token>", text)
            if token_match:
                return f"{_nc_public()}/s/{token_match.group(1)}"

            logger.error("Could not parse share URL from response")
            return None

    except Exception as exc:
        logger.error("Large attachment upload error: %s", exc)
        return None


def format_link_html(filename: str, size_bytes: int, share_url: str) -> str:
    """Generate HTML snippet for the shared file link (Outlook style)."""
    size_mb = size_bytes / (1024 * 1024)
    return (
        f'<div style="border:1px solid #c7e0f4;border-radius:6px;padding:12px 16px;margin:8px 0;'
        f'background:#f0f6ff;font-family:Segoe UI,sans-serif;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-size:20px;">📎</span>'
        f'<div>'
        f'<a href="{share_url}" style="color:#0078d4;text-decoration:none;font-weight:600;font-size:14px;"'
        f' target="_blank">{filename}</a>'
        f'<div style="color:#605e5c;font-size:12px;">{size_mb:.1f} MB — Almacenado en Nube Maquita</div>'
        f'</div></div></div>'
    )
