import asyncio
import re
from asyncio.subprocess import PIPE
from app.wrappers.privilegios import con_sudo

_USER_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_user(u: str):
    if not _USER_RE.match(u):
        raise ValueError(f"Username invalido: {u}")


# --- Blindaje de argumentos (fase 2 del panel, 2026-09-04) --------------------
#
# Estas llamadas NO pasan por un intérprete de comandos, así que no hay inyección
# de shell. El riesgo es otro y es real: varios argumentos llegan desde la
# petición HTTP (la carpeta y la consulta de búsqueda) y se colocan tal cual en
# la línea de órdenes. Un valor que empiece por guion deja de ser un dato y pasa
# a ser una OPCIÓN de doveadm. La peligrosa es `-o ajuste=valor`, que sobrescribe
# la configuración de Dovecot en esa invocación.
#
# Hoy el panel corre como root, así que esto ya importa. Cuando pase a correr con
# usuario propio y sudo acotado, importaría MÁS: el sudoers sería impecable sobre
# una orden que interpola datos del usuario, que es el mismo fallo de C-4 y C-5
# con otra ropa. Por eso se cierra ANTES de conceder el sudo, no después.
#
# Regla: ningún argumento de origen externo puede empezar por guion, y los
# nombres de carpeta se limitan al juego de caracteres que Dovecot usa de verdad.

_FOLDER_RE = re.compile(r"^[A-Za-z0-9 _.\-/&+()\[\]]{1,255}$")


def _validate_folder(f: str) -> str:
    """Valida un nombre de buzón que viene de la petición."""
    if not f or not _FOLDER_RE.match(f) or f.startswith("-") or ".." in f:
        raise ValueError(f"Nombre de carpeta invalido: {f!r}")
    return f


def _validate_query_tokens(tokens: list[str]) -> list[str]:
    """Rechaza tokens de búsqueda que doveadm interpretaría como opciones."""
    for t in tokens:
        if t.startswith("-"):
            raise ValueError(
                f"Termino de busqueda invalido: {t!r} (no se admiten opciones)")
    return tokens


