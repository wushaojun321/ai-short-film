from beanie import PydanticObjectId
from app.models.shot import Shot, ShotState
from app.models.episode import Episode, EpisodeStep
from app.services.episode_service import invalidate_final_video
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
        await invalidate_final_video(shot.episode_id, target_step=EpisodeStep.storyboard_videos)
    await shot.set(updates)
    return shot


async def restore_shot_version(shot: Shot, version: str) -> Shot:
    selected = next((item for item in shot.versions if item.version == version), None)
    if not selected:
        raise ValueError("Shot version not found")

    await invalidate_final_video(shot.episode_id, target_step=EpisodeStep.storyboard_videos)
    await shot.set({
        "video_url": selected.video_url,
        "last_frame_url": selected.last_frame_url,
        "prompt": selected.prompt or shot.prompt,
        "submitted_prompt": selected.prompt or shot.submitted_prompt,
        "description": selected.description or shot.description,
        "version": selected.version,
        "state": ShotState.rendered,
        "continuity_dirty": False,
        "continuity_dirty_reason": "",
    })
    dependent_shots = await Shot.find(Shot.depends_on_last_frame_shot_id == shot.id).to_list()
    for dependent in dependent_shots:
        if dependent.video_url:
            await dependent.set({
                "continuity_dirty": True,
                "continuity_dirty_reason": f"依赖镜头 {shot.shot_code} 已回选历史版本，上一镜尾帧发生变化，建议刷新本镜视频。",
            })
    return shot


async def delete_shot(shot: Shot) -> None:
    await shot.delete()
