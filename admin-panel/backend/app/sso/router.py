"""Panel SSO / Identidad — estado del IdP (Keycloak), federación LDAP y sync.

Agrega el estado real del Single Sign-On del ecosistema y permite re-sincronizar
los buzones a LDAP. Solo lectura + una acción (sync). Admin.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import asyncio
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException

from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/sso", tags=["sso"])

KC_REALM = "https://auth.maquita.org/realms/maquita"
WEBMAIL_OIDC = "https://mail.maquita.org/api/auth/oidc/enabled"
SYNC = "/opt/maquita-webmail/deploy/sso/sync-ldap-from-maildb.sh"


def _db(r: Request):
    return r.app.state.db


def _entorno_ldap() -> dict:
    """Lee /etc/maquita/ldap-sync.env (KEY=valor) sin pasar por un shell."""
    env = {}
    try:
        with open("/etc/maquita/ldap-sync.env", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


async def _ejecutar(args: list, timeout: int = 20):
    """[M-03] Lista de argumentos, nunca shell. Devuelve CompletedProcess o None."""
    try:
        return await asyncio.to_thread(subprocess.run, args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


async def _ldap_usuarios() -> int:
    e = _entorno_ldap()
    if not e.get("LDAP_URI") or not e.get("LDAP_BASE"):
        return 0
    p = await _ejecutar([
        "ldapsearch", "-x", "-H", e["LDAP_URI"], "-D", e.get("LDAP_ADMIN_DN", ""),
        "-w", e.get("LDAP_ADMIN_PW", ""), "-b", f"ou=people,{e['LDAP_BASE']}", "(uid=*)", "dn",
    ])
    if not p:
        return 0
    return sum(1 for l in (p.stdout or "").splitlines() if l.startswith("dn:"))


async def _http_estado(url: str) -> tuple[int, str]:
    import urllib.request

    def _pedir():
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return r.status, r.read(4096).decode("utf-8", "ignore")
        except Exception:
            return 0, ""

    return await asyncio.to_thread(_pedir)


@router.get("/status")
async def status(r: Request, a=Depends(get_current_admin)):
    mailbox = await _db(r).fetchval("SELECT count(*) FROM mailbox WHERE active") or 0
    ldap_users = await _ldap_usuarios()
    kc_status, _ = await _http_estado(f"{KC_REALM}/.well-known/openid-configuration")
    _st, cuerpo = await _http_estado(WEBMAIL_OIDC)
    return {
        "realm": "maquita",
        "idp_url": "https://auth.maquita.org",
        "keycloak_ok": kc_status == 200,
        "oidc_enabled": '"enabled":true' in cuerpo,
        "mailbox_active": mailbox,
        "ldap_users": ldap_users,
        "ldap_synced_pct": round(100 * ldap_users / mailbox) if mailbox else 0,
        "webmail_client": "webmail-maquita",
    }


@router.post("/sync")
async def sync(r: Request, a=Depends(require_superadmin)):
    p = await _ejecutar(["bash", SYNC], timeout=120)
    if not p:
        raise HTTPException(500, "No se pudo ejecutar la sincronización")
    try:
        await _db(r).execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
            "VALUES ($1,$2,$3,$4,$5)", a["id"], a["username"], "sso_ldap_sync", "",
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception as exc:
        # [L-02] La auditoria nunca falla en silencio: error con marca para monitoreo.
        import logging

        logging.getLogger("security").error("AUDITORIA_NO_REGISTRADA accion=sso_ldap_sync error=%s", str(exc)[:120])
    return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr or "")[-2000:]}
