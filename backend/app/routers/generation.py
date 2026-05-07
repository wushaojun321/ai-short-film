"""Generation trigger endpoints and SSE progress streaming."""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from beanie import PydanticObjectId
from app.models.project import Project
from app.models.episode import Episode
from app.models.shot import Shot, ShotState
from app.models.asset import Asset
from app.models.task_record import TaskRecord, TaskStatus
from app.schemas.project import ParseScriptRequest
from app.deps import get_current_user, get_owned_project
from app.services.project_task_cleanup import (
    cancel_project_generation_tasks,
    get_active_parse_record,
)

router = APIRouter(prefix="/generate", tags=["generation"], dependencies=[Depends(get_current_user)])


async def _ensure_project_not_parsing(project_id: PydanticObjectId):
    active_parse = await get_active_parse_record(project_id)
    if active_parse:
        raise HTTPException(409, "项目正在解析剧本，请等待解析完成后再开始生成任务")


# ── Script parsing ────────────────────────────────────────────

@router.post("/projects/{project_id}/parse-script")
async def enqueue_parse_script(
    data: ParseScriptRequest,
    project: Project = Depends(get_owned_project),
):
    if not project.script_text:
        raise HTTPException(400, "Script not uploaded yet")

    active_parse = await get_active_parse_record(project.id)
    if active_parse:
        return {
            "task_id": active_parse.celery_task_id,
            "record_id": str(active_parse.id),
            "skipped": True,
            "reason": "parse already running",
        }

    await cancel_project_generation_tasks(
        project.id,
        reason="用户重新提交剧本解析，已停止旧生成任务",
        terminate_workers=True,
    )

    await project.set({
        "target_episode_count": data.target_episodes,
        "min_episode_duration": data.min_duration,
        "parse_notes": data.parse_notes or "",
    })

    from app.tasks.llm_tasks import parse_script_task
    from datetime import datetime

    task = parse_script_task.delay(str(project.id))
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
async def enqueue_shot_script(
    episode_id: PydanticObjectId,
    max_shot_duration: int = 8,
    feedback: str | None = None,
    current_user=Depends(get_current_user),
):
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    # 验证 episode 所属项目归属当前用户
    project = await Project.get(episode.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Episode not found")
    await _ensure_project_not_parsing(project.id)

    from app.tasks.llm_tasks import gen_shot_script_task
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
async def enqueue_asset_image(asset_id: PydanticObjectId, current_user=Depends(get_current_user)):
    from app.models.asset import AssetStatus
    asset = await Asset.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    project = await Project.get(asset.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Asset not found")
    await _ensure_project_not_parsing(project.id)

    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        return {"task_id": None, "record_id": None, "skipped": True, "reason": "already queued or generating"}

    from app.services import asset_service
    from app.tasks.image_tasks import gen_asset_image_task
    from datetime import datetime

    asset = await asset_service.refresh_asset_submitted_prompts(asset, force=True)
    task = gen_asset_image_task.delay(str(asset_id))
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
async def enqueue_shot_image(shot_id: PydanticObjectId, current_user=Depends(get_current_user)):
    shot = await Shot.get(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    project = await Project.get(shot.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Shot not found")
    await _ensure_project_not_parsing(project.id)

    from app.tasks.image_tasks import gen_shot_image_task
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
async def enqueue_shot_video(shot_id: PydanticObjectId, current_user=Depends(get_current_user)):
    shot = await Shot.get(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    project = await Project.get(shot.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Shot not found")
    await _ensure_project_not_parsing(project.id)

    from app.tasks.video_tasks import gen_shot_video_task
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


@router.post("/episodes/{episode_id}/shot-videos")
async def enqueue_episode_shot_videos(episode_id: PydanticObjectId, current_user=Depends(get_current_user)):
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    project = await Project.get(episode.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Episode not found")
    await _ensure_project_not_parsing(project.id)

    from app.models.shot import ShotState
    from app.tasks.video_tasks import gen_shot_video_chain_task
    from datetime import datetime

    shots = await Shot.find(Shot.episode_id == episode.id).sort("+order").to_list()
    records: list[dict] = []
    queued = 0
    queued_chains = 0
    skipped = 0
    active_target_ids: set[str] = set()
    active_celery_ids: set[str] = set()

    active_records = await TaskRecord.find(
        TaskRecord.episode_id == episode.id,
        TaskRecord.task_type == "gen_shot_video",
        {"status": {"$in": ["pending", "running"]}},
    ).to_list()
    for active in active_records:
        active_celery_ids.add(active.celery_task_id)
        if active.target_id:
            active_target_ids.add(str(active.target_id))

    # Segment boundaries are the concurrency boundaries: segments run in parallel,
    # while shots inside one segment run sequentially to preserve last-frame continuity.
    segments: list[tuple[str, list[Shot]]] = []
    for shot in shots:
        segment_key = shot.segment_code or "__episode__"
        if not segments or segments[-1][0] != segment_key:
            segments.append((segment_key, []))
        segments[-1][1].append(shot)

    for segment_key, segment_shots in segments:
        chain: list[Shot] = []
        blocked_by_active_previous = False

        for shot in segment_shots:
            if shot.video_url:
                continue

            shot_has_active_record = (
                str(shot.id) in active_target_ids
                or (shot.generation_task_id in active_celery_ids if shot.generation_task_id else False)
            )
            shot_is_active = shot_has_active_record or (
                shot.state == ShotState.rendering
                and shot.generation_task_id in active_celery_ids
            )
            if shot_is_active:
                records.append({
                    "task_id": shot.generation_task_id,
                    "record_id": None,
                    "shot_id": str(shot.id),
                    "shot_code": shot.shot_code,
                    "segment_code": shot.segment_code,
                    "queued": False,
                    "reason": "already running",
                })
                blocked_by_active_previous = True
                skipped += 1
                continue

            if blocked_by_active_previous:
                records.append({
                    "task_id": None,
                    "record_id": None,
                    "shot_id": str(shot.id),
                    "shot_code": shot.shot_code,
                    "segment_code": shot.segment_code,
                    "queued": False,
                    "reason": "waiting for previous shot in segment",
                })
                skipped += 1
                continue

            chain.append(shot)

        if not chain:
            skipped += 1
            continue

        segment_label = chain[0].segment_code or f"EP{episode.number:02d}"
        task = gen_shot_video_chain_task.delay([str(shot.id) for shot in chain], segment_label)
        for shot in chain:
            await shot.set({
                "state": ShotState.rendering,
                "generation_task_id": task.id,
            })
        record = TaskRecord(
            celery_task_id=task.id,
            task_type="gen_shot_video",
            project_id=episode.project_id,
            episode_id=episode.id,
            target_id=chain[0].id,
            status=TaskStatus.running,
            progress=0,
            logs=[
                (
                    f"[video-chain] 已加入片段链队列：{segment_label}，"
                    f"{len(chain)} 个镜头将按顺序生成并传递上一镜尾帧"
                )
            ],
            started_at=datetime.utcnow(),
        )
        await record.insert()
        records.append({
            "task_id": task.id,
            "record_id": str(record.id),
            "shot_id": str(chain[0].id),
            "shot_ids": [str(shot.id) for shot in chain],
            "shot_code": chain[0].shot_code,
            "shot_codes": [shot.shot_code for shot in chain],
            "segment_code": chain[0].segment_code,
            "queued": True,
            "chain": True,
        })
        queued += len(chain)
        queued_chains += 1

    first_record = next((item for item in records if item.get("record_id")), None)
    return {
        "task_id": first_record["task_id"] if first_record else None,
        "record_id": first_record["record_id"] if first_record else None,
        "records": records,
        "queued": queued,
        "queued_chains": queued_chains,
        "skipped": skipped,
    }


# ── Episode merge ─────────────────────────────────────────────

@router.post("/episodes/{episode_id}/merge")
async def enqueue_merge(episode_id: PydanticObjectId, current_user=Depends(get_current_user)):
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    project = await Project.get(episode.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(404, "Episode not found")
    await _ensure_project_not_parsing(project.id)

    shots = await Shot.find(Shot.episode_id == episode.id).sort("+order").to_list()
    if not shots:
        raise HTTPException(400, "当前分集还没有分镜，无法合并")
    missing_videos = [shot.shot_code for shot in shots if not shot.video_url]
    unapproved = [shot.shot_code for shot in shots if shot.state != ShotState.approved]
    if missing_videos:
        preview = "、".join(missing_videos[:5])
        more = f" 等 {len(missing_videos)} 个" if len(missing_videos) > 5 else ""
        raise HTTPException(400, f"还有镜头未生成视频：{preview}{more}")
    if unapproved:
        preview = "、".join(unapproved[:5])
        more = f" 等 {len(unapproved)} 个" if len(unapproved) > 5 else ""
        raise HTTPException(400, f"还有镜头未审批通过：{preview}{more}")

    from app.tasks.merge_tasks import merge_episode_task
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
async def task_progress_sse(record_id: PydanticObjectId, current_user=Depends(get_current_user)):
    """SSE endpoint: streams task progress until completion."""

    async def event_stream():
        last_progress = -1
        max_polls = 600
        for _ in range(max_polls):
            record = await TaskRecord.get(record_id)
            if not record:
                yield f"data: {json.dumps({'error': 'task not found'})}\n\n"
                return
            # 验证任务归属
            project = await Project.get(record.project_id)
            if not project or project.owner_id != current_user.id:
                yield f"data: {json.dumps({'error': 'task not found'})}\n\n"
                return

            if record.progress != last_progress:
                last_progress = record.progress
                payload = {"status": record.status, "progress": record.progress}
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
