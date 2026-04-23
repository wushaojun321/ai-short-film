"""Tests for asset CRUD and lifecycle."""
import pytest
from tests.conftest import create_project

pytestmark = pytest.mark.asyncio


async def create_asset(client, pid, name="林小雨", asset_type="character"):
    r = await client.post(f"/api/v1/projects/{pid}/assets", json={
        "name": name,
        "asset_type": asset_type,
        "prompt": "年轻女性，25岁，清秀面容",
    })
    assert r.status_code == 201
    return r.json()


class TestAssetCRUD:
    async def test_list_assets_empty(self, client):
        proj = await create_project(client)
        r = await client.get(f"/api/v1/projects/{proj['_id']}/assets")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        assert asset["name"] == "林小雨"
        assert asset["asset_type"] == "character"
        assert asset["status"] == "pending"
        assert asset["preview_url"] is None

    async def test_create_scene_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"], "皇宫大殿", "scene")
        assert asset["asset_type"] == "scene"

    async def test_list_assets(self, client):
        proj = await create_project(client)
        pid = proj["_id"]
        await create_asset(client, pid, "角色A", "character")
        await create_asset(client, pid, "场景B", "scene")
        await create_asset(client, pid, "道具C", "prop")
        r = await client.get(f"/api/v1/projects/{pid}/assets")
        assert len(r.json()) == 3

    async def test_get_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        r = await client.get(f"/api/v1/projects/{proj['_id']}/assets/{asset['_id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "林小雨"

    async def test_get_asset_not_found(self, client):
        proj = await create_project(client)
        r = await client.get(f"/api/v1/projects/{proj['_id']}/assets/000000000000000000000000")
        assert r.status_code == 404

    async def test_update_asset_prompt(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        r = await client.patch(f"/api/v1/projects/{proj['_id']}/assets/{asset['_id']}", json={
            "prompt": "更新后的提示词，古装风格"
        })
        assert r.status_code == 200
        assert r.json()["prompt"] == "更新后的提示词，古装风格"

    async def test_delete_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        aid = asset["_id"]
        r = await client.delete(f"/api/v1/projects/{proj['_id']}/assets/{aid}")
        assert r.status_code == 204
        r2 = await client.get(f"/api/v1/projects/{proj['_id']}/assets/{aid}")
        assert r2.status_code == 404

    async def test_invalid_asset_type(self, client):
        proj = await create_project(client)
        r = await client.post(f"/api/v1/projects/{proj['_id']}/assets", json={
            "name": "测试", "asset_type": "invalid_type", "prompt": "test"
        })
        assert r.status_code == 422


class TestAssetLifecycle:
    async def test_confirm_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        r = await client.post(f"/api/v1/projects/{proj['_id']}/assets/{asset['_id']}/confirm")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    async def test_regen_asset(self, client):
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        r = await client.post(f"/api/v1/projects/{proj['_id']}/assets/{asset['_id']}/regen")
        assert r.status_code == 200
        assert r.json()["status"] == "need_regen"
        assert "task_id" in r.json()

    async def test_confirm_then_regen(self, client):
        """Confirm → regen transitions status correctly."""
        proj = await create_project(client)
        asset = await create_asset(client, proj["_id"])
        pid, aid = proj["_id"], asset["_id"]

        await client.post(f"/api/v1/projects/{pid}/assets/{aid}/confirm")
        assert (await client.get(f"/api/v1/projects/{pid}/assets/{aid}")).json()["status"] == "approved"

        await client.post(f"/api/v1/projects/{pid}/assets/{aid}/regen")
        assert (await client.get(f"/api/v1/projects/{pid}/assets/{aid}")).json()["status"] == "need_regen"
