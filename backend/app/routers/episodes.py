from fastapi import APIRouter, HTTPException, Query, Depends
from beanie import PydanticObjectId
from app.models.project import Project
from app.models.episode import EpisodeStep
from app.models.shot import Shot
from app.schemas.episode import EpisodeCreate, EpisodeUpdate, StepAdvanceRequest
from app.services import episode_service
from app.services import storage_service
from app.deps import get_current_user, get_owned_project

router = APIRouter(prefix="/projects/{project_id}/episodes", tags=["episodes"], dependencies=[Depends(get_current_user)])


def _shot_summary(shot: Shot) -> dict:
    return {
        "_id": str(shot.id),
        "project_id": str(shot.project_id),
        "episode_id": str(shot.episode_id),
        "shot_code": shot.shot_code,
        "order": shot.order,
        "duration": shot.duration,
        "segment_code": shot.segment_code,
        "segment_name": shot.segment_name,
        "segment_function": shot.segment_function,
        "shot_function": shot.shot_function,
        "transition_in": shot.transition_in,
        "transition_out": shot.transition_out,
        "transition_type": shot.transition_type,
        "start_state": shot.start_state,
        "end_state": shot.end_state,
        "screen_direction": shot.screen_direction,
        "continuity_notes": shot.continuity_notes,
        "use_prev_last_frame": shot.use_prev_last_frame,
        "depends_on_last_frame_shot_id": str(shot.depends_on_last_frame_shot_id) if shot.depends_on_last_frame_shot_id else None,
        "continuity_dirty": shot.continuity_dirty,
        "continuity_dirty_reason": shot.continuity_dirty_reason,
        "description": shot.description,
        "dialogues": [line.model_dump(mode="json") for line in shot.dialogues],
        "required_assets": [item.model_dump(mode="json") for item in shot.required_assets],
        "state": shot.state,
        "version": shot.version,
        "image_url": shot.image_url,
        "video_url": shot.video_url,
        "audio_url": shot.audio_url,
        "last_frame_url": shot.last_frame_url,
        "versions": [],
        "version_count": len(shot.versions or []),
        "review_comment": shot.review_comment,
        "generation_task_id": shot.generation_task_id,
        "created_at": shot.created_at,
        "updated_at": shot.updated_at,
    }


@router.get("")
async def list_episodes(project: Project = Depends(get_owned_project)):
    return await episode_service.list_episodes(project.id)


@router.post("", status_code=201)
async def create_episode(data: EpisodeCreate, project: Project = Depends(get_owned_project)):
    return await episode_service.create_episode(project, data)


@router.get("/{episode_id}")
async def get_episode(
    episode_id: PydanticObjectId,
    include_shots: bool = Query(False),
    shots_view: str = Query("full", pattern="^(full|summary)$"),
    project: Project = Depends(get_owned_project),
):
    episode = await episode_service.get_episode(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    if include_shots:
        from app.models.task_record import TaskRecord
        shots = await Shot.find(Shot.episode_id == episode.id).sort("+order").to_list()
        running_tasks = await TaskRecord.find(
            TaskRecord.episode_id == episode.id,
            {"status": {"$in": ["pending", "running"]}},
        ).to_list()
        data = episode.model_dump(by_alias=True, mode="json")
        data["shots"] = [
            _shot_summary(s) if shots_view == "summary" else s.model_dump(by_alias=True, mode="json")
            for s in shots
        ]
        data["running_tasks"] = [
            {"task_type": t.task_type, "status": t.status, "progress": t.progress or 0}
            for t in running_tasks
        ]
        return data
    return episode


@router.get("/{episode_id}/final-video/download-url")
async def get_final_video_download_url(
    episode_id: PydanticObjectId,
    project: Project = Depends(get_owned_project),
):
    episode = await episode_service.get_episode(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    if not episode.final_video_url:
        raise HTTPException(400, "当前分集还没有合成视频")

    safe_title = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in episode.title).strip()
    filename = f"第{episode.number}集_{safe_title or '成片'}.mp4"
    return {
        "url": storage_service.get_presigned_download_url(
            episode.final_video_url,
            filename=filename,
        ),
        "filename": filename,
        "expires_in": 600,
    }


@router.patch("/{episode_id}")
async def update_episode(
    episode_id: PydanticObjectId,
    data: EpisodeUpdate,
    project: Project = Depends(get_owned_project),
):
    episode = await episode_service.get_episode(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    return await episode_service.update_episode(episode, data)


@router.post("/{episode_id}/advance-step")
async def advance_step(
    episode_id: PydanticObjectId,
    project: Project = Depends(get_owned_project),
):
    episode = await episode_service.get_episode(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    return await episode_service.advance_step(episode)


@router.post("/{episode_id}/set-step")
async def set_step(
    episode_id: PydanticObjectId,
    data: StepAdvanceRequest,
    project: Project = Depends(get_owned_project),
):
    episode = await episode_service.get_episode(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    return await episode_service.set_step(episode, EpisodeStep(data.step))
