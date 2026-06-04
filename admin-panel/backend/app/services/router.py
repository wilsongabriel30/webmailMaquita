import asyncio
import json
import re
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/services", tags=["services"])

MANAGED_SERVICES = {
    "postfix": {"unit": "postfix", "label": "Postfix (SMTP)"},
    "dovecot": {"unit": "dovecot", "label": "Dovecot (IMAP/POP3)"},
    "rspamd": {"unit": "rspamd", "label": "Rspamd (Anti-Spam)"},
    "redis": {"unit": "redis-server", "label": "Redis"},
    "postgresql": {"unit": "postgresql", "label": "PostgreSQL"},
    "nginx": {"unit": "nginx", "label": "Nginx"},
    "clamav": {"unit": "clamav-daemon", "label": "ClamAV (Antivirus)"},
    "fail2ban": {"unit": "fail2ban", "label": "Fail2ban (Firewall)"},
}

# Postfix params safe to edit from UI
POSTFIX_EDITABLE = {
    "message_size_limit", "mailbox_size_limit", "smtpd_recipient_limit",
    "smtp_tls_security_level", "smtpd_tls_security_level",
    "myhostname", "mydomain", "myorigin", "mydestination",
    "inet_interfaces", "inet_protocols",
    "smtpd_banner", "maximal_queue_lifetime", "bounce_queue_lifetime",
    "smtpd_client_connection_rate_limit", "smtpd_client_message_rate_limit",
    "header_size_limit", "virtual_mailbox_limit",
}

# Postfix params to show (read-only + editable)
POSTFIX_SHOW = POSTFIX_EDITABLE | {
    "mail_version", "queue_directory", "command_directory",
    "virtual_transport", "virtual_mailbox_domains",
    "smtpd_sasl_auth_enable", "smtpd_sasl_type",
}


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


async def _run(*cmd) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


def _get_unit(service_key: str) -> str:
    svc = MANAGED_SERVICES.get(service_key)
    if not svc:
        raise HTTPException(400, f"Servicio no reconocido: {service_key}")
    return svc["unit"]


# ── Service status & actions ──

@router.get("")
async def list_services(admin: dict = Depends(get_current_admin)):
    results = []
    for key, info in MANAGED_SERVICES.items():
        unit = info["unit"]
        status_out, _, _ = await _run("systemctl", "is-active", unit)
        enabled_out, _, _ = await _run("systemctl", "is-enabled", unit)
        show_out, _, _ = await _run(
            "systemctl", "show", unit,
            "--property=MainPID,MemoryCurrent,ActiveEnterTimestamp,SubState"
        )
        props = {}
        for line in show_out.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
        results.append({
            "key": key, "label": info["label"], "unit": unit,
            "status": status_out.strip(), "enabled": enabled_out.strip(),
            "pid": int(props.get("MainPID", 0)) or None,
            "memory_bytes": int(props.get("MemoryCurrent", 0)) if props.get("MemoryCurrent", "").isdigit() else None,
            "since": props.get("ActiveEnterTimestamp", ""),
            "sub_state": props.get("SubState", ""),
        })
    return results


@router.get("/fail2ban/jails")
async def fail2ban_jails(admin: dict = Depends(get_current_admin)):
    jails_raw, _, _ = await _run("sudo", "fail2ban-client", "status")
    jails = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = line.split(":", 1)[1].strip().split(",")
            for name in names:
                name = name.strip()
                if not name:
                    continue
                detail, _, _ = await _run("sudo", "fail2ban-client", "status", name)
                banned = 0
                total_banned = 0
                banned_ips = []
                for dl in detail.split("\n"):
                    dl = dl.strip()
                    if "Currently banned:" in dl:
                        banned = int(dl.split(":")[-1].strip())
                    elif "Total banned:" in dl:
                        total_banned = int(dl.split(":")[-1].strip())
                    elif "Banned IP list:" in dl:
                        ip_str = dl.split(":", 1)[-1].strip()
                        if ip_str:
                            banned_ips = ip_str.split()
                jails.append({
                    "name": name, "currently_banned": banned,
                    "total_banned": total_banned, "banned_ips": banned_ips,
                })
    return jails


