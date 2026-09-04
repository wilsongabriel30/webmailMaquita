import asyncio
import os
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_admin
from app.wrappers.privilegios import con_sudo

router = APIRouter(prefix="/api/health", tags=["health"])


async def _run_cmd(*cmd) -> str:
    proc = await asyncio.create_subprocess_exec(*con_sudo(*cmd), stdout=PIPE, stderr=PIPE)
    out, _ = await proc.communicate()
    return out.decode().strip()


@router.get("")
async def system_health(admin: dict = Depends(get_current_admin)):
    cpu_q = _run_cmd("bash", "-c", "grep -c ^processor /proc/cpuinfo")
    load_q = _run_cmd("cat", "/proc/loadavg")
    mem_q = _run_cmd("free", "-b")
    disk_q = _run_cmd("df", "-B1", "/", "/var/vmail")
    uptime_q = _run_cmd("cat", "/proc/uptime")
    fail2ban_q = _run_cmd("sudo", "fail2ban-client", "status")

    cpu_cores, load, mem_raw, disk_raw, uptime_raw, f2b = await asyncio.gather(
        cpu_q, load_q, mem_q, disk_q, uptime_q, fail2ban_q
    )

    # Parse memory
    mem = {}
    for line in mem_raw.split("\n"):
        parts = line.split()
        if parts and parts[0] == "Mem:":
            mem = {"total": int(parts[1]), "used": int(parts[2]), "free": int(parts[3]), "available": int(parts[6]) if len(parts) > 6 else 0}
        elif parts and parts[0] == "Swap:":
            mem["swap_total"] = int(parts[1])
            mem["swap_used"] = int(parts[2])

    # Parse disk
    disks = []
    for line in disk_raw.split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 6:
            disks.append({
                "filesystem": parts[0], "size": int(parts[1]), "used": int(parts[2]),
                "available": int(parts[3]), "percent": parts[4], "mount": parts[5],
            })

    # Load average
    load_parts = load.split()

    return {
        "cpu_cores": int(cpu_cores) if cpu_cores.isdigit() else 0,
        "load_avg": {"1m": float(load_parts[0]), "5m": float(load_parts[1]), "15m": float(load_parts[2])} if len(load_parts) >= 3 else {},
        "memory": mem,
        "disks": disks,
        "uptime_seconds": float(uptime_raw.split()[0]) if uptime_raw else 0,
        "fail2ban": f2b,
    }


@router.get("/fail2ban")
async def fail2ban_status(admin: dict = Depends(get_current_admin)):
    """Detalle de jails de fail2ban."""
    jails_raw = await _run_cmd("sudo", "fail2ban-client", "status")
    jails = []
    for line in jails_raw.split("\n"):
        if "Jail list:" in line:
            names = line.split(":", 1)[1].strip().split(",")
            for name in names:
                name = name.strip()
                if name:
                    detail = await _run_cmd("sudo", "fail2ban-client", "status", name)
                    banned = 0
                    total_banned = 0
                    for dl in detail.split("\n"):
                        dl = dl.strip()
                        if "Currently banned:" in dl:
                            banned = int(dl.split(":")[-1].strip())
                        elif "Total banned:" in dl:
                            total_banned = int(dl.split(":")[-1].strip())
                    jails.append({"name": name, "currently_banned": banned, "total_banned": total_banned})
    return jails


@router.get("/connections")
async def active_connections(admin: dict = Depends(get_current_admin)):
    """Conexiones IMAP/POP3 activas."""
    from app.wrappers.doveadm import get_who
    return await get_who()
