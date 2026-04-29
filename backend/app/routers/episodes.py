from fastapi import APIRouter, HTTPException, Query
from beanie import PydanticObjectId
from app.models.project import Project
from app.models.episode import EpisodeStep
from app.models.shot import Shot
from app.schemas.episode import EpisodeCreate, EpisodeUpdate, StepAdvanceRequest
from app.services import episode_service

router = APIRouter(prefix="/projects/{project_id}/episodes", tags=["episodes"])


async def _get_project(project_id: PydanticObjectId) -> Project:
    project = await Project.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("")
async def list_episodes(project_id: PydanticObjectId):
    await _get_project(project_id)
    return await episode_service.list_episodes(project_id)


@router.post("", status_code=201)
async def create_episode(project_id: PydanticObjectId, data: EpisodeCreate):
    project = await _get_project(project_id)
    return await episode_service.create_episode(project, data)


@router.get("/{episode_id}")
async def get_episode(
    project_id: PydanticObjectId,
    episode_id: PydanticObjectId,
    include_shots: bool = Query(False),
):
    await _get_project(project_id)
    episode = await episode_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    if include_shots:
        shots = await Shot.find(Shot.episode_id == episode.id).sort("+order").to_list()
        data = episode.model_dump(by_alias=True)
        data["shots"] = [s.model_dump(by_alias=True) for s in shots]
        return data
    return episode


@router.patch("/{episode_id}")
async def update_episode(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, data: EpisodeUpdate
):
    await _get_project(project_id)
    episode = await episode_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    return await episode_service.update_episode(episode, data)


@router.post("/{episode_id}/advance-step")
async def advance_step(project_id: PydanticObjectId, episode_id: PydanticObjectId):
    """Advance episode to next step in pipeline."""
    await _get_project(project_id)
    episode = await episode_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    return await episode_service.advance_step(episode)


@router.post("/{episode_id}/set-step")
async def set_step(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, data: StepAdvanceRequest
):
    """Jump to a specific step."""
    await _get_project(project_id)
    episode = await episode_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    return await episode_service.set_step(episode, EpisodeStep(data.step))
