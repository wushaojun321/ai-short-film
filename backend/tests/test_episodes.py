"""Tests for episode CRUD and step progression."""
import pytest
from tests.conftest import create_project

pytestmark = pytest.mark.asyncio


async def setup_project_with_episodes(client, ep_count=2):
    """Helper: create project and confirm N episodes."""
    proj = await create_project(client)
    pid = proj["_id"]
    episodes = [
        {"number": i + 1, "title": f"第{i+1}集", "summary": f"第{i+1}集简介",
         "word_count": 2000, "estimated_duration": 120}
        for i in range(ep_count)
    ]
    await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={"episodes": episodes})
    eps = (await client.get(f"/api/v1/projects/{pid}/episodes")).json()
    return pid, eps


class TestEpisodeCRUD:
    async def test_list_episodes_empty(self, client):
        proj = await create_project(client)
        r = await client.get(f"/api/v1/projects/{proj['_id']}/episodes")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_episodes(self, client):
        pid, eps = await setup_project_with_episodes(client, 3)
        r = await client.get(f"/api/v1/projects/{pid}/episodes")
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_episodes_ordered_by_number(self, client):
        pid, eps = await setup_project_with_episodes(client, 3)
        r = await client.get(f"/api/v1/projects/{pid}/episodes")
        numbers = [e["number"] for e in r.json()]
        assert numbers == sorted(numbers)

    async def test_get_episode(self, client):
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        r = await client.get(f"/api/v1/projects/{pid}/episodes/{eid}")
        assert r.status_code == 200
        assert r.json()["number"] == 1

    async def test_get_episode_not_found(self, client):
        proj = await create_project(client)
        r = await client.get(f"/api/v1/projects/{proj['_id']}/episodes/000000000000000000000000")
        assert r.status_code == 404

    async def test_update_episode(self, client):
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        r = await client.patch(f"/api/v1/projects/{pid}/episodes/{eid}", json={
            "title": "修改后标题", "continuity_notes": "主角服装要统一"
        })
        assert r.status_code == 200
        assert r.json()["title"] == "修改后标题"
        assert r.json()["continuity_notes"] == "主角服装要统一"

    async def test_create_episode_directly(self, client):
        proj = await create_project(client)
        pid = proj["_id"]
        r = await client.post(f"/api/v1/projects/{pid}/episodes", json={
            "number": 1, "title": "直接创建", "summary": "s", "word_count": 100, "estimated_duration": 60
        })
        assert r.status_code == 201
        assert r.json()["title"] == "直接创建"


class TestEpisodeSteps:
    async def test_initial_step_is_storyboard_script(self, client):
        pid, eps = await setup_project_with_episodes(client)
        ep = eps[0]
        assert ep["current_step"] == "storyboard_script"
        assert ep["status"] == "not_started"

    async def test_advance_step(self, client):
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        r = await client.post(f"/api/v1/projects/{pid}/episodes/{eid}/advance-step")
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == "storyboard_images"
        assert data["status"] == "in_progress"

    async def test_advance_step_full_pipeline(self, client):
        """Step through all 8 steps until done."""
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        expected_steps = [
            "storyboard_images", "image_review", "storyboard_videos",
            "video_review", "dubbing", "merge", "done",
        ]
        for expected in expected_steps:
            r = await client.post(f"/api/v1/projects/{pid}/episodes/{eid}/advance-step")
            assert r.status_code == 200
            assert r.json()["current_step"] == expected

        # At done, status should be completed
        final = (await client.get(f"/api/v1/projects/{pid}/episodes/{eid}")).json()
        assert final["status"] == "completed"

    async def test_set_step(self, client):
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        r = await client.post(f"/api/v1/projects/{pid}/episodes/{eid}/set-step", json={
            "step": "video_review"
        })
        assert r.status_code == 200
        assert r.json()["current_step"] == "video_review"

    async def test_set_invalid_step(self, client):
        pid, eps = await setup_project_with_episodes(client)
        eid = eps[0]["_id"]
        r = await client.post(f"/api/v1/projects/{pid}/episodes/{eid}/set-step", json={
            "step": "nonexistent_step"
        })
        assert r.status_code == 422
