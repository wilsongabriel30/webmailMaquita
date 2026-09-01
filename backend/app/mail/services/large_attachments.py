"""Servicio de adjuntos grandes — sube al Almacén (Drive Maquita) y devuelve un
enlace público de descarga.

Cuando un adjunto supera SIZE_THRESHOLD, en vez de adjuntarlo en línea se sube al
Almacén del usuario y se genera un enlace público de solo lectura. Reemplaza la
antigua integración con Nextcloud (en retiro).
"""
import os
import logging

import httpx

logger = logging.getLogger(__name__)

SIZE_THRESHOLD = 25 * 1024 * 1024  # 25 MB

# El Almacén corre en el mismo servidor (gunicorn :8788). El servicio del webmail
# (app_webmail) expone su API bajo /api/almacen.
ALMACEN_BASE = os.getenv("ALMACEN_INTERNAL_URL", "http://127.0.0.1:8788")
API = ALMACEN_BASE + "/api/almacen"
CARPETA_ADJUNTOS = "/Adjuntos-Correo"


async def upload_and_share(access_token: str, filename: str, content: bytes) -> str | None:
    """Sube el archivo al Almacén del usuario y devuelve la URL pública de descarga.

    Se reenvía el ``access_token`` del usuario (la misma cookie del webmail, que el
    Almacén valida con el secreto compartido y su sesión viva). Devuelve ``None`` ante
    cualquier fallo, para que el llamador vuelva a adjuntar el archivo de forma normal.
    El archivo se guarda en ``/Adjuntos-Correo``.
    """
    if not access_token:
        return None
    cookies = {"access_token": access_token}
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # 1) Asegurar la carpeta destino (idempotente: si ya existe, se ignora).
            try:
                await client.post(
                    f"{API}/carpetas",
                    json={"ruta": "/", "nombre": "Adjuntos-Correo"},
                    cookies=cookies,
                )
            except Exception:
                pass

            # 2) Subir el archivo (multipart: campo `archivo` + `carpeta`).
            files = {"archivo": (filename, content, "application/octet-stream")}
            data = {"carpeta": CARPETA_ADJUNTOS}
            resp = await client.post(f"{API}/archivos", files=files, data=data, cookies=cookies)
            if resp.status_code != 201:
                logger.error("Almacén subida falló: %s %s", resp.status_code, resp.text[:200])
                return None
            subidos = (resp.json() or {}).get("archivos") or []
            ruta = subidos[0].get("ruta") if subidos else None
            if not ruta:
                logger.error("Almacén: respuesta de subida sin ruta")
                return None

            # 3) Crear un enlace público de solo lectura (tipo 3 = enlace).
            sh = await client.post(
                f"{API}/compartir",
                json={"ruta": ruta, "tipo": 3, "permisos": 1},
                cookies=cookies,
            )
            if sh.status_code != 201:
                logger.error("Almacén compartir falló: %s %s", sh.status_code, sh.text[:200])
                return None
            url = ((sh.json() or {}).get("compartido") or {}).get("url")
            return url or None

    except Exception as exc:
        logger.error("Error subiendo adjunto grande al Almacén: %s", exc)
        return None


def format_link_html(filename: str, size_bytes: int, share_url: str) -> str:
    """HTML del enlace al archivo compartido (tarjeta estilo Outlook)."""
    size_mb = size_bytes / (1024 * 1024)
    return (
        f'<div style="border:1px solid #c7e0f4;border-radius:6px;padding:12px 16px;margin:8px 0;'
        f'background:#f0f6ff;font-family:Segoe UI,sans-serif;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-size:20px;">📎</span>'
        f'<div>'
        f'<a href="{share_url}" style="color:#0078d4;text-decoration:none;font-weight:600;font-size:14px;"'
        f' target="_blank">{filename}</a>'
        f'<div style="color:#605e5c;font-size:12px;">{size_mb:.1f} MB — Almacenado en Almacén Maquita</div>'
        f'</div></div></div>'
    )