@router.get("/fail2ban/search/{ip}")
async def fail2ban_search_ip(ip: str, admin: dict = Depends(get_current_admin)):
    """Buscar en que jails esta baneada una IP."""
    if not re.match(r"^[\d.:a-fA-F]+$", ip):
        raise HTTPException(400, "IP invalida")
    jails_raw, _, _ = await _run("sudo", "fail2ban-client", "status")
    found_in = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = [n.strip() for n in line.split(":", 1)[1].strip().split(",") if n.strip()]
            for name in names:
                detail, _, _ = await _run("sudo", "fail2ban-client", "status", name)
                for dl in detail.split("\n"):
                    if "Banned IP list:" in dl:
                        ips = dl.split(":", 1)[-1].strip().split()
                        if ip in ips:
                            found_in.append(name)
    return {"ip": ip, "banned_in": found_in, "is_banned": len(found_in) > 0}


@router.post("/fail2ban/unban")
async def fail2ban_unban(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    jail = data.get("jail", "")
    ip = data.get("ip", "")
    if not jail or not ip:
        raise HTTPException(400, "jail e ip requeridos")
    out, err, rc = await _run("sudo", "fail2ban-client", "set", jail, "unbanip", ip)
    await _audit(request, admin, "fail2ban_unban", ip, {"jail": jail})
    if rc != 0:
        return {"ok": False, "error": err or out}
    return {"ok": True, "jail": jail, "ip": ip}


@router.post("/fail2ban/unban-all")
async def fail2ban_unban_all(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Desbanear IP de TODOS los jails donde este baneada."""
    data = await request.json()
    ip = data.get("ip", "")
    if not ip:
        raise HTTPException(400, "ip requerida")
    # Find all jails
    jails_raw, _, _ = await _run("sudo", "fail2ban-client", "status")
    unbanned_from = []
    errors = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = [n.strip() for n in line.split(":", 1)[1].strip().split(",") if n.strip()]
            for name in names:
                detail, _, _ = await _run("sudo", "fail2ban-client", "status", name)
                for dl in detail.split("\n"):
                    if "Banned IP list:" in dl and ip in dl.split(":", 1)[-1].strip().split():
                        out, err, rc = await _run("sudo", "fail2ban-client", "set", name, "unbanip", ip)
                        if rc == 0:
                            unbanned_from.append(name)
                        else:
                            errors.append({"jail": name, "error": err or out})
    await _audit(request, admin, "fail2ban_unban_all", ip, {"jails": unbanned_from})
    return {"ok": True, "ip": ip, "unbanned_from": unbanned_from, "errors": errors}


@router.post("/fail2ban/ban")
async def fail2ban_ban(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    jail = data.get("jail", "")
    ip = data.get("ip", "")
    if not jail or not ip:
        raise HTTPException(400, "jail e ip requeridos")
    out, err, rc = await _run("sudo", "fail2ban-client", "set", jail, "banip", ip)
    await _audit(request, admin, "fail2ban_ban", ip, {"jail": jail})
    if rc != 0:
        return {"ok": False, "error": err or out}
    return {"ok": True, "jail": jail, "ip": ip}


@router.post("/fail2ban/ban-all")
async def fail2ban_ban_all(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Banear IP en TODOS los jails."""
    data = await request.json()
    ip = data.get("ip", "")
    if not ip:
        raise HTTPException(400, "ip requerida")
    jails_raw, _, _ = await _run("sudo", "fail2ban-client", "status")
    banned_in = []
    errors = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = [n.strip() for n in line.split(":", 1)[1].strip().split(",") if n.strip()]
            for name in names:
                out, err, rc = await _run("sudo", "fail2ban-client", "set", name, "banip", ip)
                if rc == 0:
                    banned_in.append(name)
                else:
                    errors.append({"jail": name, "error": err or out})
    await _audit(request, admin, "fail2ban_ban_all", ip, {"jails": banned_in})
    return {"ok": True, "ip": ip, "banned_in": banned_in, "errors": errors}


@router.get("/fail2ban/jail-config/{jail_name}")
async def fail2ban_jail_config(jail_name: str, admin: dict = Depends(get_current_admin)):
    """Get config of a specific fail2ban jail."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", jail_name):
        raise HTTPException(400, "Nombre de jail invalido")
    config = {}
    for prop in ["bantime", "maxretry", "findtime"]:
        out, _, rc = await _run("sudo", "fail2ban-client", "get", jail_name, prop)
        if rc == 0:
            val = out.strip()
            try:
                config[prop] = int(val)
            except ValueError:
                config[prop] = val
    return {"jail": jail_name, "config": config}


@router.put("/fail2ban/jail-config/{jail_name}")
async def fail2ban_update_jail_config(
    jail_name: str, request: Request,
    admin: dict = Depends(require_role("superadmin")),
):
    """Update fail2ban jail config (bantime, maxretry, findtime)."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", jail_name):
        raise HTTPException(400, "Nombre de jail invalido")
    data = await request.json()
    allowed = {"bantime", "maxretry", "findtime"}
    results = {}
    for k, v in data.items():
        if k not in allowed:
            continue
        out, err, rc = await _run("sudo", "fail2ban-client", "set", jail_name, k, str(v))
        results[k] = {"ok": rc == 0, "value": str(v), "error": err if rc != 0 else None}
    await _audit(request, admin, "fail2ban_config", jail_name, data)
    return {"ok": True, "jail": jail_name, "results": results}


# ── Service detail & logs ──

@router.get("/{service_key}")
async def service_detail(service_key: str, admin: dict = Depends(get_current_admin)):
    unit = _get_unit(service_key)
    out, _, _ = await _run("systemctl", "status", unit, "--no-pager", "-l")
    return {"key": service_key, "unit": unit, "status_output": out}


@router.post("/{service_key}/{action}")
async def service_action(
    service_key: str, action: str, request: Request,
    admin: dict = Depends(require_role("superadmin")),
):
    if action not in ("start", "stop", "restart", "reload"):
        raise HTTPException(400, f"Accion invalida: {action}")
    unit = _get_unit(service_key)
    if action == "stop" and service_key in ("postgresql", "nginx"):
        raise HTTPException(400, f"No se puede detener {service_key}: servicio critico")
    out, err, rc = await _run("systemctl", action, unit)
    await _audit(request, admin, f"service_{action}", service_key, {"unit": unit, "rc": rc})
    if rc != 0:
        return {"ok": False, "error": err or out, "rc": rc}
    return {"ok": True, "action": action, "service": service_key}


@router.get("/{service_key}/logs")
async def service_logs(
    service_key: str, lines: int = Query(100, ge=10, le=1000),
    admin: dict = Depends(get_current_admin),
):
    unit = _get_unit(service_key)
    out, _, _ = await _run("journalctl", "-u", unit, "--no-pager", "-n", str(lines), "--output=short-iso")
    log_lines = [l for l in out.strip().split("\n") if l.strip()]
    return {"service": service_key, "lines": log_lines}


# ── Service configuration ──

@router.get("/{service_key}/config")
async def service_config(service_key: str, admin: dict = Depends(get_current_admin)):
    """Read config for a service."""
    if service_key == "postfix":
        return await _postfix_config()
    elif service_key == "dovecot":
        return await _dovecot_config()
    elif service_key == "rspamd":
        return await _rspamd_config()
    elif service_key == "fail2ban":
        return await _fail2ban_config()
    elif service_key == "nginx":
        return await _nginx_config()
    elif service_key == "clamav":
        return await _clamav_config()
    else:
        return {"service": service_key, "config": {}, "editable": [], "message": "Configuracion no disponible para este servicio"}


@router.put("/{service_key}/config")
async def update_service_config(
    service_key: str, request: Request,
    admin: dict = Depends(require_role("superadmin")),
):
    """Update config for a service."""
    data = await request.json()
    if service_key == "postfix":
        return await _update_postfix(data, request, admin)
    elif service_key == "fail2ban":
        # Handled by jail-specific endpoint
        raise HTTPException(400, "Use /fail2ban/jail-config/{jail} para configurar fail2ban")
    else:
        raise HTTPException(400, f"Edicion de configuracion no soportada para {service_key}")


async def _postfix_config():
    params = {}
    for key in POSTFIX_SHOW:
        out, _, rc = await _run("postconf", key)
        if rc == 0 and "=" in out:
            val = out.split("=", 1)[1].strip()
            params[key] = val
    return {
        "service": "postfix",
        "config": params,
        "editable": sorted(POSTFIX_EDITABLE),
    }


async def _update_postfix(data: dict, request, admin):
    results = {}
    changed = []
    for k, v in data.items():
        if k not in POSTFIX_EDITABLE:
            results[k] = {"ok": False, "error": "Parametro no editable"}
            continue
        # Validate: no shell injection
        safe_val = str(v).replace("'", "")
        out, err, rc = await _run("postconf", "-e", f"{k}={safe_val}")
        results[k] = {"ok": rc == 0, "error": err if rc != 0 else None}
        if rc == 0:
            changed.append(k)
    if changed:
        await _audit(request, admin, "postfix_config", ",".join(changed), data)
        # Reload postfix to apply
        await _run("systemctl", "reload", "postfix")
    return {"ok": True, "results": results, "reloaded": len(changed) > 0}


async def _dovecot_config():
    out, _, _ = await _run("doveconf", "-n")
    lines = out.strip().split("\n")
    config = {}
    for line in lines[:100]:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip()
    return {"service": "dovecot", "config": config, "editable": []}


async def _rspamd_config():
    # Show rspamd actions config
    config = {}
    actions_conf = "/etc/rspamd/local.d/actions.conf"
    try:
        out, _, rc = await _run("cat", actions_conf)
        if rc == 0:
            config["actions.conf"] = out[:2000]
    except Exception:
        pass
    # Show milter headers
    milter_conf = "/etc/rspamd/local.d/milter_headers.conf"
    out2, _, rc2 = await _run("cat", milter_conf)
    if rc2 == 0:
        config["milter_headers.conf"] = out2[:2000]
    return {"service": "rspamd", "config": config, "editable": []}


async def _fail2ban_config():
    # List jails and their basic config
    jails_raw, _, _ = await _run("sudo", "fail2ban-client", "status")
    jails = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = [n.strip() for n in line.split(":", 1)[1].strip().split(",") if n.strip()]
            for name in names:
                cfg = {}
                for prop in ["bantime", "maxretry", "findtime"]:
                    out, _, rc = await _run("sudo", "fail2ban-client", "get", name, prop)
                    if rc == 0:
                        try:
                            cfg[prop] = int(out.strip())
                        except ValueError:
                            cfg[prop] = out.strip()
                jails.append({"name": name, "config": cfg})
    return {"service": "fail2ban", "jails": jails, "editable": ["bantime", "maxretry", "findtime"]}


async def _nginx_config():
    out, _, rc = await _run("nginx", "-T")
    if rc != 0:
        return {"service": "nginx", "config": {}, "editable": []}
    # Only return the mail proxy / admin panel parts (limit output)
    lines = out.split("\n")
    config_text = "\n".join(lines[:200])
    return {"service": "nginx", "config": {"nginx.conf": config_text}, "editable": []}


async def _clamav_config():
    config = {}
    for path in ["/etc/clamav/clamd.conf", "/etc/clamav/freshclam.conf"]:
        out, _, rc = await _run("cat", path)
        if rc == 0:
            config[path.split("/")[-1]] = out[:2000]
    return {"service": "clamav", "config": config, "editable": []}
