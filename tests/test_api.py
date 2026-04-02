import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Helix"


@pytest.mark.asyncio
async def test_webhook_without_message(client):
    response = await client.post("/api/v1/webhook/telegram", json={})
    assert response.status_code == 200
    assert response.json()["ok"] is True
