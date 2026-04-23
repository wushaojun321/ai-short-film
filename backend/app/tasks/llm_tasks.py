"""LLM Celery tasks: script parsing, shot script generation."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.llm.parse_script", queue="llm")
def parse_script_task(self, project_id: str):
    """Parse script and generate episode plan + asset list."""
    return run_async(_parse_script_async(self.request.id, project_id))


async def _parse_script_async(celery_id: str, project_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.project import Project, ProjectInitStatus
    from app.models.episode import Episode, EpisodeStatus
    from app.models.asset import Asset, AssetType, AssetStatus
    from app.models.task_record import TaskRecord
    from app.services import llm_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope

    try:
        project = await Project.get(PydanticObjectId(project_id))
        if not project or not project.script_text:
            raise ValueError("Project or script not found")

        # Update task record progress
        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 10})

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.script_parse,
            {
                "script_text": project.script_text[:8000],  # truncate for token limits
                "target_episodes": project.target_episode_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
            },
        )

        if record:
            await record.set({"progress": 30})

        result = await llm_service.chat_json(system_prompt, user_prompt)

        if record:
            await record.set({"progress": 70})

        # Save series_prompt
        if "series_prompt" in result:
            await project.set({"series_prompt": result["series_prompt"]})

        # Create episodes
        episodes_data = result.get("episodes", [])
        for ep_data in episodes_data:
            existing = await Episode.find_one(
                Episode.project_id == project.id,
                Episode.number == ep_data.get("number", 0),
            )
            if not existing:
                ep = Episode(
                    project_id=project.id,
                    number=ep_data.get("number", 0),
                    title=ep_data.get("title", ""),
                    summary=ep_data.get("summary", ""),
                    word_count=ep_data.get("word_count", 0),
                    estimated_duration=ep_data.get("estimated_duration", 0),
                    status=EpisodeStatus.not_started,
                )
                await ep.insert()

        # Create assets
        assets_data = result.get("assets", {})
        type_map = {
            "characters": AssetType.character,
            "scenes": AssetType.scene,
            "props": AssetType.prop,
        }
        for key, asset_type in type_map.items():
            for a in assets_data.get(key, []):
                existing_asset = await Asset.find_one(
                    Asset.project_id == project.id,
                    Asset.name == a.get("name", ""),
                )
                if not existing_asset:
                    asset = Asset(
                        project_id=project.id,
                        name=a.get("name", ""),
                        asset_type=asset_type,
                        prompt=a.get("description", ""),
                        status=AssetStatus.pending,
                    )
                    await asset.insert()

        await project.set({"init_status": ProjectInitStatus.episodes_confirmed})

        if record:
            await record.set({"progress": 100})

        await finish_task_record(celery_id, result={"episodes": len(episodes_data)})
        return result

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise


@celery_app.task(bind=True, name="app.tasks.llm.gen_shot_script", queue="llm")
def gen_shot_script_task(self, episode_id: str):
    """Generate storyboard script for an episode."""
    return run_async(_gen_shot_script_async(self.request.id, episode_id))


async def _gen_shot_script_async(celery_id: str, episode_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.episode import Episode, EpisodeStep
    from app.models.project import Project
    from app.models.shot import Shot, ShotState
    from app.models.asset import Asset
    from app.models.task_record import TaskRecord
    from app.services import llm_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope

    try:
        episode = await Episode.get(PydanticObjectId(episode_id))
        if not episode:
            raise ValueError("Episode not found")

        project = await Project.get(episode.project_id)
        assets = await Asset.find(Asset.project_id == episode.project_id).to_list()
        asset_list = [{"name": a.name, "type": a.asset_type, "preview_url": a.preview_url} for a in assets]

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 10})

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_script_gen,
            {
                "series_prompt": project.series_prompt or "",
                "episode_number": episode.number,
                "episode_title": episode.title,
                "episode_summary": episode.summary,
                "asset_list": str(asset_list),
                "continuity_notes": episode.continuity_notes or "",
            },
        )

        if record:
            await record.set({"progress": 30})

        result = await llm_service.chat_json(system_prompt, user_prompt)

        if record:
            await record.set({"progress": 70})

        # Create shots
        shots_data = result.get("shots", [])
        for idx, s in enumerate(shots_data):
            shot = Shot(
                project_id=episode.project_id,
                episode_id=episode.id,
                shot_code=s.get("shot_code", f"EP{episode.number:02d}-S{idx+1:02d}"),
                order=s.get("order", idx + 1),
                duration=s.get("duration", 5),
                description=s.get("description", ""),
                prompt=s.get("prompt", ""),
                state=ShotState.planned,
            )
            await shot.insert()

        await episode.set({"current_step": EpisodeStep.storyboard_images})

        await finish_task_record(celery_id, result={"shots": len(shots_data)})
        return result

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
