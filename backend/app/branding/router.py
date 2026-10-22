import os

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.branding import entrada
from app.portales.resolucion import dominio_del_portal

router = APIRouter(prefix="/api/branding", tags=["branding"])

UPLOAD_DIR = "/opt/maquita-webmail/uploads/branding"

# [H-02] Lo que puede ver cualquiera desde la pantalla de entrada: solo nombre, lema,
# contacto, colores y archivos de marca. Nada de configuracion interna.
_PUBLICAS = (
    "org_name",
    "app_name",
    "org_slogan",
    "org_phone",
    "org_email",
    "org_website",
    # Política de privacidad (LOPDP): datos del responsable y del delegado que la ley obliga
    # a publicar (art. 12.8 y 12.9). Se configuran en branding_settings, no en el código.
    "org_ruc",
    "org_address",
    "privacy_contact_area",
    "privacy_contact_email",
    "dpo_name",
    "dpo_email",
    "dpo_phone",
    "privacy_updated",
    "privacy_version",
    "primary_color",
    "secondary_color",
    "footer_text",
    "logo_url",
    "favicon_url",
)


@router.get("")
async def get_branding(request: Request, response: Response):
    db = request.app.state.db_pool
    try:
        rows = await db.fetch("SELECT key, value FROM branding_settings")
    except Exception:
        return {}
    result = {r["key"]: r["value"] for r in rows if r["key"] in _PUBLICAS}
    org_general = result.get("org_name")

    # Nombre de organizacion para el frontend (TwoFactorGate, etc.), con fallback neutro
    result.setdefault("org_name", "Tu organización")

    for ftype in ("favicon", "logo"):
        path = os.path.join(UPLOAD_DIR, ftype)
        if os.path.isdir(path):
            files = os.listdir(path)
            if files:
                result[f"{ftype}_url"] = f"/api/branding/file/{ftype}/{files[0]}"

    # Portal de empresa: su marca manda sobre la general. Lo que la empresa no haya
    # definido (por ejemplo, si no tiene logo propio) se queda con el de la casa.
    dominio = await dominio_del_portal(db, request)
    if dominio:
        result.update(await _marca_de_empresa(db, dominio))
    # Pantalla de entrada del dominio por el que se entra (mail.<dominio>, webmail.<dominio>):
    # sugerencia del campo de correo, bienvenida, contacto y color. Ver entrada.py.
    result.update(await entrada.datos_de_entrada(db, request, org_general))
    # La respuesta depende del nombre de servidor pedido: que nadie la reutilice
    # para otro portal.
    response.headers["Vary"] = "Host"

    return result


async def _marca_de_empresa(db, dominio: str) -> dict:
    """Marca propia de una empresa: textos, colores y archivos."""
    propia: dict = {}
    try:
        filas = await db.fetch(
            "SELECT clave, valor FROM branding_empresa WHERE dominio = $1", dominio
        )
        propia = {
            f["clave"]: f["valor"]
            for f in filas
            if f["clave"] in _PUBLICAS and f["valor"]
        }
    except Exception:
        pass
    for ftype in ("favicon", "logo"):
        path = os.path.join(UPLOAD_DIR, "empresas", dominio, ftype)
        if os.path.isdir(path):
            files = sorted(os.listdir(path))
            if files:
                propia[f"{ftype}_url"] = (
                    f"/api/branding/empresa/{dominio}/{ftype}/{files[0]}"
                )
    return propia


@router.get("/empresa/{dominio}/{file_type}/{filename}")
async def get_file_empresa(dominio: str, file_type: str, filename: str):
    """Logo o icono propio de una empresa."""
    if file_type not in ("favicon", "logo"):
        raise HTTPException(404)
    filepath = os.path.join(
        UPLOAD_DIR,
        "empresas",
        os.path.basename(dominio),
        file_type,
        os.path.basename(filename),
    )
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(filepath)


@router.get("/file/{file_type}/{filename}")
async def get_file(file_type: str, filename: str):
    if file_type not in ("favicon", "logo"):
        raise HTTPException(404)
    safe = os.path.basename(filename)
    filepath = os.path.join(UPLOAD_DIR, file_type, safe)
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(filepath)
