import pytest

@pytest.mark.asyncio
async def test_api_docs(client):
    """API docs endpoint responds"""
    r = await client.get("/docs")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_openapi_schema(client):
    """OpenAPI schema is valid"""
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data
    assert "/api/auth/login" in data["paths"]
