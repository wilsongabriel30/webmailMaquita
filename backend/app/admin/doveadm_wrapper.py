import asyncio
import re
from asyncio.subprocess import PIPE

ALLOWED_COMMANDS = {
    "quota_get": ["doveadm", "quota", "get", "-u"],
    "who": ["doveadm", "who"],
    "mailbox_list": ["doveadm", "mailbox", "list", "-u"],
    "pw": ["doveadm", "pw", "-s", "SHA512-CRYPT", "-p"],
    "force_resync": ["doveadm", "force-resync", "-u"],
    "user_info": ["doveadm", "user", "-u"],
}

# Validate usernames: user@domain format only
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise ValueError(f"Invalid username format: {username}")


async def run_doveadm(command: str, *args: str) -> str:
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {command}")

    # Validate any username arguments
    for arg in args:
        if "@" in arg:
            _validate_username(arg)

    cmd = ALLOWED_COMMANDS[command] + list(args)
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(f"doveadm {command} failed: {err}")

    return stdout.decode()


async def generate_password_hash(password: str) -> str:
    result = await run_doveadm("pw", password)
    return result.strip()


async def get_quota(username: str) -> dict:
    _validate_username(username)
    output = await run_doveadm("quota_get", username)
    quota = {"used": 0, "limit": 0, "percent": 0}
    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "STORAGE":
            quota["used"] = int(parts[1]) * 1024  # KB to bytes
            quota["limit"] = int(parts[2]) * 1024 if parts[2] != "-" else 0
            if quota["limit"] > 0:
                quota["percent"] = round(quota["used"] / quota["limit"] * 100, 1)
    return quota


async def list_mailboxes(username: str) -> list[str]:
    _validate_username(username)
    output = await run_doveadm("mailbox_list", username)
    return [line.strip() for line in output.strip().split("\n") if line.strip()]
