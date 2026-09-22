"""Panel · Dispositivos: QR de aprovisionamiento (control completo / Device Owner) por código.

Un teléfono restaurado de fábrica lee este QR en la pantalla de bienvenida (tocar 6 veces) y Android
descarga la app publicada, verifica su huella y la instala como administradora del dispositivo. El QR
lleva además el código de enrolamiento (`PROVISIONING_ADMIN_EXTRAS_BUNDLE.codigo_enrolamiento`) para
que la app se registre sola; si la app aún no lo lee, la persona lo escribe. La huella se calcula del
APK publicado en `descargas-app/` (cambia con cada versión: el QR siempre es de la versión vigente).
Cada QR generado con código en claro queda en `admin_audit` (`dispositivo_codigo_qr`).
"""

import base64
import hashlib
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_role
from app.dispositivos import codigo_cifrado, version_publicada
from app.dispositivos.comun import auditar, db

router = APIRouter(prefix="/api/dispositivos/codigos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
APK = os.environ.get("DISP_APK_PUBLICADO", "/opt/maquita-webmail/descargas-app/maquita-mail.apk")
URL_APK = os.environ.get("DISP_APK_URL", "https://mail.maquita.org/webmail/descargas/maquita-mail.apk")
COMPONENTE = "org.maquita.mail/org.maquita.mail.equipo.AdministradorEquipo"
_cache: dict = {}


def _huella() -> str:
    try:
        st = os.stat(APK)
    except OSError:
        raise HTTPException(503, "No hay APK publicado en el servidor (descargas-app/maquita-mail.apk)")
    clave = (st.st_mtime, st.st_size)
    if _cache.get("clave") != clave:
        with open(APK, "rb") as f:
            h = hashlib.sha256(f.read()).digest()
        _cache.update(clave=clave, huella=base64.urlsafe_b64encode(h).decode().rstrip("="))
    return _cache["huella"]


def contenido(codigo: str | None) -> dict:
    qr = {
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": COMPONENTE,
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": URL_APK,
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": _huella(),
        "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": True,
        "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": True,
        "android.app.extra.PROVISIONING_LOCALE": "es_EC",
        "android.app.extra.PROVISIONING_TIME_ZONE": "America/Guayaquil",
    }
    if codigo:
        qr["android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE"] = {"codigo_enrolamiento": codigo}
    return qr


@router.post("/qr")
async def generar_qr(request: Request, admin: dict = Depends(_ADMIN)):
    """Cuerpo: `{codigo}` (en claro, recién creado) o `{codigo_id}` (asignado y vigente: se descifra) o
    nada (QR sin código: la persona lo escribe en la app). Devuelve el QR en SVG."""
    try:
        import segno
    except ImportError:
        raise HTTPException(503, "Falta el módulo segno en el panel (pip install segno)")
    b = await request.json() if int(request.headers.get("content-length") or 0) else {}
    codigo = (b.get("codigo") or "").strip().lower() or None
    codigo_id = b.get("codigo_id")
    if not codigo and codigo_id:
        c = await db(request).fetchrow(
            "SELECT codigo_cifrado, modo FROM disp_codigos WHERE id = $1 AND revocado_en IS NULL AND usos < usos_max "
            "AND (caduca_en IS NULL OR caduca_en > NOW())", int(codigo_id))
        codigo = codigo_cifrado.descifrar(c["codigo_cifrado"]) if c else None
    texto = json.dumps(contenido(codigo), ensure_ascii=False)
    svg = segno.make(texto, error="m").svg_inline(scale=6, border=3, dark="#000", omitsize=True, svgclass="qr-aprov", lineclass=None)
    await auditar(request, admin, "dispositivo_codigo_qr", str(codigo_id or "nuevo"), {"con_codigo": bool(codigo), "version": version_publicada.leer().get("versionName")})
    return {"svg": svg, "con_codigo": bool(codigo), "version": version_publicada.leer().get("versionName"), "json": texto}
