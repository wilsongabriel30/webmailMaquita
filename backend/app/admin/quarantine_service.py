"""
Servicio de cuarentena de spam para el panel de administración.
Permite listar correos en Junk de todos los usuarios, aprobarlos (mover a Inbox)
o confirmarlos como spam (dejar en Junk o eliminar).
"""
import subprocess
import asyncio
import re
from datetime import datetime


async def run_doveadm(command: str, *args: str) -> str:
    """Ejecuta un comando doveadm y retorna la salida."""
    cmd = ["/usr/bin/doveadm", command] + list(args)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


async def list_all_users() -> list[str]:
    """Lista todos los usuarios de correo."""
    output = await run_doveadm("user", "*")
    return [u.strip() for u in output.strip().split("\n") if u.strip()]


async def get_junk_messages(username: str, limit: int = 50) -> list[dict]:
    """Lista mensajes en carpeta Junk de un usuario."""
    output = await run_doveadm(
        "fetch", "-u", username,
        "uid date.received from subject flags",
        "mailbox", "Junk"
    )
    messages = []
    current = {}
    for line in output.split("\n"):
        if line.startswith("uid: "):
            if current:
                messages.append(current)
            current = {"uid": line[5:].strip(), "username": username}
        elif line.startswith("date.received: "):
            current["date"] = line[15:].strip()
        elif line.startswith("from: "):
            current["from"] = line[6:].strip()
        elif line.startswith("subject: "):
            current["subject"] = line[9:].strip()
        elif line.startswith("flags: "):
            current["flags"] = line[7:].strip()
    if current and "uid" in current:
        messages.append(current)
    return messages[-limit:]


async def get_all_junk_messages(limit: int = 100) -> list[dict]:
    """Lista mensajes Junk de TODOS los usuarios."""
    users = await list_all_users()
    all_messages = []
    for user in users:
        msgs = await get_junk_messages(user, limit=20)
        all_messages.extend(msgs)
    all_messages.sort(key=lambda m: m.get("date", ""), reverse=True)
    return all_messages[:limit]


async def approve_message(username: str, uid: str) -> bool:
    """Mueve un mensaje de Junk a INBOX (falso positivo)."""
    try:
        await run_doveadm(
            "move", "-u", username,
            "INBOX", "mailbox", "Junk", "uid", uid
        )
        return True
    except Exception:
        return False


async def confirm_spam(username: str, uid: str) -> bool:
    """Confirma que es spam y lo marca como leido en Junk."""
    try:
        await run_doveadm(
            "flags", "-u", username,
            "add", "\\Seen", "mailbox", "Junk", "uid", uid
        )
        return True
    except Exception:
        return False


async def delete_spam(username: str, uid: str) -> bool:
    """Elimina un mensaje de Junk permanentemente."""
    try:
        await run_doveadm(
            "expunge", "-u", username,
            "mailbox", "Junk", "uid", uid
        )
        return True
    except Exception:
        return False


async def get_spam_filter_log(lines: int = 50) -> list[dict]:
    """Lee el log del filtro spam Python."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tail", "-n", str(lines), "/var/log/maquita-spam-filter.log",
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        entries = []
        for line in stdout.decode("utf-8", errors="replace").strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(" | ")
            if len(parts) >= 2:
                entries.append({
                    "timestamp": parts[0].strip(),
                    "level": parts[1].strip() if len(parts) > 1 else "",
                    "verdict": parts[2].strip() if len(parts) > 2 else "",
                    "details": " | ".join(parts[3:]) if len(parts) > 3 else ""
                })
        return entries
    except Exception:
        return []


async def get_keywords() -> str:
    """Lee el archivo de keywords."""
    try:
        with open("/etc/maquita-mail/spam-keywords.txt", "r") as f:
            return f.read()
    except Exception:
        return ""


async def save_keywords(content: str) -> bool:
    """Guarda el archivo de keywords."""
    try:
        with open("/etc/maquita-mail/spam-keywords.txt", "w") as f:
            f.write(content)
        return True
    except Exception:
        return False


async def get_whitelist() -> str:
    """Lee el archivo de whitelist."""
    try:
        with open("/etc/maquita-mail/whitelist-senders.txt", "r") as f:
            return f.read()
    except Exception:
        return ""


async def save_whitelist(content: str) -> bool:
    """Guarda el archivo de whitelist."""
    try:
        with open("/etc/maquita-mail/whitelist-senders.txt", "w") as f:
            f.write(content)
        return True
    except Exception:
        return False
