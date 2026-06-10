"""Antispam Avanzado — afinar desde el panel el filtro de adjuntos/comprimidos,
la neurona de spam y la depuracion mensual. La config vive en un JSON que el
filtro (spam-filter-service.py) y la neurona leen en cada correo."""
import json
import os
import asyncio
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/antispam-avanzado", tags=["antispam-avanzado"])

CFG_PATH = "/etc/maquita-mail/filtro-avanzado.json"
NEURONA_JSON = "/opt/maquita-mail-filter/datos/neurona_spam.json"
DEPURA_BIN = "/usr/local/sbin/depurar-adjuntos-peligrosos"

DEFAULTS = {"umbral": 3, "macro_score": 2, "neurona_peso": 0,
            "extensiones_extra": [], "depuracion_dias": 35}

FAMILIAS = {
    "ejecutables_scripts": ["exe", "scr", "bat", "cmd", "com", "pif", "vbs",
        "vbe", "js", "jse", "wsf", "wsh", "wsc", "hta", "jar", "lnk", "ps1",
        "msi", "reg", "cpl", "scf", "sct", "chm", "jnlp", "xll", "wll", "one", "dll"],
    "imagenes_disco": ["iso", "img", "vhd", "vhdx", "udf", "vmdk", "wim"],
    "office_macros": ["docm", "xlsm", "pptm", "dotm", "xltm", "potm", "xlsb", "ppam", "xlam"],
    "comprimidos_inspeccionados": ["zip", "rar", "7z", "tar", "gz", "tgz", "cab",
        "ace", "lzh", "arj", "z", "lzma", "xz", "bz2", "zipx", "deb", "rpm", "cpio"],
}


def _db(r: Request):
    return r.app.state.db


def _load():
    cfg = dict(DEFAULTS)
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except Exception:
        pass
    return cfg


async def _audit(r, a, action, details=None):
    try:
        await _db(r).execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
            a["id"], a["username"], action, "antispam-avanzado",
            json.dumps(details or {}),
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass


class CfgIn(BaseModel):
    umbral: int = Field(3, ge=1, le=15)
    macro_score: int = Field(2, ge=0, le=6)
    neurona_peso: int = Field(0, ge=0, le=5)
    extensiones_extra: list[str] = []
    depuracion_dias: int = Field(35, ge=1, le=90)


class DepuraIn(BaseModel):
    dias: int = Field(35, ge=1, le=90)
    borrar: bool = False


@router.get("")
async def get_cfg(request: Request, admin: dict = Depends(get_current_admin)):
    cfg = _load()
    neu = {"entrenada": os.path.exists(NEURONA_JSON),
           "bytes": os.path.getsize(NEURONA_JSON) if os.path.exists(NEURONA_JSON) else 0}
    return {"config": cfg, "familias": FAMILIAS, "neurona": neu}


@router.put("")
async def put_cfg(body: CfgIn, request: Request,
                  admin: dict = Depends(require_role("superadmin", "admin"))):
    exts = sorted({str(e).strip().lstrip(".").lower()
                   for e in body.extensiones_extra if str(e).strip()})
    cfg = {"umbral": body.umbral, "macro_score": body.macro_score,
           "neurona_peso": body.neurona_peso, "extensiones_extra": exts,
           "depuracion_dias": body.depuracion_dias}
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CFG_PATH)
    try:
        os.chmod(CFG_PATH, 0o644)
    except OSError:
        pass
    await _audit(request, admin, "antispam_avanzado_update", cfg)
    return {"ok": True, "config": cfg}


@router.post("/depurar")
async def depurar(body: DepuraIn, request: Request,
                  admin: dict = Depends(require_role("superadmin", "admin"))):
    if body.borrar and admin.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadmin puede borrar")
    args = [DEPURA_BIN, "--dias", str(body.dias)]
    if body.borrar:
        args.append("--borrar")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        salida = out.decode("utf-8", "replace")
    except asyncio.TimeoutError:
        salida = "(timeout: la busqueda en buzones tardo mas de 180s; correr de noche)"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando depuracion: {e}")
    await _audit(request, admin, "antispam_avanzado_depurar",
                 {"dias": body.dias, "borrar": body.borrar})
    return {"ok": True, "salida": salida, "borrado": body.borrar}
