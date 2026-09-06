import pytest


@pytest.mark.asyncio
async def test_api_docs(client):
    """API docs deshabilitados fuera de desarrollo [A2]"""
    r = await client.get("/docs")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_openapi_schema(client):
    """OpenAPI no se publica fuera de desarrollo [A2]; el esquema sigue disponible en memoria"""
    r = await client.get("/openapi.json")
    assert r.status_code == 404
    from app.main import app

    assert "/api/auth/login" in app.openapi()["paths"]
