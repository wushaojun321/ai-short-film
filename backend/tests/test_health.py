"""Smoke tests: health check and basic API availability."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_openapi_available(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert data["info"]["title"] == "AI Short Film API"
    paths = list(data["paths"].keys())
    # Verify key route groups exist
    assert any("/projects" in p for p in paths)
    assert any("/episodes" in p for p in paths)
    assert any("/shots" in p for p in paths)
    assert any("/assets" in p for p in paths)
    assert any("/conversations" in p for p in paths)
    assert any("/generate" in p for p in paths)
    assert any("/admin/prompt-configs" in p for p in paths)


async def test_404_returns_json(client):
    r = await client.get("/nonexistent-route")
    assert r.status_code == 404
