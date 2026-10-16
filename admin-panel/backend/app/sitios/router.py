"""Sitios web del servidor (sección «Hospedaje → Sitios web» del panel).

Cada sitio tiene su usuario de sistema, su pool de PHP y su vhost de nginx; se le puede instalar
WordPress o Joomla (software libre, descargado de su origen oficial y verificado), activar el
acceso FTP seguro/SFTP y pedir el certificado HTTPS. Todo lo que toca el sistema lo hace el
ayudante /usr/local/sbin/maquita-sitios, por el envoltorio maquita-sudo, que valida cada
argumento. Aquí se valida además en la entrada y se registra en auditoría.

Las contraseñas que se generan (administrador de la aplicación, FTP) se devuelven una sola vez
para mostrarlas en pantalla: no se guardan en el panel ni en la auditoría.
"""

import asyncio
import base64
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.wrappers.privilegios import con_sudo

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
AYUDANTE = "/usr/local/sbin/maquita-sitios"
RE_DOMINIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_CORREO = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


async def _ayudante(*args: str, tiempo: int = 60) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            *con_sudo(AYUDANTE, *args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        raise HTTPException(503, "Los sitios web no están instalados en este servidor")
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=tiempo)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "La operación tardó demasiado; revise el estado del sitio")
    texto = (out or b"").decode().strip()
    if not texto:
        motivo = (err or b"").decode(errors="replace").strip().splitlines()
        if "no such file" in " ".join(motivo).lower() or proc.returncode == 3:
            raise HTTPException(503, "Los sitios web no están instalados en este servidor")
        raise HTTPException(400, (motivo[-1] if motivo else "la orden fue rechazada")[:300])
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        raise HTTPException(500, "respuesta no válida del ayudante de sitios")
    if isinstance(datos, dict) and datos.get("error"):
        raise HTTPException(400, datos["error"])
    return datos


def _dominio(valor: str) -> str:
    valor = (valor or "").strip().lower().removeprefix("www.")
    if not RE_DOMINIO.match(valor):
        raise HTTPException(400, "Dominio no válido")
    return valor


def _correo(valor: str) -> str:
    valor = (valor or "").strip().lower()
    if not RE_CORREO.match(valor):
        raise HTTPException(400, "Correo no válido")
    return valor


