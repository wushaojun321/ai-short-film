from fastapi import APIRouter, HTTPException, Query, Depends
from beanie import PydanticObjectId
from app.models.project import Project
from app.models.episode import EpisodeStep
from app.models.shot import Shot
from app.schemas.episode import EpisodeCreate, EpisodeUpdate, StepAdvanceRequest
from app.services import episode_service
from app.deps import get_current_user, get_owned_project

router = APIRouter(prefix="/projects/{project_id}/episodes", tags=["episodes"], dependencies=[Depends(get_current_user)])


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
        data["shots"] = [s.model_dump(by_alias=True, mode="json") for s in shots]
        data["running_tasks"] = [
            {"task_type": t.task_type, "status": t.status, "progress": t.progress or 0}
            for t in running_tasks
        ]
        return data
    return episode


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
