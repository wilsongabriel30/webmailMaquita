"""Configuración de la entrada por OpenID Connect (tabla admin_oidc_config, una fila).

Solo el superadministrador la ve y la cambia. El client_secret nunca sale del servidor: se guarda
cifrado (cifrado.py) y la pantalla solo sabe si hay uno guardado. La pantalla de entrada pregunta
/api/auth/oidc/estado (público) para saber si mostrar el botón y con qué texto.
"""

import json
import re
from urllib.parse import urlsplit

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from app import organizacion
from app.auth.dependencies import require_superadmin
from app.auth.sesion import ip_de
from app.entrada import cifrado, oidc_protocolo

router = APIRouter(prefix="/api/auth/oidc", tags=["auth"])

ROLES = ("superadmin", "admin", "viewer")
RE_CLIENT_ID = re.compile(r"[A-Za-z0-9._~:@/+=-]{1,255}")
RE_CLAIM = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}")
RE_GRUPO = re.compile(r"[^\x00-\x1f\x7f]{1,255}")
RE_TEXTO_BOTON = re.compile(r"[^\x00-\x1f\x7f<>]{1,60}")
RE_SERVIDOR = re.compile(r"([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(:[0-9]{1,5})?")
RE_SECRETO = re.compile(r"[^\x00-\x1f\x7f]{1,512}")
NO_INSTALADO = "Falta la migración 2026-10-21-entrada-oidc-y-vales.sql (ajuste 66)"
RUTA_VUELTA = "/api/auth/oidc/vuelta"


def _db(request: Request):
    return request.app.state.db


async def leer(db) -> dict | None:
    """La fila de configuración, o None si este servidor aún no tiene la tabla."""
    try:
        fila = await db.fetchrow("SELECT * FROM admin_oidc_config WHERE id = 1")
    except asyncpg.exceptions.UndefinedTableError:
        return None
    return dict(fila) if fila else None


def activa(cfg: dict | None) -> bool:
    return bool(cfg and cfg.get("activado") and cfg.get("emisor") and cfg.get("client_id")
                and cfg.get("client_secret_cifrado"))


def url_vuelta(request: Request) -> str:
    """Dirección de vuelta (redirect_uri) que hay que registrar en el proveedor.

    ORG_URL_PANEL (organizacion.env) si está; si no, el nombre por el que se llegó y el puerto 8443
    (nginx pasa el Host sin puerto). Un Host inventado solo daría una dirección que el proveedor rechaza."""
    base = organizacion.url("ORG_URL_PANEL", "")
    if base and urlsplit(base).scheme == "https" and urlsplit(base).hostname:
        return f"https://{urlsplit(base).netloc}{RUTA_VUELTA}"
    host = request.headers.get("host", "").strip().lower()
    if len(host) > 260 or not RE_SERVIDOR.fullmatch(host):
        host = "localhost"
    return f"https://{host if ':' in host else host + ':8443'}{RUTA_VUELTA}"


def _publica(cfg: dict) -> dict:
    return {
        "activado": bool(cfg.get("activado")), "emisor": cfg.get("emisor", ""), "client_id": cfg.get("client_id", ""),
        "secreto_guardado": bool(cfg.get("client_secret_cifrado")), "claim_usuario": cfg.get("claim_usuario", ""),
        "claim_grupos": cfg.get("claim_grupos", ""), "grupo_requerido": cfg.get("grupo_requerido", ""),
        "crear_si_no_existe": bool(cfg.get("crear_si_no_existe")), "rol_nuevo": cfg.get("rol_nuevo", "viewer"),
        "texto_boton": cfg.get("texto_boton", ""), "actualizado_por": cfg.get("actualizado_por", ""),
        "actualizado_en": cfg["actualizado_en"].isoformat() if hasattr(cfg.get("actualizado_en"), "isoformat") else None,
    }


@router.get("/estado")
async def estado(request: Request):
    """Público: lo pide la pantalla de entrada para mostrar (o no) el botón."""
    cfg = await leer(_db(request))
    if not activa(cfg):
        return {"activado": False, "texto_boton": ""}
    return {"activado": True, "texto_boton": cfg["texto_boton"] or "Entrar con Identidad"}


@router.get("/config")
async def ver(request: Request, admin: dict = Depends(require_superadmin)):
    cfg = await leer(_db(request))
    if cfg is None:
        raise HTTPException(503, NO_INSTALADO)
    return {**_publica(cfg), "url_vuelta": url_vuelta(request)}


def _texto(datos: dict, campo: str, actual: dict) -> str:
    valor = datos.get(campo, actual.get(campo, ""))
    return valor.strip() if isinstance(valor, str) else ""


