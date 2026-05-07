"""Project-level task cleanup helpers.

The parser rewrites episodes/assets/shots for a project. Any generation task
still running against the old records must be stopped first, otherwise the UI can
show successful task records whose target asset/shot has already been replaced.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from beanie import PydanticObjectId

from app.models.asset import Asset, AssetStatus
from app.models.shot import Shot, ShotState
from app.models.task_record import TaskRecord, TaskStatus


GENERATION_TASK_TYPES = {
    "gen_asset_image",
    "gen_shot_image",
    "gen_shot_script",
    "gen_shot_video",
    "gen_episode_videos",
    "merge_episode",
}


async def get_active_parse_record(
    project_id: PydanticObjectId,
    *,
    exclude_celery_task_id: str | None = None,
) -> TaskRecord | None:
    records = await TaskRecord.find(
        TaskRecord.project_id == project_id,
        TaskRecord.task_type == "parse_script",
        {"status": {"$in": [TaskStatus.pending.value, TaskStatus.running.value]}},
    ).sort("-created_at").to_list()
    for record in records:
        if exclude_celery_task_id and record.celery_task_id == exclude_celery_task_id:
            continue
        return record
    return None


async def cancel_project_generation_tasks(
    project_id: PydanticObjectId,
    *,
    reason: str,
    exclude_celery_task_ids: Iterable[str] = (),
    terminate_workers: bool = False,
) -> dict:
    excluded = {task_id for task_id in exclude_celery_task_ids if task_id}
    records = await TaskRecord.find(
        TaskRecord.project_id == project_id,
        {"task_type": {"$in": sorted(GENERATION_TASK_TYPES)}},
        {"status": {"$in": [TaskStatus.pending.value, TaskStatus.running.value]}},
    ).to_list()
    records = [record for record in records if record.celery_task_id not in excluded]
    celery_ids = [record.celery_task_id for record in records if record.celery_task_id]

    revoke_error = ""
    if terminate_workers and celery_ids:
        try:
            from app.celery_app import celery_app

            celery_app.control.revoke(celery_ids, terminate=True, signal="SIGTERM")
        except Exception as exc:  # pragma: no cover - broker connectivity is environment-specific.
            revoke_error = str(exc) or exc.__class__.__name__

    now = datetime.utcnow()
    for record in records:
        logs = list(record.logs or [])
        logs.append(f"[cancel] {reason}")
        await record.set({
            "status": TaskStatus.cancelled,
            "progress": 0,
            "error": reason,
            "finished_at": now,
            "logs": logs,
        })

    updated_assets = 0
    assets = await Asset.find(
        Asset.project_id == project_id,
        {"status": {"$in": [AssetStatus.queued.value, AssetStatus.generating.value]}},
    ).to_list()
    for asset in assets:
        next_status = (
            AssetStatus.pending
            if asset.preview_url or asset.view_urls
            else AssetStatus.need_regen
        )
        await asset.set({
            "status": next_status,
            "generation_task_id": None,
            "updated_at": now,
        })
        updated_assets += 1

    updated_shots = 0
    shots = await Shot.find(
        Shot.project_id == project_id,
        {"state": {"$in": [ShotState.generating.value, ShotState.rendering.value]}},
    ).to_list()
    for shot in shots:
        if shot.video_url:
            updates = {
                "state": ShotState.rendered,
                "generation_task_id": None,
                "updated_at": now,
            }
        elif shot.state == ShotState.rendering:
            updates = {
                "state": ShotState.review_failed,
                "generation_task_id": None,
                "review_comment": reason,
                "continuity_dirty": True,
                "continuity_dirty_reason": "生成任务被取消，需要重新生成本镜头。",
                "updated_at": now,
            }
        else:
            updates = {
                "state": ShotState.planned,
                "generation_task_id": None,
                "review_comment": reason,
                "updated_at": now,
            }
        await shot.set(updates)
        updated_shots += 1

    return {
        "cancelled_tasks": len(records),
        "revoked_celery_tasks": len(celery_ids),
        "updated_assets": updated_assets,
        "updated_shots": updated_shots,
        "revoke_error": revoke_error,
    }

