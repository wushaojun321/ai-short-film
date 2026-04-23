from beanie import PydanticObjectId
from app.models.shot import Shot, ShotState
from app.models.episode import Episode
from app.schemas.shot import ShotCreate, ShotUpdate


async def create_shot(episode: Episode, data: ShotCreate) -> Shot:
    shot = Shot(
        project_id=episode.project_id,
        episode_id=episode.id,
        **data.model_dump(),
    )
    await shot.insert()
    return shot


async def get_shot(shot_id: PydanticObjectId) -> Shot | None:
    return await Shot.get(shot_id)


async def list_shots(episode_id: PydanticObjectId) -> list[Shot]:
    return await Shot.find(Shot.episode_id == episode_id).sort("+order").to_list()


async def update_shot(shot: Shot, data: ShotUpdate) -> Shot:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await shot.set(update_data)
    return shot


async def review_shot(shot: Shot, approved: bool, comment: str | None = None) -> Shot:
    updates: dict = {}
    if approved:
        updates["state"] = ShotState.approved
    else:
        updates["state"] = ShotState.review_failed
        if comment:
            updates["review_comment"] = comment
    await shot.set(updates)
    return shot


async def delete_shot(shot: Shot) -> None:
    await shot.delete()
