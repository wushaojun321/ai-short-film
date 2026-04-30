"""Tests for project CRUD and initialization flow."""
import pytest
from io import BytesIO
from zipfile import ZipFile
from tests.conftest import create_project, upload_script

pytestmark = pytest.mark.asyncio


class TestProjectCRUD:
    async def test_create_project(self, client):
        r = await client.post("/api/v1/projects", json={
            "title": "宫廷秘史", "genre": "古装", "target_episode_count": 10,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "宫廷秘史"
        assert data["init_status"] == "not_started"
        assert data["_id"] is not None

    async def test_list_projects_empty(self, client):
        r = await client.get("/api/v1/projects")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_projects(self, client):
        await create_project(client, "项目A")
        await create_project(client, "项目B")
        r = await client.get("/api/v1/projects")
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_get_project(self, client):
        proj = await create_project(client)
        r = await client.get(f"/api/v1/projects/{proj['_id']}")
        assert r.status_code == 200
        assert r.json()["title"] == "测试项目"

    async def test_get_project_not_found(self, client):
        r = await client.get("/api/v1/projects/000000000000000000000000")
        assert r.status_code == 404

    async def test_update_project(self, client):
        proj = await create_project(client, "旧标题")
        r = await client.patch(f"/api/v1/projects/{proj['_id']}", json={
            "title": "新标题", "genre": "都市言情"
        })
        assert r.status_code == 200
        assert r.json()["title"] == "新标题"
        assert r.json()["genre"] == "都市言情"

    async def test_delete_project(self, client):
        proj = await create_project(client)
        pid = proj["_id"]
        r = await client.delete(f"/api/v1/projects/{pid}")
        assert r.status_code == 204
        r2 = await client.get(f"/api/v1/projects/{pid}")
        assert r2.status_code == 404

    async def test_delete_cascades_episodes(self, client):
        proj = await create_project(client)
        pid = proj["_id"]
        # Create an episode
        await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={
            "episodes": [{"number": 1, "title": "第一集", "summary": "s", "word_count": 100, "estimated_duration": 60}]
        })
        # Delete project
        await client.delete(f"/api/v1/projects/{pid}")
        # Episodes should be gone
        r = await client.get(f"/api/v1/projects/{pid}/episodes")
        assert r.status_code == 404


class TestProjectInitFlow:
    async def test_upload_script(self, client, mock_cos):
        proj = await create_project(client)
        data = await upload_script(client, proj["_id"])
        assert "script_file_url" in data
        assert data["init_status"] == "script_uploaded"

    async def test_upload_script_stores_text(self, client, mock_cos):
        proj = await create_project(client)
        content = "这是剧本正文内容。".encode("utf-8")
        r = await client.post(
            f"/api/v1/projects/{proj['_id']}/upload-script",
            files={"file": ("script.txt", content, "text/plain")},
        )
        assert r.status_code == 200
        # Verify project now has script text
        proj_r = await client.get(f"/api/v1/projects/{proj['_id']}")
        assert proj_r.json()["script_text"] == content.decode()

    async def test_upload_script_decodes_gbk_text(self, client, mock_cos):
        proj = await create_project(client)
        text = "这是 GBK 编码剧本。"
        r = await client.post(
            f"/api/v1/projects/{proj['_id']}/upload-script",
            files={"file": ("script.txt", text.encode("gbk"), "text/plain")},
        )
        assert r.status_code == 200
        assert r.json()["script_text_length"] == len(text)

        proj_r = await client.get(f"/api/v1/projects/{proj['_id']}")
        assert proj_r.json()["script_text"] == text

    async def test_upload_script_extracts_docx_text(self, client, mock_cos):
        proj = await create_project(client)
        docx = BytesIO()
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>第一场：雨夜。</w:t></w:r></w:p>
    <w:p><w:r><w:t>主角推门而入。</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        with ZipFile(docx, "w") as zf:
            zf.writestr("word/document.xml", document_xml)

        r = await client.post(
            f"/api/v1/projects/{proj['_id']}/upload-script",
            files={
                "file": (
                    "script.docx",
                    docx.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert r.status_code == 200

        proj_r = await client.get(f"/api/v1/projects/{proj['_id']}")
        assert proj_r.json()["script_text"] == "第一场：雨夜。\n主角推门而入。"

    async def test_upload_script_rejects_empty_text(self, client, mock_cos):
        proj = await create_project(client)
        r = await client.post(
            f"/api/v1/projects/{proj['_id']}/upload-script",
            files={"file": ("empty.txt", b"   \n\t", "text/plain")},
        )
        assert r.status_code == 400
        assert "未能从文件中提取到剧本文本" in r.json()["detail"]

    async def test_parse_script_requires_uploaded(self, client):
        proj = await create_project(client)
        r = await client.post(f"/api/v1/projects/{proj['_id']}/parse-script", json={
            "target_episodes": 5, "min_duration": 120, "parse_notes": ""
        })
        assert r.status_code == 400

    async def test_parse_script_stub(self, client, mock_cos):
        proj = await create_project(client)
        await upload_script(client, proj["_id"])
        r = await client.post(f"/api/v1/projects/{proj['_id']}/parse-script", json={
            "target_episodes": 5, "min_duration": 120, "parse_notes": "无特殊要求"
        })
        assert r.status_code == 200
        assert "task_id" in r.json()

    async def test_confirm_episodes(self, client):
        proj = await create_project(client)
        r = await client.post(f"/api/v1/projects/{proj['_id']}/confirm-episodes", json={
            "episodes": [
                {"number": 1, "title": "第一集", "summary": "开始", "word_count": 2000, "estimated_duration": 120},
                {"number": 2, "title": "第二集", "summary": "发展", "word_count": 2100, "estimated_duration": 125},
            ]
        })
        assert r.status_code == 200
        assert r.json()["init_status"] == "episodes_confirmed"
        # Episodes should exist
        eps = await client.get(f"/api/v1/projects/{proj['_id']}/episodes")
        assert len(eps.json()) == 2

    async def test_confirm_assets_requires_episodes_confirmed(self, client):
        proj = await create_project(client)
        r = await client.post(f"/api/v1/projects/{proj['_id']}/confirm-assets")
        assert r.status_code == 400

    async def test_confirm_assets(self, client):
        proj = await create_project(client)
        # Confirm episodes first
        await client.post(f"/api/v1/projects/{proj['_id']}/confirm-episodes", json={
            "episodes": [{"number": 1, "title": "第一集", "summary": "s", "word_count": 100, "estimated_duration": 60}]
        })
        r = await client.post(f"/api/v1/projects/{proj['_id']}/confirm-assets")
        assert r.status_code == 200
        assert r.json()["init_status"] == "initialized"

    async def test_full_init_flow(self, client, mock_cos):
        """Full initialization: create → upload → confirm episodes → confirm assets → initialized."""
        proj = await create_project(client, "完整流程项目")
        pid = proj["_id"]

        # Upload script
        await upload_script(client, pid)
        proj_data = await client.get(f"/api/v1/projects/{pid}")
        assert proj_data.json()["init_status"] == "script_uploaded"

        # Confirm episodes
        await client.post(f"/api/v1/projects/{pid}/confirm-episodes", json={
            "episodes": [{"number": 1, "title": "EP01", "summary": "s", "word_count": 100, "estimated_duration": 60}]
        })
        assert (await client.get(f"/api/v1/projects/{pid}")).json()["init_status"] == "episodes_confirmed"

        # Confirm assets → initialized
        await client.post(f"/api/v1/projects/{pid}/confirm-assets")
        final = await client.get(f"/api/v1/projects/{pid}")
        assert final.json()["init_status"] == "initialized"
