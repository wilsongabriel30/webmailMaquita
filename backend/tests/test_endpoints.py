import pytest

PROTECTED_ENDPOINTS = [
    ("GET", "/api/mail/folders"),
    ("GET", "/api/mail/messages/INBOX"),
    ("GET", "/api/contacts/"),
    ("GET", "/api/calendar/calendars"),
    ("GET", "/api/tasks/boards"),
    ("GET", "/api/identities/"),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_protected_endpoint_rejects_unauth(client, method, path):
    """Protected endpoints return 401/403, never 500"""
    if method == "GET":
        r = await client.get(path)
    elif method == "POST":
        r = await client.post(path, json={})
    assert r.status_code in (401, 403, 307), f"{method} {path} returned {r.status_code}"
    assert r.status_code != 500, f"{method} {path} crashed with 500"
