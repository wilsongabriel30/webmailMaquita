"""
Firewall & fail2ban management router for Maquita Webmail Admin.
Prefix: /api/admin/firewall
"""

import asyncio
import ipaddress
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.admin import audit_service
from app.auth.dependencies import require_admin

router = APIRouter(prefix="/api/admin/firewall", tags=["admin-firewall"])

BLACKLIST_FILE = "/etc/maquita-mail/blacklist-ips.txt"
MAIL_LOG = "/var/log/mail.log"

FAIL2BAN_JAILS = [
    "postfix-sasl",
    "dovecot",
    "postfix-rbl",
    "recidive",
]


# ── Helpers ──────────────────────────────────────────────────


def _get_ip(request: Request) -> str:
    return request.headers.get(
        "X-Real-IP", request.client.host if request.client else "unknown"
    )


async def _audit(
    request: Request, admin: str, action: str, target: str = None, details: dict = None
):
    db = request.app.state.db_pool
    await audit_service.log_action(db, admin, action, target, details, _get_ip(request))


# Caracteres admitidos en el motivo de un bloqueo. Lista BLANCA a proposito: el
# motivo lo escribe quien administra y acaba en una linea de comentario del
# fichero de listas. Antes iba a `bash -c` citado con repr(), que es citado de
# Python y NO de shell: al aparecer una comilla simple, repr() cambia a comillas
# dobles y bash expande $( ), ` ` y $VAR. Eso era ejecucion de ordenes.
_RE_MOTIVO_PROHIBIDO = re.compile(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ ._,:()/#@+=—-]")
_LARGO_MAXIMO_MOTIVO = 120


AYUDANTE_LISTA = "/usr/local/sbin/maquita-blacklist"


async def _lista_negra(*args: str) -> dict:
    """Invoca al ayudante privilegiado y devuelve su respuesta.

    El backend corre como www-data: no puede escribir en /etc ni tocar nftables.
    Antes intentaba hacerlo directamente y los cuatro pasos fallaban sin que
    nadie se enterara, porque no se miraba el resultado. El ayudante valida por
    su cuenta la IP y el motivo -corre como root, es el ultimo sitio donde se
    puede comprobar- y ademas sincroniza el mapa que rspamd lee de verdad.
    """
    import json as _json

    stdout, stderr, codigo = await _run_cmd(
        "sudo", "-n", AYUDANTE_LISTA, *args, timeout=40
    )
    try:
        respuesta = _json.loads(stdout or "{}")
    except ValueError:
        raise HTTPException(
            500,
            f"Respuesta ilegible del ayudante de listas: {(stderr or stdout)[:120]}",
        )
    if not respuesta.get("ok"):
        raise HTTPException(
            400, respuesta.get("error") or "No se pudo actualizar la lista"
        )
    return respuesta


def _sanear_motivo(texto: str) -> str:
    """Motivo apto para una linea de comentario: sin saltos de linea ni metacaracteres."""
    texto = (texto or "").strip()
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = _RE_MOTIVO_PROHIBIDO.sub("", texto).strip()
    texto = re.sub(r"\s+", " ", texto)[:_LARGO_MAXIMO_MOTIVO].strip()
    return texto or "Bloqueado manualmente"


async def _run_cmd(*args: str, timeout: int = 30) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise HTTPException(504, f"Comando timeout: {' '.join(args[:2])}")
    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        proc.returncode,
    )


def _parse_blacklist(content: str) -> list[dict]:
    """Parse blacklist file content into list of {ip, reason, date}."""
    entries = []
    pending_comment = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            pending_comment = ""
            continue
        if stripped.startswith("#"):
            pending_comment = stripped.lstrip("# ").strip()
            continue
        # It's an IP/CIDR line
        parts = pending_comment.rsplit(" - ", 1) if pending_comment else ["", ""]
        reason = parts[0] if len(parts) >= 1 else ""
        date_str = parts[1] if len(parts) >= 2 else ""
        entries.append(
            {
                "ip": stripped,
                "reason": reason,
                "date": date_str,
            }
        )
        pending_comment = ""
    return entries


def _validate_ip_or_cidr(value: str) -> bool:
    """Validate that value is a valid IP address or CIDR range."""
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


async def _read_file(path: str) -> str:
    """Read file content."""
    try:
        stdout, _, rc = await _run_cmd("cat", path)
        if rc != 0:
            return ""
        return stdout
    except Exception:
        return ""


async def _get_blacklist_ips() -> list[dict]:
    content = await _read_file(BLACKLIST_FILE)
    return _parse_blacklist(content)


