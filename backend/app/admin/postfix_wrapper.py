import asyncio
import json
import re
from asyncio.subprocess import PIPE

# Queue ID: hex characters, 6-16 chars (Postfix format)
_QUEUE_ID_RE = re.compile(r"^[A-Fa-f0-9]{6,16}$")

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"  # [S7-1] envoltorio con validación propia

ALLOWED_COMMANDS = {
    "queue_list": ["sudo", "-n", MAQUITA_SUDO, "postqueue", "-j"],
    "queue_flush_one": ["sudo", "-n", MAQUITA_SUDO, "postqueue", "-i"],
    "queue_flush_all": ["sudo", "-n", MAQUITA_SUDO, "postqueue", "-f"],
    "queue_delete": ["sudo", "-n", MAQUITA_SUDO, "postsuper", "-d"],
    "queue_hold": ["sudo", "-n", MAQUITA_SUDO, "postsuper", "-h"],
    "queue_release": ["sudo", "-n", MAQUITA_SUDO, "postsuper", "-H"],
    "queue_delete_all": ["sudo", "-n", MAQUITA_SUDO, "postsuper", "-d", "ALL"],
}


def _validate_queue_id(queue_id: str) -> None:
    if not _QUEUE_ID_RE.match(queue_id):
        raise ValueError(f"Invalid queue ID format: {queue_id}")


async def _run(cmd: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and stderr:
        err = stderr.decode().strip()
        raise RuntimeError(f"Command failed: {err}")
    return stdout.decode()


async def list_queue() -> list[dict]:
    try:
        output = await _run(ALLOWED_COMMANDS["queue_list"])
    except RuntimeError:
        return []

    if not output.strip():
        return []

    messages = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            messages.append(
                {
                    "queue_id": entry.get("queue_id", ""),
                    "queue_name": entry.get("queue_name", ""),
                    "arrival_time": entry.get("arrival_time", 0),
                    "message_size": entry.get("message_size", 0),
                    "sender": entry.get("sender", ""),
                    "recipients": [
                        {
                            "address": r.get("address", ""),
                            "delay_reason": r.get("delay_reason", ""),
                        }
                        for r in entry.get("recipients", [])
                    ],
                }
            )
        except json.JSONDecodeError:
            continue

    return messages


async def flush_one(queue_id: str) -> bool:
    _validate_queue_id(queue_id)
    await _run(ALLOWED_COMMANDS["queue_flush_one"] + [queue_id])
    return True


async def flush_all() -> bool:
    await _run(ALLOWED_COMMANDS["queue_flush_all"])
    return True


async def delete_one(queue_id: str) -> bool:
    _validate_queue_id(queue_id)
    await _run(ALLOWED_COMMANDS["queue_delete"] + [queue_id])
    return True


async def hold_one(queue_id: str) -> bool:
    _validate_queue_id(queue_id)
    await _run(ALLOWED_COMMANDS["queue_hold"] + [queue_id])
    return True


async def release_one(queue_id: str) -> bool:
    _validate_queue_id(queue_id)
    await _run(ALLOWED_COMMANDS["queue_release"] + [queue_id])
    return True


async def delete_all() -> bool:
    await _run(ALLOWED_COMMANDS["queue_delete_all"])
    return True