async def _run(*cmd: str) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(*con_sudo(*cmd), stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return out.decode(), err.decode(), proc.returncode


async def generate_password_hash(password: str) -> str:
    out, err, rc = await _run("doveadm", "pw", "-s", "SHA512-CRYPT", "-p", password)
    if rc != 0:
        raise RuntimeError(f"doveadm pw failed: {err}")
    return out.strip()


async def verify_password(username: str, password: str) -> bool:
    """Confirma que la contrasena autentica de verdad contra Dovecot/BD."""
    _validate_user(username)
    out, err, rc = await _run("doveadm", "auth", "test", username, password)
    return rc == 0 and "auth succeeded" in (out + err).lower()


async def get_quota(username: str) -> dict:
    _validate_user(username)
    quota = {"used_bytes": 0, "limit_bytes": 0, "percent": 0, "messages": 0}
    
    # Try doveadm quota first
    out, _, rc = await _run("doveadm", "quota", "get", "-u", username)
    if rc == 0 and out.strip():
        for line in out.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 4:
                if "STORAGE" in parts:
                    idx = parts.index("STORAGE")
                    quota["used_bytes"] = int(parts[idx+1]) * 1024
                    quota["limit_bytes"] = int(parts[idx+2]) * 1024 if parts[idx+2] != "-" else 0
                    if quota["limit_bytes"] > 0:
                        quota["percent"] = round(quota["used_bytes"] / quota["limit_bytes"] * 100, 1)
                elif "MESSAGE" in parts:
                    idx = parts.index("MESSAGE")
                    quota["messages"] = int(parts[idx+1])
        return quota
    
    # Fallback: use du for disk usage
    domain = username.split("@")[1] if "@" in username else ""
    local = username.split("@")[0] if "@" in username else username
    maildir = f"/var/vmail/{domain}/{local}"
    out, _, rc = await _run("du", "-sb", maildir)
    if rc == 0 and out.strip():
        try:
            quota["used_bytes"] = int(out.split()[0])
        except (ValueError, IndexError):
            pass
    # Count messages
    out2, _, rc2 = await _run("find", maildir, "-name", "*.eml", "-o", "-name", "*,S*", "-type", "f")
    if rc2 == 0:
        quota["messages"] = len([l for l in out2.strip().split("\n") if l.strip()])
    
    return quota


async def list_mailboxes(username: str) -> list[str]:
    _validate_user(username)
    out, _, _ = await _run("doveadm", "mailbox", "list", "-u", username)
    return [l.strip() for l in out.strip().split("\n") if l.strip()]


async def get_who() -> list[dict]:
    out, _, _ = await _run("doveadm", "who")
    connections = []
    for line in out.strip().split("\n"):
        if not line.strip() or line.startswith("username"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            connections.append({
                "username": parts[0],
                "service": parts[1],
                "connections": int(parts[2]) if parts[2].isdigit() else 1,
                "ips": parts[3] if len(parts) > 3 else "",
            })
    return connections


async def search_messages(username: str, query: str) -> list[dict]:
    _validate_user(username)
    tokens = _validate_query_tokens(query.split())
    out, _, rc = await _run("doveadm", "search", "-u", username, *tokens)
    results = []
    for line in out.strip().split("\n"):
        parts = line.strip().split()
        if len(parts) >= 2:
            results.append({"mailbox_guid": parts[0], "uid": parts[1]})
    return results


async def fetch_message_headers(username: str, mailbox_guid: str, uid: str) -> dict:
    _validate_user(username)
    out, _, rc = await _run(
        "doveadm", "fetch", "-u", username,
        "hdr.subject hdr.from hdr.date hdr.to flags mailbox",
        "mailbox-guid", mailbox_guid, "uid", uid,
    )
    msg = {}
    for line in out.strip().split("\n"):
        if line.startswith("hdr.subject:"):
            msg["subject"] = line.split(":", 1)[1].strip()
        elif line.startswith("hdr.from:"):
            msg["from"] = line.split(":", 1)[1].strip()
        elif line.startswith("hdr.date:"):
            msg["date"] = line.split(":", 1)[1].strip()
        elif line.startswith("hdr.to:"):
            msg["to"] = line.split(":", 1)[1].strip()
        elif line.startswith("flags:"):
            msg["flags"] = line.split(":", 1)[1].strip()
        elif line.startswith("mailbox:"):
            msg["mailbox"] = line.split(":", 1)[1].strip()
    return msg


async def move_message(username: str, dest_mailbox: str, mailbox_guid: str, uid: str) -> bool:
    _validate_user(username)
    _, err, rc = await _run(
        "doveadm", "move", "-u", username, dest_mailbox,
        "mailbox-guid", mailbox_guid, "uid", uid,
    )
    return rc == 0


async def expunge(username: str, query_parts: list[str]) -> bool:
    _validate_user(username)
    _, _, rc = await _run("doveadm", "expunge", "-u", username, *query_parts)
    return rc == 0


async def force_resync(username: str, mailbox: str = "*") -> bool:
    _validate_user(username)
    _, _, rc = await _run("doveadm", "force-resync", "-u", username, mailbox)
    return rc == 0


async def get_mailbox_status(username: str) -> list[dict]:
    """Get status of all mailboxes. Output format: 'Folder Name messages=N recent=N unseen=N'"""
    _validate_user(username)
    out, _, _ = await _run(
        "doveadm", "mailbox", "status", "-u", username, "messages unseen recent", "*"
    )
    boxes = []
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        # Format: "Folder Name messages=123 recent=0 unseen=5"
        m_msgs = re.search(r'messages=(\d+)', line)
        m_unseen = re.search(r'unseen=(\d+)', line)
        m_recent = re.search(r'recent=(\d+)', line)
        if m_msgs:
            # Folder name is everything before first key=value
            folder_name = re.split(r'\s+messages=', line)[0].strip()
            boxes.append({
                "mailbox": folder_name,
                "messages": int(m_msgs.group(1)),
                "unseen": int(m_unseen.group(1)) if m_unseen else 0,
                "recent": int(m_recent.group(1)) if m_recent else 0,
            })
    return boxes