# ── Models ───────────────────────────────────────────────────


class BlacklistAddRequest(BaseModel):
    ip: str
    reason: str = ""


class BanToPermanentRequest(BaseModel):
    ip: str


# ── Endpoints ────────────────────────────────────────────────


@router.get("/dashboard")
async def firewall_dashboard(request: Request, admin: str = Depends(require_admin)):
    """Dashboard con estadísticas generales del firewall."""

    # 1. Total IPs bloqueadas permanentes
    blacklist_entries = await _get_blacklist_ips()
    total_blocked = len(blacklist_entries)

    # 2. fail2ban stats por jail
    jail_stats = {}
    total_banned = 0
    active_jails = 0
    for jail in FAIL2BAN_JAILS:
        stdout, _, rc = await _run_cmd("fail2ban-client", "status", jail)
        if rc == 0:
            active_jails += 1
            # Parse "Currently banned: N"
            match = re.search(r"Currently banned:\s*(\d+)", stdout)
            banned = int(match.group(1)) if match else 0
            # Parse "Total banned: N"
            total_match = re.search(r"Total banned:\s*(\d+)", stdout)
            total_hist = int(total_match.group(1)) if total_match else 0
            jail_stats[jail] = {
                "currently_banned": banned,
                "total_banned": total_hist,
            }
            total_banned += banned
        else:
            jail_stats[jail] = {
                "currently_banned": 0,
                "total_banned": 0,
                "error": "jail no activo",
            }

    # 3. Ataques últimas 24h
    since = (datetime.now() - timedelta(hours=24)).strftime("%b %d")
    stdout, _, _ = await _run_cmd(
        "grep",
        "-c",
        "-i",
        "authentication fail",
        MAIL_LOG,
    )
    attacks_24h = int(stdout.strip()) if stdout.strip().isdigit() else 0

    # Also count SASL failures
    stdout2, _, _ = await _run_cmd(
        "grep",
        "-c",
        "-i",
        "SASL.*authentication failed",
        MAIL_LOG,
    )
    sasl_fails = int(stdout2.strip()) if stdout2.strip().isdigit() else 0
    attacks_24h = max(attacks_24h, sasl_fails)

    # 4. Top 10 IPs atacantes
    stdout, _, _ = await _run_cmd(
        "bash",
        "-c",
        f'grep -i -E "(authentication fail|SASL.*authentication failed)" {MAIL_LOG} '
        f'| grep -oP "\\b(?:[0-9]{{1,3}}\\.?){{4}}\\b" '
        f"| sort | uniq -c | sort -rn | head -10",
    )
    top_ips = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            count_str, ip = parts
            if _validate_ip_or_cidr(ip):
                top_ips.append({"ip": ip, "count": int(count_str), "type": "auth_fail"})

    return {
        "total_blocked_permanent": total_blocked,
        "total_banned_fail2ban": total_banned,
        "attacks_24h": attacks_24h,
        "active_jails": active_jails,
        "jail_stats": jail_stats,
        "top_attacking_ips": top_ips[:10],
    }


@router.get("/attacks")
async def list_attacks(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    admin: str = Depends(require_admin),
):
    """Listar ataques recientes agrupados por IP."""
    stdout, _, _ = await _run_cmd(
        "bash",
        "-c",
        f'grep -i -E "(authentication fail|SASL.*authentication failed|unknown\\[)" {MAIL_LOG} '
        f"| tail -{limit * 5}",
        timeout=60,
    )

    ip_data: dict[str, dict] = {}
    for line in stdout.strip().splitlines():
        if not line:
            continue

        # Extract IP
        ip_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", line)
        if not ip_match:
            continue
        ip = ip_match.group(1)

        # Determine attack type
        if "SASL" in line.upper():
            attack_type = "sasl_fail"
        elif "authentication fail" in line.lower():
            attack_type = "auth_fail"
        else:
            attack_type = "other"

        # Extract username attempted
        user_match = re.search(r"user=<?([^>,\s]+)", line)
        username = user_match.group(1) if user_match else ""
        if not username:
            user_match2 = re.search(
                r"SASL\s+\w+\s+authentication failed:?\s*(.*)", line, re.IGNORECASE
            )
            username = user_match2.group(1).strip() if user_match2 else ""

        # Extract timestamp
        ts_match = re.match(r"^(\w{3}\s+\d+\s+\d+:\d+:\d+)", line)
        timestamp = ts_match.group(1) if ts_match else ""

        if ip not in ip_data:
            ip_data[ip] = {
                "ip": ip,
                "count": 0,
                "type": attack_type,
                "username_attempted": username,
                "timestamp": timestamp,
                "events": [],
            }
        ip_data[ip]["count"] += 1
        if len(ip_data[ip]["events"]) < 5:
            ip_data[ip]["events"].append(
                {
                    "timestamp": timestamp,
                    "type": attack_type,
                    "username_attempted": username,
                }
            )

    # Sort by count descending
    sorted_attacks = sorted(ip_data.values(), key=lambda x: x["count"], reverse=True)
    return {"attacks": sorted_attacks[:limit], "total": len(sorted_attacks)}


