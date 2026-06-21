"""Panel SSO / Identidad — estado del IdP (Keycloak), federación LDAP y sync.

Agrega el estado real del Single Sign-On del ecosistema y permite re-sincronizar
los buzones a LDAP. Solo lectura + una acción (sync). Admin.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/sso", tags=["sso"])

KC_REALM = "https://auth.maquita.org/realms/maquita"
WEBMAIL_OIDC = "https://mail.maquita.org/api/auth/oidc/enabled"
SYNC = "/opt/maquita-webmail/deploy/sso/sync-ldap-from-maildb.sh"


def _db(r: Request):
    return r.app.state.db


def _sh(cmd: str, timeout: int = 20):
    try:
        return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


@router.get("/status")
async def status(r: Request, a=Depends(get_current_admin)):
    mailbox = await _db(r).fetchval("SELECT count(*) FROM mailbox WHERE active") or 0

    p = _sh('. /etc/maquita/ldap-sync.env 2>/dev/null; '
            'ldapsearch -x -H "$LDAP_URI" -D "$LDAP_ADMIN_DN" -w "$LDAP_ADMIN_PW" '
            '-b "ou=people,$LDAP_BASE" "(uid=*)" dn 2>/dev/null | grep -c "^dn:"')
    txt = (p.stdout.strip() if p else "0")
    ldap_users = int(txt) if txt.isdigit() else 0

    p2 = _sh(f'curl -s -m 8 -o /dev/null -w "%{{http_code}}" {KC_REALM}/.well-known/openid-configuration')
    kc_ok = bool(p2 and p2.stdout.strip() == "200")

    p3 = _sh(f'curl -s -m 8 {WEBMAIL_OIDC}')
    oidc = bool(p3 and '"enabled":true' in (p3.stdout or ""))

    return {
        "realm": "maquita",
        "idp_url": "https://auth.maquita.org",
        "keycloak_ok": kc_ok,
        "oidc_enabled": oidc,
        "mailbox_active": mailbox,
        "ldap_users": ldap_users,
        "ldap_synced_pct": round(100 * ldap_users / mailbox) if mailbox else 0,
        "webmail_client": "webmail-maquita",
    }


@router.post("/sync")
async def sync(r: Request, a=Depends(get_current_admin)):
    p = _sh(f"bash {SYNC}", timeout=120)
    if not p:
        raise HTTPException(500, "No se pudo ejecutar la sincronización")
    try:
        await _db(r).execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
            "VALUES ($1,$2,$3,$4,$5)", a["id"], a["username"], "sso_ldap_sync", "",
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass
    return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr or "")[-2000:]}
