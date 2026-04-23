"""Tests for shot CRUD and review workflow."""
import pytest
from tests.conftest import create_project

pytestmark = pytest.mark.asyncio


async def setup_episode(client):
    """Create project + episode, return (project_id, episode_id)."""
    proj = await create_project(client)
    pid = proj["_id"]
    await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={
        "episodes": [{"number": 1, "title": "第一集", "summary": "s", "word_count": 100, "estimated_duration": 60}]
    })
    eps = (await client.get(f"/api/v1/projects/{pid}/episodes")).json()
    return pid, eps[0]["_id"]


async def create_shot(client, pid, eid, code="S01", order=1):
    r = await client.post(
        f"/api/v1/projects/{pid}/episodes/{eid}/shots",
        json={"shot_code": code, "order": order, "duration": 5, "description": "测试镜头"}
    )
    assert r.status_code == 201
    return r.json()


class TestShotCRUD:
    async def test_list_shots_empty(self, client):
        pid, eid = await setup_episode(client)
        r = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}/shots")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_shot(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        assert shot["shot_code"] == "S01"
        assert shot["state"] == "planned"
        assert shot["order"] == 1
        assert shot["project_id"] == pid
        assert shot["episode_id"] == eid

    async def test_list_shots_ordered(self, client):
        pid, eid = await setup_episode(client)
        await create_shot(client, pid, eid, "S03", 3)
        await create_shot(client, pid, eid, "S01", 1)
        await create_shot(client, pid, eid, "S02", 2)
        r = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}/shots")
        orders = [s["order"] for s in r.json()]
        assert orders == [1, 2, 3]

    async def test_get_shot(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        r = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}/shots/{shot['_id']}")
        assert r.status_code == 200
        assert r.json()["shot_code"] == "S01"

    async def test_get_shot_not_found(self, client):
        pid, eid = await setup_episode(client)
        r = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}/shots/000000000000000000000000")
        assert r.status_code == 404

    async def test_update_shot(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        r = await client.patch(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots/{shot['_id']}",
            json={"description": "修改描述", "prompt": "新提示词", "duration": 8}
        )
        assert r.status_code == 200
        assert r.json()["description"] == "修改描述"
        assert r.json()["duration"] == 8

    async def test_delete_shot(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        sid = shot["_id"]
        r = await client.delete(f"/api/v1/projects/{pid}/episodes/{eid}/shots/{sid}")
        assert r.status_code == 204
        r2 = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}/shots/{sid}")
        assert r2.status_code == 404


class TestShotReview:
    async def test_approve_shot(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        r = await client.post(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots/{shot['_id']}/review",
            json={"approved": True}
        )
        assert r.status_code == 200
        assert r.json()["state"] == "approved"

    async def test_reject_shot_with_comment(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        r = await client.post(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots/{shot['_id']}/review",
            json={"approved": False, "comment": "光线太暗，需要重生"}
        )
        assert r.status_code == 200
        assert r.json()["state"] == "review_failed"
        assert r.json()["review_comment"] == "光线太暗，需要重生"

    async def test_batch_review(self, client):
        pid, eid = await setup_episode(client)
        s1 = await create_shot(client, pid, eid, "S01", 1)
        s2 = await create_shot(client, pid, eid, "S02", 2)
        s3 = await create_shot(client, pid, eid, "S03", 3)

        r = await client.post(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots/batch-review",
            json={"reviews": [
                {"shot_id": s1["_id"], "approved": True},
                {"shot_id": s2["_id"], "approved": False, "comment": "需重做"},
                {"shot_id": s3["_id"], "approved": True},
            ]}
        )
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 3
        states = {r["_id"]: r["state"] for r in results}
        assert states[s1["_id"]] == "approved"
        assert states[s2["_id"]] == "review_failed"
        assert states[s3["_id"]] == "approved"

    async def test_review_missing_field(self, client):
        pid, eid = await setup_episode(client)
        shot = await create_shot(client, pid, eid)
        r = await client.post(
            f"/api/v1/projects/{pid}/episodes/{eid}/shots/{shot['_id']}/review",
            json={}  # missing 'approved'
        )
        assert r.status_code == 422
