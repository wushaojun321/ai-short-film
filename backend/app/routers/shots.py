from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from app.models.episode import Episode
from app.schemas.shot import ShotCreate, ShotUpdate, ShotReviewRequest, BatchReviewRequest
from app.services import shot_service

router = APIRouter(
    prefix="/projects/{project_id}/episodes/{episode_id}/shots", tags=["shots"]
)


async def _get_episode(episode_id: PydanticObjectId) -> Episode:
    episode = await Episode.get(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    return episode


@router.get("")
async def list_shots(project_id: PydanticObjectId, episode_id: PydanticObjectId):
    await _get_episode(episode_id)
    return await shot_service.list_shots(episode_id)


@router.post("", status_code=201)
async def create_shot(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, data: ShotCreate
):
    episode = await _get_episode(episode_id)
    return await shot_service.create_shot(episode, data)


@router.get("/{shot_id}")
async def get_shot(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, shot_id: PydanticObjectId
):
    shot = await shot_service.get_shot(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    return shot


@router.patch("/{shot_id}")
async def update_shot(
    project_id: PydanticObjectId,
    episode_id: PydanticObjectId,
    shot_id: PydanticObjectId,
    data: ShotUpdate,
):
    shot = await shot_service.get_shot(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    return await shot_service.update_shot(shot, data)


@router.delete("/{shot_id}", status_code=204)
async def delete_shot(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, shot_id: PydanticObjectId
):
    shot = await shot_service.get_shot(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    await shot_service.delete_shot(shot)


@router.post("/{shot_id}/review")
async def review_shot(
    project_id: PydanticObjectId,
    episode_id: PydanticObjectId,
    shot_id: PydanticObjectId,
    data: ShotReviewRequest,
):
    shot = await shot_service.get_shot(shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    return await shot_service.review_shot(shot, data.approved, data.comment)


@router.post("/batch-review")
async def batch_review(
    project_id: PydanticObjectId, episode_id: PydanticObjectId, data: BatchReviewRequest
):
    results = []
    for item in data.reviews:
        shot = await shot_service.get_shot(PydanticObjectId(item["shot_id"]))
        if shot:
            updated = await shot_service.review_shot(
                shot, item.get("approved", False), item.get("comment")
            )
            results.append(updated)
    return results
