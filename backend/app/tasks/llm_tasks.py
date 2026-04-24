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

    async def log(msgs: list[str], progress: int):
        """Append log lines and update progress atomically."""
        if record:
            current = record.logs or []
            await record.set({"logs": current + msgs, "progress": progress})

    try:
        project = await Project.get(PydanticObjectId(project_id))
        if not project or not project.script_text:
            raise ValueError("Project or script not found")

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        script_len = len(project.script_text)
        await log([
            f"[init] 项目加载完成：{project.title}",
            f"[init] 剧本长度：{script_len} 字，目标集数：{project.target_episode_count}",
        ], 10)

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.script_parse,
            {
                "script_text": project.script_text[:8000],  # truncate for token limits
                "target_episodes": project.target_episode_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
            },
        )
        await log([
            "[prompt] Prompt 渲染完成，发送 LLM 请求…",
        ], 20)

        result = await llm_service.chat_json(system_prompt, user_prompt)
        await log([
            "✓ LLM 响应完成，开始解析结果…",
        ], 65)

        # Save series_prompt
        if "series_prompt" in result:
            await project.set({"series_prompt": result["series_prompt"]})
            await log(["[series] 剧集全局提示词已保存"], 68)

        # Create episodes
        episodes_data = result.get("episodes", [])
        created_eps = 0
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
                created_eps += 1
        await log([f"[episodes] 已创建 {created_eps} 集（共 {len(episodes_data)} 集）"], 78)

        # Create assets
        assets_data = result.get("assets", {})
        type_map = {
            "characters": AssetType.character,
            "scenes": AssetType.scene,
            "props": AssetType.prop,
        }
        asset_counts: dict[str, int] = {}
        for key, asset_type in type_map.items():
            count = 0
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
                    count += 1
            if count:
                asset_counts[key] = count
        asset_summary = "、".join(f"{v} 个{k}" for k, v in asset_counts.items()) if asset_counts else "无新资产"
        await log([f"[assets] 资产入库：{asset_summary}"], 90)

        await project.set({"init_status": ProjectInitStatus.episodes_confirmed})
        await log(["✓ 分集规划已确认，项目状态更新完成"], 100)

        await finish_task_record(celery_id, result={"episodes": len(episodes_data)})
        return result

    except Exception as e:
        if record:
            await record.set({"logs": (record.logs or []) + [f"[error] {e}"]})
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
