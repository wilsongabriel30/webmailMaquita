import asyncio
import json
import re
from asyncio.subprocess import PIPE

_QID_RE = re.compile(r"^[A-Fa-f0-9]{6,16}$")


def _validate_qid(qid: str):
    if not _QID_RE.match(qid):
        raise ValueError(f"Queue ID invalido: {qid}")


async def _run(*cmd: str) -> str:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0 and err:
        raise RuntimeError(err.decode().strip())
    return out.decode()


async def list_queue() -> list[dict]:
    try:
        out = await _run("sudo", "postqueue", "-j")
    except RuntimeError:
        return []
    if not out.strip():
        return []
    messages = []
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            messages.append({
                "queue_id": e.get("queue_id", ""),
                "queue_name": e.get("queue_name", ""),
                "arrival_time": e.get("arrival_time", 0),
                "message_size": e.get("message_size", 0),
                "sender": e.get("sender", ""),
                "recipients": [
                    {"address": r.get("address", ""), "delay_reason": r.get("delay_reason", "")}
                    for r in e.get("recipients", [])
                ],
            })
        except json.JSONDecodeError:
            continue
    return messages


async def flush_one(qid: str) -> bool:
    _validate_qid(qid)
    await _run("sudo", "postqueue", "-i", qid)
    return True

async def flush_all() -> bool:
    await _run("sudo", "postqueue", "-f")
    return True

async def delete_one(qid: str) -> bool:
    _validate_qid(qid)
    await _run("sudo", "postsuper", "-d", qid)
    return True

async def hold_one(qid: str) -> bool:
    _validate_qid(qid)
    await _run("sudo", "postsuper", "-h", qid)
    return True

async def release_one(qid: str) -> bool:
    _validate_qid(qid)
    await _run("sudo", "postsuper", "-H", qid)
    return True

async def delete_all() -> bool:
    await _run("sudo", "postsuper", "-d", "ALL")
    return True

async def requeue_one(qid: str) -> bool:
    _validate_qid(qid)
    await _run("sudo", "postsuper", "-r", qid)
    return True

async def requeue_all() -> bool:
    await _run("sudo", "postsuper", "-r", "ALL")
    return True
