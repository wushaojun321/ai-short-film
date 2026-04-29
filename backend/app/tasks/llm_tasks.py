"""LLM Celery tasks: script parsing, shot script generation."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record

# 超过此字数时启用 Map-Reduce 分段解析
LONG_SCRIPT_THRESHOLD = 10000


def _split_script(text: str, target_episodes: int) -> list[str]:
    """按目标集数均分剧本，在段落边界切分，每段约 6000 字。"""
    chunk_size = max(6000, len(text) // max(target_episodes, 1))
    chunks, pos = [], 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind('\n\n', pos + int(chunk_size * 0.5), end)
            if boundary > pos:
                end = boundary + 2
        chunks.append(text[pos:end].strip())
        pos = end
    return [c for c in chunks if c]


def _build_reduce_input(chunks_results: list[dict]) -> str:
    """将 N 段 map 结果合并为 Reduce 阶段的 script_text。"""
    lines = []
    for i, r in enumerate(chunks_results):
        lines.append(f"=== 第 {i + 1} 段摘要 ===")
        lines.append(f"情节：{r.get('plot_summary', '')}")
        chars = r.get('characters', [])
        if chars:
            lines.append("人物：" + "；".join(
                f"{c['name']}（{c.get('description', '')}）" for c in chars
            ))
        scenes = r.get('scenes', [])
        if scenes:
            lines.append("场景：" + "；".join(
                f"{s['name']}（{s.get('description', '')}）" for s in scenes
            ))
        props = [p for p in r.get('props', []) if int(p.get('significance', 0)) >= 4]
        if props:
            lines.append("道具：" + "；".join(p['name'] for p in props))
        hints = r.get('episode_hints', [])
        if hints:
            lines.append("分集建议：" + "；".join(hints))
        lines.append("")
    return "\n".join(lines)


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

        # ── Map-Reduce 分支（长剧本） ─────────────────────────────────────────
        if script_len >= LONG_SCRIPT_THRESHOLD:
            import asyncio
            from app.models.prompt_config import PromptConfigScope as Scope

            await log([
                f"[map-reduce] 剧本 {script_len} 字，超过 {LONG_SCRIPT_THRESHOLD} 字阈值，启用 Map-Reduce 分段解析…"
            ], 15)

            chunks = _split_script(project.script_text, project.target_episode_count)
            total = len(chunks)
            await log([f"[map-reduce] 切分为 {total} 段，开始并发提取摘要…"], 18)

            # 获取 Map prompt（只取 system_prompt 和 user_prompt_template）
            map_config = await render(Scope.script_map, {
                "chunk_index": 1, "total_chunks": total, "chunk_text": "",
            })
            map_sys = map_config[0]
            map_user_tpl = map_config[2].get("user_prompt_template", "")

            sem = asyncio.Semaphore(3)
            completed = [0]  # 用列表包装以在闭包中修改

            async def map_chunk(chunk: str, idx: int):
                async with sem:
                    user_p = map_user_tpl.format(
                        chunk_index=idx + 1,
                        total_chunks=total,
                        chunk_text=chunk,
                    )
                    result = await llm_service.chat_json(map_sys, user_p, max_tokens=8192)
                    completed[0] += 1
                    pct = 18 + int(completed[0] / total * 32)
                    await log([f"[map] 第 {idx + 1}/{total} 段提取完成"], pct)
                    return result

            map_results = await asyncio.gather(*[map_chunk(c, i) for i, c in enumerate(chunks)])
            await log(["[map-reduce] Map 阶段完成，合并摘要，准备 Reduce…"], 52)

            script_text_for_reduce = _build_reduce_input(list(map_results))
        else:
            # 短剧本：直接截断走原有逻辑
            script_text_for_reduce = project.script_text[:8000]

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.script_parse,
            {
                "script_text": script_text_for_reduce,
                "target_episodes": project.target_episode_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
            },
        )
        await log([
            "[prompt] Prompt 渲染完成，发送 LLM 请求…",
        ], 55)

        result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=16384)
        await log([
            "✓ LLM 响应完成，开始解析结果…",
        ], 70)

        # Save series_prompt
        if "series_prompt" in result:
            await project.set({"series_prompt": result["series_prompt"]})
            await log(["[series] 剧集全局提示词已保存"], 72)

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

        def calc_duration(word_count: int, llm_duration: int, min_dur: int) -> int:
            """字数推算兜底：word_count ÷ 3.5 × 1.4，与 min_dur 取较大值，向上取整到 5 的倍数。
            若 LLM 返回值在合理范围内（±50% of formula）则尊重 LLM，否则用公式修正。"""
            import math
            formula = word_count / 3.5 * 1.4 if word_count > 0 else min_dur
            lo, hi = formula * 0.5, formula * 1.5
            chosen = llm_duration if (lo <= llm_duration <= hi and llm_duration > 0) else formula
            result_sec = max(chosen, min_dur or 30)
            return int(math.ceil(result_sec / 5) * 5)

        created_eps = 0
        for ep_data in episodes_data:
            existing = await Episode.find_one(
                Episode.project_id == project.id,
                Episode.number == ep_data.get("number", 0),
            )
            if not existing:
                wc = ep_data.get("word_count", 0)
                llm_dur = ep_data.get("estimated_duration", 0)
                duration = calc_duration(wc, llm_dur, project.min_episode_duration or 30)
                ep = Episode(
                    project_id=project.id,
                    number=ep_data.get("number", 0),
                    title=ep_data.get("title", ""),
                    summary=ep_data.get("summary", ""),
                    script_excerpt=ep_data.get("script_excerpt", ""),
                    word_count=wc,
                    estimated_duration=duration,
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
def gen_shot_script_task(self, episode_id: str, max_shot_duration: int = 5, feedback: str | None = None):
    """Generate storyboard script for an episode."""
    return run_async(_gen_shot_script_async(self.request.id, episode_id, max_shot_duration, feedback))


async def _gen_shot_script_async(celery_id: str, episode_id: str, max_shot_duration: int = 5, feedback: str | None = None):
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
                "series_prompt": project.series_prompt or "",
                "episode_number": episode.number,
                "episode_title": episode.title,
                "script_excerpt": episode.script_excerpt or episode.summary or "",
                "continuity_notes": episode.continuity_notes or "无",
                "asset_list": str(asset_list),
                "max_shot_duration": max_shot_duration,
                "feedback_section": f"\n\n修改意见：\n{feedback}" if feedback else "",
            },
        )

        if record:
            await record.set({"progress": 30})

        result = await llm_service.chat_json(system_prompt, user_prompt)

        if record:
            await record.set({"progress": 70})

        # 重新生成时先删除旧分镜，避免追加导致数量翻倍
        # 同时回退步骤到 storyboard_script，等用户重新审批后再推进
        is_regen = episode.current_step != EpisodeStep.storyboard_script
        if is_regen:
            await episode.set({"current_step": EpisodeStep.storyboard_script})
        await Shot.find(Shot.episode_id == episode.id).delete()

        # Create shots — LLM may return array or dict with various key names
        if isinstance(result, list):
            shots_data = result
        elif isinstance(result, dict) and "shot_code" in result:
            # LLM returned a single shot object instead of an array
            shots_data = [result]
        else:
            shots_data = (
                result.get("shots")
                or result.get("storyboard")
                or result.get("shot_list")
                or []
            )
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

            raw_code = s.get("shot_code")
            shot_code = str(raw_code) if raw_code is not None else f"EP{episode.number:02d}-S{idx+1:02d}"

            # 解析 dialogues 列表，兼容旧格式（dialogue/speaker 字符串）
            raw_dialogues = s.get("dialogues")
            if isinstance(raw_dialogues, list):
                from app.models.shot import ShotDialogueLine
                dialogues = [
                    ShotDialogueLine(speaker=d.get("speaker", ""), text=d.get("text", ""))
                    for d in raw_dialogues if isinstance(d, dict) and d.get("text")
                ]
            else:
                # 兼容旧格式：dialogue + speaker 字符串
                from app.models.shot import ShotDialogueLine
                old_text = s.get("dialogue", "")
                old_speaker = s.get("speaker", "")
                dialogues = [ShotDialogueLine(speaker=old_speaker, text=old_text)] if old_text else []

            shot = Shot(
                project_id=episode.project_id,
                episode_id=episode.id,
                shot_code=shot_code,
                order=s.get("order", idx + 1),
                duration=s.get("duration", 5),
                description=s.get("description", ""),
                dialogues=dialogues,
                prompt=s.get("prompt", ""),
                required_assets=required_assets,
                state=ShotState.planned,
            )
            await shot.insert()

        await finish_task_record(celery_id, result={"shots": len(shots_data)})

        # 生成完成后停留在 storyboard_script，等待用户手动审批后再推进
        # （前端点击"全部通过"时由 episodeAPI.advanceStep 推进到 storyboard_images）

        return result

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
