"""Tests for prompt config admin API."""
import pytest

pytestmark = pytest.mark.asyncio


class TestPromptConfigAdmin:
    async def test_list_all_scopes(self, client):
        """After seed, all 13 scopes should be available."""
        r = await client.get("/api/v1/admin/prompt-configs")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 13
        expected_scopes = [
            "script_parse", "episode_split", "continuity_extract",
            "shot_script_gen", "shot_script_edit", "asset_prompt_gen",
            "asset_prompt_edit", "shot_image_gen", "shot_image_edit",
            "shot_video_gen", "shot_video_edit", "dubbing_gen",
            "series_overview_edit",
        ]
        for scope in expected_scopes:
            assert scope in data

    async def test_get_single_scope(self, client):
        r = await client.get("/api/v1/admin/prompt-configs/script_parse")
        assert r.status_code == 200
        data = r.json()
        assert data["scope"] == "script_parse"
        assert data["is_active"] is True
        assert data["version"] == 1
        assert len(data["system_prompt"]) > 0

    async def test_get_invalid_scope(self, client):
        r = await client.get("/api/v1/admin/prompt-configs/nonexistent")
        assert r.status_code == 422  # Invalid enum value

    async def test_update_prompt_config(self, client):
        r = await client.put("/api/v1/admin/prompt-configs/script_parse", json={
            "system_prompt": "新的系统提示词，更简洁",
            "user_prompt_template": "剧本：{script_text}",
            "description": "测试更新",
            "variables": ["script_text"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["system_prompt"] == "新的系统提示词，更简洁"
        assert data["version"] == 2  # Version bumped
        assert data["is_active"] is True

    async def test_update_creates_new_version(self, client):
        """Update deactivates old version and creates new one."""
        # Update twice
        await client.put("/api/v1/admin/prompt-configs/shot_script_gen", json={
            "system_prompt": "版本2提示词",
        })
        await client.put("/api/v1/admin/prompt-configs/shot_script_gen", json={
            "system_prompt": "版本3提示词",
        })
        # Active version should be 3
        r = await client.get("/api/v1/admin/prompt-configs/shot_script_gen")
        assert r.json()["version"] == 3
        assert r.json()["system_prompt"] == "版本3提示词"

    async def test_get_history(self, client):
        # Update once to create version 2
        await client.put("/api/v1/admin/prompt-configs/asset_prompt_gen", json={
            "system_prompt": "版本2"
        })
        r = await client.get("/api/v1/admin/prompt-configs/asset_prompt_gen/history")
        assert r.status_code == 200
        history = r.json()
        assert len(history) == 2
        # Sorted by version descending
        assert history[0]["version"] == 2
        assert history[1]["version"] == 1

    async def test_rollback(self, client):
        # Update to v2
        await client.put("/api/v1/admin/prompt-configs/dubbing_gen", json={
            "system_prompt": "版本2提示词",
        })
        # Rollback to v1
        r = await client.post("/api/v1/admin/prompt-configs/dubbing_gen/rollback/1")
        assert r.status_code == 200
        assert r.json()["version"] == 1
        assert r.json()["is_active"] is True
        # Currently active should be v1
        active = (await client.get("/api/v1/admin/prompt-configs/dubbing_gen")).json()
        assert active["version"] == 1

    async def test_rollback_nonexistent_version(self, client):
        r = await client.post("/api/v1/admin/prompt-configs/script_parse/rollback/999")
        assert r.status_code == 404
