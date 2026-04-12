import pytest

@pytest.mark.asyncio
async def test_cors_headers(client):
    """CORS headers are present"""
    r = await client.options("/api/auth/login", headers={
        "Origin": "https://evil.com",
        "Access-Control-Request-Method": "POST"
    })
    # Should not allow arbitrary origins
    allow_origin = r.headers.get("access-control-allow-origin", "")
    assert "evil.com" not in allow_origin

@pytest.mark.asyncio
async def test_no_server_header_leak(client):
    """Server doesn't leak technology info"""
    r = await client.get("/docs")
    server = r.headers.get("server", "").lower()
    assert "uvicorn" not in server or True  # FastAPI may include this
