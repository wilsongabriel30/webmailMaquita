import pytest

# test_mime_deliverability.py es un script autónomo (imprime y termina con sys.exit):
# se ejecuta a mano antes de tocar smtp_client.py, no lo recolecta pytest.
collect_ignore = ["test_mime_deliverability.py"]
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Redis real para las pruebas de gran escala (temporal, el del CI o PRUEBAS_REDIS_URL;
# si no hay ninguno, esas pruebas se saltan). Ver tests/_escala_servicios.py.
from tests._escala_servicios import redis, url_redis  # noqa: E402,F401
