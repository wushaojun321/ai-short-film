from beanie import PydanticObjectId
from app.models.episode import Episode, EpisodeStatus, EpisodeStep, STEP_ORDER
from app.models.project import Project
from app.schemas.episode import EpisodeCreate, EpisodeUpdate


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
    else:
        idx = STEP_ORDER.index(current)
        if idx + 1 >= len(STEP_ORDER):
            # already at done
            await episode.set({"status": EpisodeStatus.completed})
            return episode
        next_step = STEP_ORDER[idx + 1]

    updates: dict = {"current_step": next_step}
    if next_step == EpisodeStep.done:
        updates["status"] = EpisodeStatus.completed
    elif episode.status == EpisodeStatus.not_started:
        updates["status"] = EpisodeStatus.in_progress

    await episode.set(updates)
    return episode


async def set_step(episode: Episode, step: EpisodeStep) -> Episode:
    updates: dict = {"current_step": step}
    if episode.status == EpisodeStatus.not_started:
        updates["status"] = EpisodeStatus.in_progress
    await episode.set(updates)
    return episode
