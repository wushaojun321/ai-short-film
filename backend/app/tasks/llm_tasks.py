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
    from app.models.project import Project
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
        target_count = project.target_episode_count or 1

        # 后端校验：LLM 返回集数与目标不符时补全或截断
        if len(episodes_data) != target_count:
            await log([
                f"[warn] LLM 返回 {len(episodes_data)} 集，目标 {target_count} 集，自动修正…"
            ], 70)
            if len(episodes_data) < target_count:
                # 补全缺少的集数
                for i in range(len(episodes_data) + 1, target_count + 1):
                    episodes_data.append({
                        "number": i,
                        "title": f"第{i}集",
                        "summary": f"待补充（第{i}集剧情）",
                        "word_count": episodes_data[-1].get("word_count", 500) if episodes_data else 500,
                        "estimated_duration": project.min_episode_duration or 120,
                    })
            else:
                # 截断多余的集数
                episodes_data = episodes_data[:target_count]

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
        await log([f"[episodes] 已创建 {created_eps} 集（共 {len(episodes_data)} 集）"], 80)

        # 立即创建 Asset 记录（status=pending，无图），供步骤3 Agent 操作
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
                    asset_prompt = a.get("prompt") or a.get("description", "")
                    asset = Asset(
                        project_id=project.id,
                        name=a.get("name", ""),
                        asset_type=asset_type,
                        prompt=asset_prompt,
                        status=AssetStatus.pending,
                    )
                    await asset.insert()
                    count += 1
            if count:
                asset_counts[key] = count
        asset_summary = "、".join(f"{v} 个{k}" for k, v in asset_counts.items()) if asset_counts else "无新资产"
        await log([f"[assets] 资产记录已创建：{asset_summary}（图片待步骤4生成）"], 95)

        # init_status 保持 script_uploaded，等待用户在步骤3确认
        await log(["✓ 剧本解析完成，请在步骤3确认分集与资产后继续"], 100)

        await finish_task_record(celery_id, result={
            "episodes": episodes_data,
            "assets": assets_data,
        })
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
    from app.models.shot import Shot, ShotState, ShotAssetBinding
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
                "episode_script": f"第{episode.number}集《{episode.title}》\n\n{episode.summary}",
                "continuity_notes": episode.continuity_notes or "无",
                "asset_list": str(asset_list),
                "series_style": project.series_prompt or "",
            },
        )

        if record:
            await record.set({"progress": 30})

        result = await llm_service.chat_json(system_prompt, user_prompt)

        if record:
            await record.set({"progress": 70})

        # Create shots — LLM may return array directly or {"shots": [...]}
        if isinstance(result, list):
            shots_data = result
        else:
            shots_data = result.get("shots", [])
        # Build asset name→id map once for efficiency
        asset_map = {a.name: a for a in assets}
        for idx, s in enumerate(shots_data):
            # Resolve asset bindings from LLM output
            required_assets: list[ShotAssetBinding] = []
            for ra in s.get("required_assets", []):
                name = ra.get("name", "") if isinstance(ra, dict) else str(ra)
                matched = asset_map.get(name)
                if matched:
                    required_assets.append(ShotAssetBinding(
                        asset_id=matched.id,
                        asset_name=matched.name,
                    ))

            shot = Shot(
                project_id=episode.project_id,
                episode_id=episode.id,
                shot_code=s.get("shot_code", f"EP{episode.number:02d}-S{idx+1:02d}"),
                order=s.get("order", idx + 1),
                duration=s.get("duration", 5),
                description=s.get("description", ""),
                prompt=s.get("prompt", ""),
                required_assets=required_assets,
                state=ShotState.planned,
            )
            await shot.insert()

        await episode.set({"current_step": EpisodeStep.storyboard_images})

        await finish_task_record(celery_id, result={"shots": len(shots_data)})
        return result

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
