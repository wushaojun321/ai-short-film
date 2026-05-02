"""Tests for generation endpoints (all external calls mocked)."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tests.conftest import create_project, upload_script

pytestmark = pytest.mark.asyncio


async def setup_shot(client):
    """Create project → episode → shot, return (pid, eid, sid)."""
    proj = await create_project(client)
    pid = proj["_id"]
    await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={
        "episodes": [{"number": 1, "title": "EP1", "summary": "s", "word_count": 100, "estimated_duration": 60}]
    })
    eps = (await client.get(f"/api/v1/projects/{pid}/episodes")).json()
    eid = eps[0]["_id"]
    shot = (await client.post(
        f"/api/v1/projects/{pid}/episodes/{eid}/shots",
        json={"shot_code": "S01", "order": 1, "duration": 5, "description": "测试镜头", "prompt": "主角站立"}
    )).json()
    return pid, eid, shot["_id"]


async def setup_asset(client):
    proj = await create_project(client)
    pid = proj["_id"]
    asset = (await client.post(f"/api/v1/projects/{pid}/assets", json={
        "name": "主角", "asset_type": "character", "prompt": "年轻女性"
    })).json()
    return pid, asset["_id"]


class TestGenerationEndpoints:
    """Verify generation endpoints return task records (Celery tasks mocked)."""

    async def test_enqueue_parse_script(self, client, mock_cos):
        proj = await create_project(client)
        pid = proj["_id"]
        await upload_script(client, pid)

        with patch("app.tasks.llm_tasks.parse_script_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-parse")
            r = await client.post(f"/api/v1/generate/projects/{pid}/parse-script")
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data
        assert "record_id" in data

    async def test_enqueue_parse_script_no_script(self, client):
        proj = await create_project(client)
        r = await client.post(f"/api/v1/generate/projects/{proj['_id']}/parse-script")
        assert r.status_code == 400

    async def test_enqueue_shot_script(self, client):
        pid, eid, _ = await setup_shot(client)
        with patch("app.tasks.llm_tasks.gen_shot_script_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-script")
            r = await client.post(f"/api/v1/generate/episodes/{eid}/shot-script")
        assert r.status_code == 200
        assert "task_id" in r.json()

    async def test_enqueue_asset_image(self, client):
        pid, aid = await setup_asset(client)
        with patch("app.tasks.image_tasks.gen_asset_image_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-asset-img")
            r = await client.post(f"/api/v1/generate/assets/{aid}/image")
        assert r.status_code == 200
        assert "task_id" in r.json()

    async def test_enqueue_shot_image(self, client):
        pid, eid, sid = await setup_shot(client)
        with patch("app.tasks.image_tasks.gen_shot_image_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-shot-img")
            r = await client.post(f"/api/v1/generate/shots/{sid}/image")
        assert r.status_code == 200

    async def test_enqueue_shot_video(self, client):
        pid, eid, sid = await setup_shot(client)
        with patch("app.tasks.video_tasks.gen_shot_video_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-shot-video")
            r = await client.post(f"/api/v1/generate/shots/{sid}/video")
        assert r.status_code == 200

    async def test_enqueue_episode_shot_videos(self, client):
        pid, eid, _ = await setup_shot(client)
        with patch("app.tasks.video_tasks.gen_episode_videos_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-episode-videos")
            r = await client.post(f"/api/v1/generate/episodes/{eid}/shot-videos")
        assert r.status_code == 200
        assert "task_id" in r.json()

    async def test_enqueue_episode_merge(self, client):
        pid, eid, _ = await setup_shot(client)
        with patch("app.tasks.merge_tasks.merge_episode_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-celery-id-merge")
            r = await client.post(f"/api/v1/generate/episodes/{eid}/merge")
        assert r.status_code == 200

    async def test_enqueue_creates_task_record(self, client):
        """Enqueueing should create a TaskRecord in DB."""
        pid, aid = await setup_asset(client)
        with patch("app.tasks.image_tasks.gen_asset_image_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="test-record-check")
            r = await client.post(f"/api/v1/generate/assets/{aid}/image")
        record_id = r.json()["record_id"]

        # Verify task record was created
        r2 = await client.get(f"/api/v1/tasks/{record_id}")
        assert r2.status_code == 200
        assert r2.json()["task_type"] == "gen_asset_image"
        assert r2.json()["status"] == "running"


class TestTaskRecords:
    async def test_list_tasks(self, client):
        pid, aid = await setup_asset(client)
        # Enqueue a couple of tasks
        for _ in range(3):
            with patch("app.tasks.image_tasks.gen_asset_image_task") as mock_task:
                mock_task.delay.return_value = MagicMock(id=f"mock-{_}")
                await client.post(f"/api/v1/generate/assets/{aid}/image")

        r = await client.get("/api/v1/tasks")
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_list_tasks_by_project(self, client):
        pid, aid = await setup_asset(client)
        with patch("app.tasks.image_tasks.gen_asset_image_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-proj-filter")
            await client.post(f"/api/v1/generate/assets/{aid}/image")

        r = await client.get(f"/api/v1/tasks?project_id={pid}")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["task_type"] == "gen_asset_image"

    async def test_get_task_not_found(self, client):
        r = await client.get("/api/v1/tasks/000000000000000000000000")
        assert r.status_code == 404
