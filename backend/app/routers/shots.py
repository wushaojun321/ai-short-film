from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from app.models.episode import Episode
from app.models.project import Project
from app.schemas.shot import ShotCreate, ShotUpdate, ShotReviewRequest, BatchReviewRequest
from app.services import shot_service
from app.deps import get_current_user, get_owned_project

router = APIRouter(
    prefix="/projects/{project_id}/episodes/{episode_id}/shots", tags=["shots"],
    dependencies=[Depends(get_current_user)]
)


async def _get_owned_episode(episode_id: PydanticObjectId, project: Project = Depends(get_owned_project)) -> Episode:
    episode = await Episode.get(episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(404, "Episode not found")
    return episode


@router.get("")
async def list_shots(episode: Episode = Depends(_get_owned_episode)):
    return await shot_service.list_shots(episode.id)


@router.post("", status_code=201)
async def create_shot(data: ShotCreate, episode: Episode = Depends(_get_owned_episode)):
    return await shot_service.create_shot(episode, data)


@router.get("/{shot_id}")
async def get_shot(shot_id: PydanticObjectId, episode: Episode = Depends(_get_owned_episode)):
    shot = await shot_service.get_shot(shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(404, "Shot not found")
    return shot


@router.patch("/{shot_id}")
async def update_shot(shot_id: PydanticObjectId, data: ShotUpdate, episode: Episode = Depends(_get_owned_episode)):
    shot = await shot_service.get_shot(shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(404, "Shot not found")
    return await shot_service.update_shot(shot, data)


@router.delete("/{shot_id}", status_code=204)
async def delete_shot(shot_id: PydanticObjectId, episode: Episode = Depends(_get_owned_episode)):
    shot = await shot_service.get_shot(shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(404, "Shot not found")
    await shot_service.delete_shot(shot)


@router.post("/{shot_id}/review")
async def review_shot(shot_id: PydanticObjectId, data: ShotReviewRequest, episode: Episode = Depends(_get_owned_episode)):
    shot = await shot_service.get_shot(shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(404, "Shot not found")
    return await shot_service.review_shot(shot, data.approved, data.comment)


@router.post("/{shot_id}/versions/{version}/restore")
async def restore_shot_version(shot_id: PydanticObjectId, version: str, episode: Episode = Depends(_get_owned_episode)):
    shot = await shot_service.get_shot(shot_id)
    if not shot or shot.episode_id != episode.id:
        raise HTTPException(404, "Shot not found")
    try:
        return await shot_service.restore_shot_version(shot, version)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/batch-review")
async def batch_review(data: BatchReviewRequest, episode: Episode = Depends(_get_owned_episode)):
    results = []
    for item in data.reviews:
        shot = await shot_service.get_shot(PydanticObjectId(item["shot_id"]))
        if shot and shot.episode_id == episode.id:
            updated = await shot_service.review_shot(
                shot, item.get("approved", False), item.get("comment")
            )
            results.append(updated)
    return results
