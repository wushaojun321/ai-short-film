from beanie import PydanticObjectId
from app.models.episode import Episode, EpisodeStatus, EpisodeStep, STEP_ORDER
from app.models.project import Project
from app.schemas.episode import EpisodeCreate, EpisodeUpdate
from datetime import datetime


def _has_final_video(episode: Episode) -> bool:
    return bool((episode.final_video_url or "").strip())


async def create_episode(project: Project, data: EpisodeCreate) -> Episode:
    episode = Episode(project_id=project.id, **data.model_dump())
    await episode.insert()
    return episode


async def get_episode(episode_id: PydanticObjectId) -> Episode | None:
    return await Episode.get(episode_id)


async def list_episodes(project_id: PydanticObjectId) -> list[Episode]:
    return await Episode.find(Episode.project_id == project_id).sort("+number").to_list()


async def update_episode(episode: Episode, data: EpisodeUpdate) -> Episode:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await episode.set(update_data)
    return episode


async def advance_step(episode: Episode) -> Episode:
    current = episode.current_step
    if current is None:
        next_step = STEP_ORDER[0]
    elif current in (EpisodeStep.storyboard_images, EpisodeStep.image_review):
        # 旧流程中的图片生成/审核步骤已移除，历史分集继续推进到分镜视频。
        next_step = EpisodeStep.storyboard_videos
    else:
        idx = STEP_ORDER.index(current)
        if idx + 1 >= len(STEP_ORDER):
            # already at done
            if _has_final_video(episode):
                await episode.set({"status": EpisodeStatus.completed})
            else:
                await episode.set({
                    "current_step": EpisodeStep.merge,
                    "status": EpisodeStatus.in_progress,
                })
            return episode
        next_step = STEP_ORDER[idx + 1]

    updates: dict = {"current_step": next_step}
    if next_step == EpisodeStep.done:
        if _has_final_video(episode):
            updates["status"] = EpisodeStatus.completed
        else:
            updates["current_step"] = EpisodeStep.merge
            updates["status"] = EpisodeStatus.in_progress
    elif episode.status == EpisodeStatus.not_started:
        updates["status"] = EpisodeStatus.in_progress

    await episode.set(updates)
    return episode


async def set_step(episode: Episode, step: EpisodeStep) -> Episode:
    target_step = step
    updates: dict = {"current_step": target_step}
    if target_step == EpisodeStep.done:
        if _has_final_video(episode):
            updates["status"] = EpisodeStatus.completed
        else:
            updates["current_step"] = EpisodeStep.merge
            updates["status"] = EpisodeStatus.in_progress
    elif episode.status in (EpisodeStatus.not_started, EpisodeStatus.completed):
        updates["status"] = EpisodeStatus.in_progress
    await episode.set(updates)
    return episode


async def invalidate_final_video(
    episode_id: PydanticObjectId,
    *,
    target_step: EpisodeStep = EpisodeStep.storyboard_videos,
) -> Episode | None:
    """Mark an episode final video stale after its shots/storyboard changed."""
    episode = await Episode.get(episode_id)
    if not episode:
        return None

    updates: dict = {"status": EpisodeStatus.in_progress, "updated_at": datetime.utcnow()}
    if episode.final_video_url:
        updates["final_video_url"] = None

    current_idx = STEP_ORDER.index(episode.current_step) if episode.current_step in STEP_ORDER else -1
    target_idx = STEP_ORDER.index(target_step) if target_step in STEP_ORDER else current_idx
    if current_idx < 0 or current_idx > target_idx or episode.status == EpisodeStatus.completed:
        updates["current_step"] = target_step

    await episode.set(updates)
    return episode
