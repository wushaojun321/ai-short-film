"""Tests for multi-turn conversation API."""
import pytest
from tests.conftest import create_project

pytestmark = pytest.mark.asyncio


async def setup_asset_with_conversation(client):
    """Create project + asset, return (project_id, asset_id)."""
    proj = await create_project(client)
    pid = proj["_id"]
    r = await client.post(f"/api/v1/projects/{pid}/assets", json={
        "name": "主角", "asset_type": "character", "prompt": "年轻女性，清秀",
    })
    aid = r.json()["_id"]
    return pid, aid


class TestConversationCRUD:
    async def test_create_conversation(self, client):
        pid, aid = await setup_asset_with_conversation(client)
        r = await client.post("/api/v1/conversations", json={
            "target_type": "asset",
            "target_id": aid,
            "project_id": pid,
            "title": "修改角色风格",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["target_type"] == "asset"
        assert data["target_id"] == aid
        assert data["messages"] == []
        assert data["is_active"] is True

    async def test_create_returns_existing_if_active(self, client):
        """Second create call returns the same conversation."""
        pid, aid = await setup_asset_with_conversation(client)
        payload = {"target_type": "asset", "target_id": aid, "project_id": pid}
        r1 = await client.post("/api/v1/conversations", json=payload)
        r2 = await client.post("/api/v1/conversations", json=payload)
        assert r1.json()["_id"] == r2.json()["_id"]

    async def test_list_by_target(self, client):
        pid, aid = await setup_asset_with_conversation(client)
        await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })
        r = await client.get(f"/api/v1/conversations/by-target/{aid}")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_get_conversation(self, client):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()
        r = await client.get(f"/api/v1/conversations/{conv['_id']}")
        assert r.status_code == 200

    async def test_get_conversation_not_found(self, client):
        r = await client.get("/api/v1/conversations/000000000000000000000000")
        assert r.status_code == 404

    async def test_close_conversation(self, client):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()
        r = await client.delete(f"/api/v1/conversations/{conv['_id']}")
        assert r.status_code == 204
        # Should create new one now (old was closed)
        r2 = await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })
        assert r2.json()["_id"] != conv["_id"]


class TestConversationMessages:
    async def test_send_message_returns_reply(self, client, mock_llm):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()

        r = await client.post(f"/api/v1/conversations/{conv['_id']}/messages", json={
            "content": "请把服装改成古装风格"
        })
        assert r.status_code == 200
        data = r.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
        assert "conversation" in data

    async def test_send_message_saves_to_conversation(self, client, mock_llm):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()
        cid = conv["_id"]

        await client.post(f"/api/v1/conversations/{cid}/messages", json={
            "content": "第一条消息"
        })
        await client.post(f"/api/v1/conversations/{cid}/messages", json={
            "content": "第二条消息"
        })

        r = await client.get(f"/api/v1/conversations/{cid}")
        messages = r.json()["messages"]
        # 2 user + 2 assistant = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    async def test_send_message_first_includes_snapshot(self, client, mock_llm):
        """First message should include artifact snapshot."""
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()

        await client.post(f"/api/v1/conversations/{conv['_id']}/messages", json={
            "content": "修改一下"
        })
        r = await client.get(f"/api/v1/conversations/{conv['_id']}")
        first_msg = r.json()["messages"][0]
        assert first_msg["artifact_snapshot"] is not None
        assert "name" in first_msg["artifact_snapshot"]  # asset snapshot has 'name'

    async def test_apply_edit_no_messages_returns_400(self, client):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()
        r = await client.post(f"/api/v1/conversations/{conv['_id']}/apply-edit")
        assert r.status_code == 400

    async def test_apply_edit_updates_asset(self, client, mock_llm):
        pid, aid = await setup_asset_with_conversation(client)
        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "asset", "target_id": aid, "project_id": pid
        })).json()
        cid = conv["_id"]

        await client.post(f"/api/v1/conversations/{cid}/messages", json={
            "content": "修改提示词"
        })
        r = await client.post(f"/api/v1/conversations/{cid}/apply-edit")
        assert r.status_code == 200
        assert "applied_changes" in r.json()


class TestConversationTargetTypes:
    """Test conversations work for different artifact types."""

    async def test_shot_script_conversation(self, client, mock_llm):
        proj = await create_project(client)
        pid = proj["_id"]
        await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={
            "episodes": [{"number": 1, "title": "EP1", "summary": "s", "word_count": 100, "estimated_duration": 60}]
        })
        eps = (await client.get(f"/api/v1/projects/{pid}/episodes")).json()
        eid = eps[0]["_id"]
        shot = (await client.post(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots",
            json={"shot_code": "S01", "order": 1, "duration": 5, "description": "测试"}
        )).json()
        sid = shot["_id"]

        conv = (await client.post("/api/v1/conversations", json={
            "target_type": "shot_script", "target_id": sid, "project_id": pid
        })).json()
        assert conv["target_type"] == "shot_script"

        r = await client.post(f"/api/v1/conversations/{conv['_id']}/messages", json={
            "content": "调整这个镜头的视角"
        })
        assert r.status_code == 200
