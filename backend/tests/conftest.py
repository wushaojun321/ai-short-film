"""
Test configuration and fixtures.

Uses a dedicated test database (ai_short_film_test) on the running MongoDB.
All external API calls (Seedream/Seedance/LLM/COS) are mocked — no money spent.
Each test function gets a clean DB via collection drop in teardown.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

pytest_plugins = ("pytest_asyncio",)

TEST_MONGO_URL = "mongodb://mongodb:27017/ai_short_film_test"


async def _init_test_db():
    """Initialize Beanie with test database."""
    from app.models import (
        Project, Episode, ScriptBlock, Shot, Asset,
        Conversation, PromptConfig, TaskRecord,
        User, InviteCode,
    )
    await init_beanie(
        connection_string=TEST_MONGO_URL,
        document_models=[
            Project, Episode, ScriptBlock, Shot, Asset,
            Conversation, PromptConfig, TaskRecord,
            User, InviteCode,
        ],
    )
    client = AsyncIOMotorClient(TEST_MONGO_URL)
    db = client["ai_short_film_test"]
    return client, db


async def _drop_test_collections(db):
    """Drop all collections to isolate tests."""
    names = await db.list_collection_names()
    for name in names:
        await db.drop_collection(name)


# ── App + client fixtures ─────────────────────────────────────
@pytest_asyncio.fixture(scope="function")
async def app():
    """FastAPI app pointed at test MongoDB, cleaned before each test."""
    from app.config import settings

    # Override MongoDB URL to test DB
    with patch.object(settings, "mongodb_url", TEST_MONGO_URL):
        client, db = await _init_test_db()
        await _drop_test_collections(db)

        # Patch init_db used in lifespan so it uses test DB
        async def mock_init_db():
            await _init_test_db()

        with patch("app.main.init_db", mock_init_db), \
             patch("app.database.init_db", mock_init_db):
            # Re-import to get fresh app with patched settings
            import importlib
            import app.main as main_mod
            importlib.reload(main_mod)
            fastapi_app = main_mod.app

            async with fastapi_app.router.lifespan_context(fastapi_app):
                yield fastapi_app

        await _drop_test_collections(db)
        client.close()


@pytest_asyncio.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── External call mocks ───────────────────────────────────────
@pytest.fixture(autouse=False)
def mock_cos():
    with patch("app.services.storage_service.upload_bytes",
               new=AsyncMock(return_value="https://cos.example.com/test.jpg")), \
         patch("app.services.storage_service.upload_file",
               new=AsyncMock(return_value="https://cos.example.com/test.mp4")), \
         patch("app.services.storage_service.upload_from_url",
               new=AsyncMock(return_value="https://cos.example.com/test.jpg")), \
         patch("app.services.storage_service.download_file",
               new=AsyncMock(return_value="/tmp/test.mp4")):
        yield


@pytest.fixture(autouse=False)
def mock_llm():
    with patch("app.services.llm_service.chat_json",
               new=AsyncMock(return_value={
                   "series_prompt": "古装宫廷剧",
                   "episodes": [{"number": 1, "title": "第一集", "summary": "故事开始", "word_count": 2000, "estimated_duration": 120}],
                   "assets": {"characters": [{"name": "主角", "description": "年轻女性"}], "scenes": [], "props": []},
                   "continuity_notes": "保持一致",
                   "shots": [
                       {"shot_code": "EP01-S01", "order": 1, "duration": 5, "description": "主角出场", "prompt": "主角站在宫门口"},
                       {"shot_code": "EP01-S02", "order": 2, "duration": 6, "description": "对话场景", "prompt": "两人对话"},
                   ],
               })), \
         patch("app.services.llm_service.chat_completion",
               new=AsyncMock(return_value="好的，已为您修改完毕。")), \
         patch("app.services.llm_service.chat_with_history",
               new=AsyncMock(return_value='{"prompt": "修改后的提示词", "note": "已调整风格"}')):
        yield


@pytest.fixture(autouse=False)
def mock_image():
    with patch("app.services.image_service.generate_image",
               new=AsyncMock(return_value="https://cos.example.com/image.jpg")):
        yield


@pytest.fixture(autouse=False)
def mock_video():
    with patch("app.services.video_service.generate_video_sync",
               return_value={
                   "video_url": "https://example.com/tmp_video.mp4",
                   "last_frame_url": "https://example.com/last_frame.jpg",
                   "task_id": "mock-task-id",
               }), \
         patch("app.services.video_service.upload_video_to_cos",
               new=AsyncMock(return_value="https://cos.example.com/video.mp4")), \
         patch("app.services.video_service.upload_last_frame_to_cos",
               new=AsyncMock(return_value="https://cos.example.com/last_frame.jpg")):
        yield


# ── Auth fixtures ─────────────────────────────────────────────
@pytest_asyncio.fixture(scope="function")
async def auth_headers(client):
    """Register a test user with an invite code and return auth headers."""
    from app.models.invite_code import InviteCode as InviteCodeModel
    code_doc = InviteCodeModel(code="TEST-INVITE-0001")
    await code_doc.insert()

    r = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "invite_code": "TEST-INVITE-0001",
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Helpers ───────────────────────────────────────────────────
async def create_project(client, title="测试项目", genre="都市", episodes=5, headers=None):
    r = await client.post("/api/v1/projects", json={
        "title": title, "genre": genre, "target_episode_count": episodes
    }, headers=headers or {})
    assert r.status_code == 201
    return r.json()


async def upload_script(client, project_id, headers=None):
    content = "这是测试剧本内容，共五集，讲述一个感人的故事。".encode("utf-8")
    r = await client.post(
        f"/api/v1/projects/{project_id}/upload-script",
        files={"file": ("test_script.txt", content, "text/plain")},
        headers=headers or {},
    )
    assert r.status_code == 200
    return r.json()
