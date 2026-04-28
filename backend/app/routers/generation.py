"""Generation trigger endpoints and SSE progress streaming."""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from beanie import PydanticObjectId
from app.models.project import Project
from app.models.episode import Episode
from app.models.shot import Shot
from app.models.asset import Asset
from app.models.task_record import TaskRecord, TaskStatus
from app.schemas.project import ParseScriptRequest

router = APIRouter(prefix="/generate", tags=["generation"])


# ── Script parsing ────────────────────────────────────────────

@router.post("/projects/{project_id}/parse-script")
async def enqueue_parse_script(project_id: PydanticObjectId, data: ParseScriptRequest):
    """Enqueue LLM script parsing task."""
    project = await Project.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.script_text:
        raise HTTPException(400, "Script not uploaded yet")

    # 把解析参数写入 Project，供 worker 读取
    await project.set({
        "target_episode_count": data.target_episodes,
        "min_episode_duration": data.min_duration,
        "parse_notes": data.parse_notes or "",
    })

    from app.tasks.llm_tasks import parse_script_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = parse_script_task.delay(str(project_id))

    record = TaskRecord(
        celery_task_id=task.id,
        task_type="parse_script",
        project_id=project.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── Shot script generation ────────────────────────────────────

@router.post("/episodes/{episode_id}/shot-script")
async def enqueue_shot_script(episode_id: PydanticObjectId, max_shot_duration: int = 5, feedback: str | None = None):
    """Enqueue shot script generation for an episode."""
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")

    from app.tasks.llm_tasks import gen_shot_script_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = gen_shot_script_task.delay(str(episode_id), max_shot_duration, feedback)
    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_shot_script",
        project_id=episode.project_id,
        episode_id=episode.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── Asset image generation ────────────────────────────────────

@router.post("/assets/{asset_id}/image")
async def enqueue_asset_image(asset_id: PydanticObjectId):
    """Enqueue image generation for an asset."""
    from app.models.asset import AssetStatus
    asset = await Asset.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")

    # 防止重复入队：已在队列或生成中时直接返回
    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        return {"task_id": None, "record_id": None, "skipped": True, "reason": "already queued or generating"}

    from app.tasks.image_tasks import gen_asset_image_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = gen_asset_image_task.delay(str(asset_id))

    # 入队后立即标记为 queued，worker 开始执行时自动改为 generating
    await asset.set({"status": AssetStatus.queued})

    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_asset_image",
        project_id=asset.project_id,
        target_id=asset.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── Shot image generation ─────────────────────────────────────

@router.post("/shots/{shot_id}/image")
async def enqueue_shot_image(shot_id: PydanticObjectId):
    """Enqueue storyboard image generation for a shot."""
    shot = await Shot.get(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")

    from app.tasks.image_tasks import gen_shot_image_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = gen_shot_image_task.delay(str(shot_id))
    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_shot_image",
        project_id=shot.project_id,
        episode_id=shot.episode_id,
        target_id=shot.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── Shot video generation ─────────────────────────────────────

@router.post("/shots/{shot_id}/video")
async def enqueue_shot_video(shot_id: PydanticObjectId):
    """Enqueue video generation for a shot."""
    shot = await Shot.get(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")

    from app.tasks.video_tasks import gen_shot_video_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = gen_shot_video_task.delay(str(shot_id))
    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_shot_video",
        project_id=shot.project_id,
        episode_id=shot.episode_id,
        target_id=shot.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── Episode merge ─────────────────────────────────────────────

@router.post("/episodes/{episode_id}/merge")
async def enqueue_merge(episode_id: PydanticObjectId):
    """Enqueue final video merge for an episode."""
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")

    from app.tasks.merge_tasks import merge_episode_task
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime

    task = merge_episode_task.delay(str(episode_id))
    record = TaskRecord(
        celery_task_id=task.id,
        task_type="merge_episode",
        project_id=episode.project_id,
        episode_id=episode.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"task_id": task.id, "record_id": str(record.id)}


# ── SSE progress stream ───────────────────────────────────────

@router.get("/tasks/{record_id}/progress")
async def task_progress_sse(record_id: PydanticObjectId):
    """SSE endpoint: streams task progress until completion."""

    async def event_stream():
        last_progress = -1
        max_polls = 600  # 10 minutes at 1s interval
        for _ in range(max_polls):
            record = await TaskRecord.get(record_id)
            if not record:
                yield f"data: {json.dumps({'error': 'task not found'})}\n\n"
                return

            if record.progress != last_progress:
                last_progress = record.progress
                payload = {
                    "status": record.status,
                    "progress": record.progress,
                }
                if record.result:
                    payload["result"] = record.result
                if record.error:
                    payload["error"] = record.error
                yield f"data: {json.dumps(payload)}\n\n"

            if record.status in (TaskStatus.success, TaskStatus.failed, TaskStatus.cancelled):
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