def validar(datos: dict, actual: dict) -> dict:
    """Los campos a guardar, ya validados (400 si algo no vale). El secreto va aparte."""
    if not isinstance(datos, dict):
        raise HTTPException(400, "Petición no válida")
    nuevo = {
        "activado": bool(datos.get("activado", actual.get("activado", False))),
        "emisor": _texto(datos, "emisor", actual).rstrip("/"),
        "client_id": _texto(datos, "client_id", actual),
        "claim_usuario": _texto(datos, "claim_usuario", actual) or "preferred_username",
        "claim_grupos": _texto(datos, "claim_grupos", actual),
        "grupo_requerido": _texto(datos, "grupo_requerido", actual),
        "crear_si_no_existe": bool(datos.get("crear_si_no_existe", actual.get("crear_si_no_existe", False))),
        "rol_nuevo": _texto(datos, "rol_nuevo", actual) or "viewer",
        "texto_boton": _texto(datos, "texto_boton", actual) or "Entrar con Identidad",
    }
    if nuevo["emisor"] and not oidc_protocolo.emisor_valido(nuevo["emisor"]):
        raise HTTPException(400, "El emisor (issuer) debe ser una dirección https:// sin espacios")
    if nuevo["client_id"] and not RE_CLIENT_ID.fullmatch(nuevo["client_id"]):
        raise HTTPException(400, "client_id no válido")
    if not RE_CLAIM.fullmatch(nuevo["claim_usuario"]):
        raise HTTPException(400, "El claim de usuario no es un nombre válido (p. ej. preferred_username o email)")
    if nuevo["claim_grupos"] and not RE_CLAIM.fullmatch(nuevo["claim_grupos"]):
        raise HTTPException(400, "El claim de grupos no es un nombre válido (p. ej. groups)")
    if nuevo["grupo_requerido"] and not RE_GRUPO.fullmatch(nuevo["grupo_requerido"]):
        raise HTTPException(400, "Grupo requerido no válido")
    if nuevo["grupo_requerido"] and not nuevo["claim_grupos"]:
        raise HTTPException(400, "Para exigir un grupo hay que indicar el claim de grupos")
    if nuevo["rol_nuevo"] not in ROLES:
        raise HTTPException(400, "Rol no válido. Opciones: superadmin, admin, viewer")
    if not RE_TEXTO_BOTON.fullmatch(nuevo["texto_boton"]):
        raise HTTPException(400, "El texto del botón debe tener de 1 a 60 caracteres, sin < ni >")
    if nuevo["activado"] and not (nuevo["emisor"] and nuevo["client_id"]):
        raise HTTPException(400, "Para activarla hacen falta el emisor y el client_id")
    return nuevo


@router.put("/config")
async def guardar(request: Request, admin: dict = Depends(require_superadmin)):
    db = _db(request)
    actual = await leer(db)
    if actual is None:
        raise HTTPException(503, NO_INSTALADO)
    datos = await request.json()
    nuevo = validar(datos, actual)
    secreto = datos.get("client_secret") if isinstance(datos, dict) else None
    cifrado_nuevo = actual.get("client_secret_cifrado", "")
    if isinstance(secreto, str) and secreto.strip():
        if not RE_SECRETO.fullmatch(secreto):
            raise HTTPException(400, "client_secret no válido")
        try:
            cifrado_nuevo = cifrado.cifrar(secreto)
        except cifrado.SinLlave as e:
            raise HTTPException(503, str(e))
    if nuevo["activado"] and not cifrado_nuevo:
        raise HTTPException(400, "Para activarla hace falta el client_secret")
    await db.execute(
        """UPDATE admin_oidc_config SET activado = $1, emisor = $2, client_id = $3, client_secret_cifrado = $4,
                  claim_usuario = $5, claim_grupos = $6, grupo_requerido = $7, crear_si_no_existe = $8,
                  rol_nuevo = $9, texto_boton = $10, actualizado_por = $11, actualizado_en = NOW()
            WHERE id = 1""",
        nuevo["activado"], nuevo["emisor"], nuevo["client_id"], cifrado_nuevo, nuevo["claim_usuario"],
        nuevo["claim_grupos"], nuevo["grupo_requerido"], nuevo["crear_si_no_existe"], nuevo["rol_nuevo"],
        nuevo["texto_boton"], admin["username"],
    )
    oidc_protocolo.olvidar_cache()
    detalles = {k: v for k, v in nuevo.items()}
    detalles["secreto_cambiado"] = cifrado_nuevo != actual.get("client_secret_cifrado", "")
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        admin["id"], admin["username"], "oidc_config", nuevo["emisor"][:255], json.dumps(detalles), ip_de(request),
    )
    return {"ok": True, **_publica({**actual, **nuevo, "client_secret_cifrado": cifrado_nuevo})}


@router.post("/probar")
async def probar(request: Request, admin: dict = Depends(require_superadmin)):
    """Descubrimiento y claves del emisor indicado (o del guardado), sin guardar nada."""
    datos = await request.json()
    emisor = str((datos or {}).get("emisor") or ((await leer(_db(request))) or {}).get("emisor") or "").strip().rstrip("/")
    try:
        doc = await oidc_protocolo.descubrir(emisor, forzar=True)
        lista = await oidc_protocolo.claves(doc["jwks_uri"], forzar=True)
    except oidc_protocolo.ErrorOidc as e:
        raise HTTPException(502, f"No se pudo usar el proveedor: {e.motivo}")
    return {
        "ok": True, "issuer": doc["issuer"], "authorization_endpoint": doc["authorization_endpoint"],
        "token_endpoint": doc["token_endpoint"], "userinfo_endpoint": doc.get("userinfo_endpoint"),
        "claves": len(lista), "pkce_s256": "S256" in (doc.get("code_challenge_methods_supported") or ["S256"]),
        "url_vuelta": url_vuelta(request),
    }
