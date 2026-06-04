import httpx
from app.config import RSPAMD_URL, RSPAMD_PASSWORD

_HEADERS = {}
if RSPAMD_PASSWORD:
    _HEADERS["Password"] = RSPAMD_PASSWORD


async def _get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{RSPAMD_URL}{path}", headers=_HEADERS)
        r.raise_for_status()
        return r.json()


async def _post(path: str, data=None, content=None, extra_headers=None) -> dict:
    headers = {**_HEADERS, **(extra_headers or {})}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{RSPAMD_URL}{path}", json=data, content=content, headers=headers)
        r.raise_for_status()
        return r.json()


async def get_stat() -> dict:
    return await _get("/stat")


async def get_history(offset: int = 0, limit: int = 50) -> list[dict]:
    data = await _get(f"/history?offset={offset}&limit={limit}")
    return data.get("rows", []) if isinstance(data, dict) else data


async def get_errors() -> list[dict]:
    data = await _get("/errors")
    return data if isinstance(data, list) else []


async def get_graphs(type_: str = "rrd") -> dict:
    return await _get(f"/graph?type={type_}")


async def learn_spam(message: bytes) -> dict:
    return await _post("/learnspam", content=message)


async def learn_ham(message: bytes) -> dict:
    return await _post("/learnham", content=message)


async def check_message(message: bytes) -> dict:
    return await _post("/checkv2", content=message)


async def get_actions() -> dict:
    return await _get("/stat")


async def fuzzy_add(message: bytes, flag: int = 1, weight: int = 1) -> dict:
    headers = {"Flag": str(flag), "Weight": str(weight)}
    return await _post("/fuzzyadd", content=message, extra_headers=headers)