@router.get("/banned")
async def list_banned(request: Request, admin: str = Depends(require_admin)):
    """Listar IPs actualmente baneadas por fail2ban."""
    banned_list = []

    for jail in FAIL2BAN_JAILS:
        stdout, _, rc = await _run_cmd("fail2ban-client", "status", jail)
        if rc != 0:
            continue

        # Parse banned IP list
        ip_match = re.search(r"Banned IP list:\s*(.*)", stdout)
        if not ip_match:
            continue

        ips_str = ip_match.group(1).strip()
        if not ips_str:
            continue

        for ip in ips_str.split():
            ip = ip.strip()
            if not ip:
                continue
            banned_list.append(
                {
                    "ip": ip,
                    "jail": jail,
                    "status": "banned",
                }
            )

    return {"banned": banned_list, "total": len(banned_list)}


@router.get("/blacklist")
async def list_blacklist(request: Request, admin: str = Depends(require_admin)):
    """Listar IPs en la blacklist permanente."""
    entries = await _get_blacklist_ips()
    return {"blacklist": entries, "total": len(entries)}


@router.post("/blacklist")
async def add_to_blacklist(
    body: BlacklistAddRequest,
    request: Request,
    admin: str = Depends(require_admin),
):
    """Agregar IP/CIDR a la blacklist permanente."""
    ip = body.ip.strip()
    reason = _sanear_motivo(body.reason)

    if not _validate_ip_or_cidr(ip):
        raise HTTPException(400, f"IP/CIDR inválido: {ip}")

    # Check if already in blacklist
    existing = await _get_blacklist_ips()
    for entry in existing:
        if entry["ip"] == ip:
            raise HTTPException(409, f"IP {ip} ya está en la blacklist")

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    comment_line = f"# {reason} - {date_str}"
    ip_line = ip

    # 1. Add to main blacklist file
    # El ayudante hace las cuatro cosas de una vez: fichero maestro, mapa de
    # rspamd, conjunto de nftables y aviso de recarga.
    resultado = await _lista_negra("add", ip, reason)

    # 5. Audit log
    await _audit(request, admin, "firewall_blacklist_add", ip, {"reason": reason})

    return {
        "ok": True,
        "message": f"IP {ip} agregada a la blacklist permanente",
        "total": resultado.get("total"),
        "nftables": resultado.get("nftables"),
        "rspamd": resultado.get("recarga"),
    }


@router.delete("/blacklist/{ip:path}")
async def remove_from_blacklist(
    ip: str,
    request: Request,
    admin: str = Depends(require_admin),
):
    """Eliminar IP de la blacklist permanente."""
    ip = ip.strip()
    if not _validate_ip_or_cidr(ip):
        raise HTTPException(400, f"IP/CIDR inválido: {ip}")

    # 1. Remove from blacklist file
    content = await _read_file(BLACKLIST_FILE)
    lines = content.splitlines()
    new_lines = []
    skip_next = False
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == ip:
            found = True
            # Also remove the comment line before it if it exists
            if new_lines and new_lines[-1].strip().startswith("#"):
                new_lines.pop()
            continue
        new_lines.append(line)

    if not found:
        raise HTTPException(404, f"IP {ip} no encontrada en la blacklist")

    resultado = await _lista_negra("remove", ip)

    # 5. Audit log
    await _audit(request, admin, "firewall_blacklist_remove", ip)

    return {
        "ok": True,
        "message": f"IP {ip} eliminada de la blacklist",
        "total": resultado.get("total"),
        "nftables": resultado.get("nftables"),
        "rspamd": resultado.get("recarga"),
    }