async def _auditar(r: Request, admin: dict, accion: str, objetivo: str, detalles: dict | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"],
        admin["username"],
        accion,
        objetivo,
        json.dumps(detalles) if detalles else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


@router.get("")
async def listar(admin: dict = Depends(get_current_admin)):
    return await _ayudante("listar")


class NuevoSitio(BaseModel):
    dominio: str
    con_www: bool = True


@router.post("", status_code=201)
async def crear(body: NuevoSitio, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(body.dominio)
    args = ["crear", dominio] + ([] if body.con_www else ["sin-www"])
    res = await _ayudante(*args)
    await _auditar(r, admin, "sitio_crear", dominio, {"www": body.con_www})
    return res


class NuevaApp(BaseModel):
    app: str
    titulo: str
    correo: str


@router.post("/{dominio}/app")
async def instalar_app(dominio: str, body: NuevaApp, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.app not in ("wordpress", "joomla"):
        raise HTTPException(400, "Aplicación no disponible")
    titulo = (body.titulo or "").strip()
    if not 1 <= len(titulo) <= 100 or re.search(r"[\x00-\x1f\x7f<>]", titulo):
        raise HTTPException(400, "El título debe tener entre 1 y 100 caracteres, sin < ni >")
    titulo_b64 = base64.urlsafe_b64encode(titulo.encode()).decode().rstrip("=")
    if len(titulo_b64) > 200:
        raise HTTPException(400, "Título demasiado largo")
    res = await _ayudante("app", dominio, body.app, titulo_b64, _correo(body.correo), tiempo=600)
    await _auditar(r, admin, "sitio_app", dominio, {"app": body.app})
    return res


class AccionFtp(BaseModel):
    accion: str  # activar (también genera clave nueva) | desactivar


@router.post("/{dominio}/ftp")
async def ftp(dominio: str, body: AccionFtp, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.accion not in ("activar", "desactivar"):
        raise HTTPException(400, "Acción no válida")
    res = await _ayudante("ftp", dominio, body.accion)
    await _auditar(r, admin, f"sitio_ftp_{body.accion}", dominio)
    return res


class PedirSsl(BaseModel):
    correo: str


@router.post("/{dominio}/ssl")
async def ssl(dominio: str, body: PedirSsl, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("ssl", dominio, _correo(body.correo), tiempo=360)
    await _auditar(r, admin, "sitio_ssl", dominio)
    return res


class Confirmacion(BaseModel):
    confirmacion: str


@router.delete("/{dominio}")
async def borrar(dominio: str, body: Confirmacion, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if (body.confirmacion or "").strip().lower() != dominio:
        raise HTTPException(400, "Escriba el dominio exacto para confirmar")
    res = await _ayudante("borrar", dominio, dominio, tiempo=300)
    await _auditar(r, admin, "sitio_borrar", dominio, {"papelera": res.get("papelera")})
    return res


@router.post("/{dominio}/entrar")
async def entrar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    """Enlace de un solo uso (60 s) al escritorio de WordPress, sin contraseña."""
    dominio = _dominio(dominio)
    res = await _ayudante("entrar", dominio)
    await _auditar(r, admin, "sitio_entrar", dominio)
    return res


@router.post("/{dominio}/clave-admin")
async def clave_admin(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    """Contraseña nueva para el administrador de la aplicación (se muestra una vez)."""
    dominio = _dominio(dominio)
    res = await _ayudante("clave-admin", dominio, tiempo=120)
    await _auditar(r, admin, "sitio_clave_admin", dominio)
    return res


@router.get("/{dominio}/seguridad")
async def revisar(dominio: str, admin: dict = Depends(get_current_admin)):
    """Versión, actualizaciones pendientes e integridad de los archivos del núcleo."""
    return await _ayudante("revisar", _dominio(dominio), tiempo=180)


@router.post("/{dominio}/actualizar")
async def actualizar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("actualizar", dominio, tiempo=600)
    await _auditar(r, admin, "sitio_actualizar", dominio)
    return res


@router.get("/{dominio}/buscadores")
async def buscadores(dominio: str, admin: dict = Depends(get_current_admin)):
    """Visibilidad del sitio: portada, robots.txt, mapa del sitio, llms.txt, schema.org, HTTPS."""
    return await _ayudante("buscadores", _dominio(dominio), tiempo=120)


@router.post("/{dominio}/avisar")
async def avisar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    """Avisa por IndexNow (Bing, Yandex…) de la portada y las direcciones del mapa del sitio."""
    dominio = _dominio(dominio)
    res = await _ayudante("avisar", dominio, tiempo=120)
    await _auditar(r, admin, "sitio_avisar_buscadores", dominio, {"avisadas": res.get("avisadas")})
    return res


class VerificacionGoogle(BaseModel):
    codigo: str


@router.post("/{dominio}/google")
async def verificacion_google(dominio: str, body: VerificacionGoogle, r: Request, admin: dict = Depends(require_superadmin)):
    """Pone en la zona DNS el registro TXT de verificación de Google Search Console."""
    from app.dns.ayudante import ayudante as ayudante_dns, b64

    dominio = _dominio(dominio)
    codigo = (body.codigo or "").strip()
    m = re.search(r"google-site-verification=([A-Za-z0-9_-]{20,100})", codigo) or re.fullmatch(r"([A-Za-z0-9_-]{20,100})", codigo)
    if not m:
        raise HTTPException(400, "Pegue el registro TXT que da Search Console (google-site-verification=…)")
    valor = f"google-site-verification={m.group(1)}"
    zonas = {z["zona"] for z in (await ayudante_dns("dns", "listar"))["zonas"]}
    if dominio not in zonas:
        raise HTTPException(400, f"La zona DNS de {dominio} no se administra en este servidor: ponga el TXT en su proveedor de DNS")
    zona = await ayudante_dns("dns", "ver", dominio)
    if not any(x["tipo"] == "TXT" and x["valor"] == valor for x in zona["registros"]):
        await ayudante_dns("dns", "agregar", dominio, b64({"nombre": "@", "tipo": "TXT", "valor": valor, "ttl": 3600}))
    await _auditar(r, admin, "sitio_verificacion_google", dominio)
    return {"dominio": dominio, "registro": valor, "zona": "actualizada"}