@router.post("/ban-to-permanent")
async def ban_to_permanent(
    body: BanToPermanentRequest,
    request: Request,
    admin: str = Depends(require_admin),
):
    """Promover un ban temporal de fail2ban a blacklist permanente."""
    ip = body.ip.strip()
    if not _validate_ip_or_cidr(ip):
        raise HTTPException(400, f"IP inválido: {ip}")

    reason = "Reincidente - promovido desde fail2ban"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    comment_line = f"# {reason} - {date_str}"

    # Check if already in blacklist
    existing = await _get_blacklist_ips()
    for entry in existing:
        if entry["ip"] == ip:
            return {
                "ok": True,
                "message": f"IP {ip} ya estaba en la blacklist permanente",
            }

    # Add to blacklist
    await _lista_negra("add", ip, reason)

    await _audit(request, admin, "firewall_ban_to_permanent", ip, {"reason": reason})

    return {"ok": True, "message": f"IP {ip} promovida a blacklist permanente"}


@router.get("/fail2ban/config")
async def fail2ban_config(request: Request, admin: str = Depends(require_admin)):
    """Obtener configuración actual de cada jail de fail2ban."""
    configs = {}
    for jail in FAIL2BAN_JAILS:
        jail_config = {"name": jail}

        for prop in ["bantime", "maxretry", "findtime"]:
            stdout, _, rc = await _run_cmd("fail2ban-client", "get", jail, prop)
            if rc == 0:
                val = stdout.strip()
                try:
                    jail_config[prop] = int(val)
                except ValueError:
                    jail_config[prop] = val
            else:
                jail_config[prop] = None

        # Human-readable bantime
        if isinstance(jail_config.get("bantime"), int):
            secs = jail_config["bantime"]
            if secs >= 86400:
                jail_config["bantime_human"] = f"{secs // 86400} día(s)"
            elif secs >= 3600:
                jail_config["bantime_human"] = f"{secs // 3600} hora(s)"
            else:
                jail_config["bantime_human"] = f"{secs // 60} minuto(s)"
        else:
            jail_config["bantime_human"] = str(jail_config.get("bantime", "N/A"))

        # Human-readable findtime
        if isinstance(jail_config.get("findtime"), int):
            secs = jail_config["findtime"]
            if secs >= 86400:
                jail_config["findtime_human"] = f"{secs // 86400} día(s)"
            elif secs >= 3600:
                jail_config["findtime_human"] = f"{secs // 3600} hora(s)"
            else:
                jail_config["findtime_human"] = f"{secs // 60} minuto(s)"
        else:
            jail_config["findtime_human"] = str(jail_config.get("findtime", "N/A"))

        configs[jail] = jail_config

    return {"jails": configs}


# ── Geo-acceso webmail por país (default: solo Ecuador) ──────────────
# El acceso a webmail/IMAP/submission (443/143/993/465/587) está restringido
# a Ecuador. El admin abre/cierra países aquí (p. ej. cuando alguien viaja).
# La red interna y el VPN SIEMPRE tienen acceso (no dependen de esta lista).

GEO_COUNTRY_SCRIPT = "/usr/local/sbin/geoip-country.sh"
_CC_RE = re.compile(r"^[a-z]{2}$")


@router.get("/countries")
async def list_geo_countries(request: Request, admin: str = Depends(require_admin)):
    """Lista los países y si tienen acceso a webmail habilitado."""
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT code, name, enabled, updated_by, updated_at "
        "FROM geo_webmail_countries ORDER BY name"
    )
    return {"countries": [dict(r) for r in rows]}


@router.post("/countries/{code}/{action}")
async def toggle_geo_country(
    code: str,
    action: str,
    request: Request,
    admin: str = Depends(require_admin),
):
    """Abre (enable) o cierra (disable) el acceso webmail de un país y aplica en caliente."""
    code = code.lower()
    if not _CC_RE.match(code):
        raise HTTPException(400, "Código de país inválido (usar ISO-2, ej. 'es')")
    if action not in ("enable", "disable"):
        raise HTTPException(400, "Acción inválida (enable|disable)")
    if code == "ec" and action == "disable":
        raise HTTPException(400, "Ecuador no se puede cerrar (acceso base)")

    stdout, stderr, rc = await _run_cmd(GEO_COUNTRY_SCRIPT, action, code, timeout=90)
    if rc != 0:
        raise HTTPException(500, f"Error aplicando cambio: {stderr or stdout}")

    await _audit(
        request,
        admin,
        f"geo_country_{action}",
        target=code,
        details={"stdout": stdout.strip()[-300:]},
    )
    return {
        "status": "ok",
        "code": code,
        "action": action,
        "detail": stdout.strip()[-300:],
    }
