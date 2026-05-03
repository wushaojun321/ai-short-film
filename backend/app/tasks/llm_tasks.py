"""LLM Celery tasks: script parsing, shot script generation."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record

# 5 万字以内允许 LLM 直接读取索引摘要；正文始终由原文块回填，不再摘要式压缩。
DIRECT_INDEX_THRESHOLD = 50000


def _group_ranges(source_ranges, target_count: int):
    """Group existing consecutive source ranges into target_count larger ranges."""
    from app.utils.script_indexer import SourceRange

    if not source_ranges:
        return []
    target = max(target_count, 1)
    if len(source_ranges) == target:
        return source_ranges
    if len(source_ranges) < target:
        return []

    grouped: list[SourceRange] = []
    for i in range(target):
        start_i = round(i * len(source_ranges) / target)
        end_i = round((i + 1) * len(source_ranges) / target) - 1
        part = source_ranges[start_i:end_i + 1]
        if part:
            grouped.append(SourceRange(part[0].start_block, part[-1].end_block))
    return grouped


def _extract_ranges_from_episode_plan(episodes_data: list[dict], blocks, target_count: int):
    from app.utils.script_indexer import normalize_ranges

    raw_ranges: list[dict] = []
    for ep in episodes_data:
        ranges = ep.get("source_block_ranges") or ep.get("source_ranges") or []
        if isinstance(ranges, list) and ranges:
            starts, ends = [], []
            for item in ranges:
                if isinstance(item, dict):
                    starts.append(item.get("start_block", item.get("start_block_index")))
                    ends.append(item.get("end_block", item.get("end_block_index")))
            try:
                raw_ranges.append({"start_block": min(int(x) for x in starts), "end_block": max(int(x) for x in ends)})
            except (TypeError, ValueError):
                continue
        elif "start_block" in ep or "end_block" in ep:
            raw_ranges.append(ep)
    ranges = normalize_ranges(raw_ranges, blocks, target_count)
    return ranges if len(ranges) == target_count else []


def _episode_title_from_range(blocks, source_range, fallback: str) -> str:
    from app.models.script_block import ScriptBlockType

    for block in blocks[source_range.start_block:source_range.end_block + 1]:
        if block.block_type == ScriptBlockType.episode_header:
            return block.text[:40]
    return fallback


def _build_range_index_digest(blocks, source_ranges, max_chars: int = 9000) -> str:
    """Build a compact index digest for selected source ranges only."""
    selected = []
    for source_range in source_ranges:
        selected.extend(
            block
            for block in blocks
            if source_range.start_block <= block.block_index <= source_range.end_block
        )

    lines: list[str] = []
    total = 0
    for block in selected:
        speaker = f" {block.speaker}：" if block.speaker else " "
        ep = f" ep={block.episode_hint}" if block.episode_hint else ""
        line = f"#{block.block_index} [{block.block_type.value}{ep} L{block.start_line}]{speaker}{block.text}"
        if total + len(line) > max_chars:
            lines.append(f"... 已截断本批索引摘要，剩余 {len(selected) - len(lines)} 个原文块仍按 block_index 引用 ...")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _merge_asset_results(target: dict, incoming: dict) -> dict:
    """Merge asset extraction batches by asset name while preserving order."""
    if not isinstance(incoming, dict):
        return target
    assets = incoming.get("assets") if "assets" in incoming else incoming
    if not isinstance(assets, dict):
        return target

    for bucket in ("characters", "scenes", "props"):
        target.setdefault(bucket, [])
        existing_names = {
            item.get("name", "")
            for item in target[bucket]
            if isinstance(item, dict)
        }
        for item in assets.get(bucket, []) or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            if not name or name in existing_names:
                continue
            target[bucket].append(item)
            existing_names.add(name)
    return target


def _known_character_packages(assets_data: dict) -> list[dict]:
    """Return compact face/voice consistency anchors for subsequent batches."""
    packages: dict[str, dict] = {}
    for item in assets_data.get("characters", []) or []:
        if not isinstance(item, dict):
            continue
        package = item.get("asset_package") or item.get("character_name") or item.get("name")
        if not package or package in packages:
            continue
        packages[package] = {
            "asset_package": package,
            "character_name": item.get("character_name") or package,
            "face_identity": item.get("face_identity", ""),
            "voice_profile": item.get("voice_profile", ""),
        }
    return list(packages.values())


def _ranges_to_jsonable(source_ranges) -> list[dict]:
    return [
        {"start_block": source_range.start_block, "end_block": source_range.end_block}
        for source_range in source_ranges
    ]


def _episode_asset_requirements(episode_data: dict) -> dict:
    req = episode_data.get("asset_requirements") if isinstance(episode_data, dict) else {}
    if not isinstance(req, dict):
        req = {}
    return {
        "characters": req.get("characters", []) if isinstance(req.get("characters", []), list) else [],
        "scenes": req.get("scenes", []) if isinstance(req.get("scenes", []), list) else [],
        "props": req.get("props", []) if isinstance(req.get("props", []), list) else [],
    }


def _compact_episode_requirements(episodes: list[dict], start: int | None = None, end: int | None = None) -> list[dict]:
    selected = episodes[start:end] if start is not None or end is not None else episodes
    compact = []
    for ep in selected:
        compact.append({
            "number": ep.get("number"),
            "title": ep.get("title", ""),
            "summary": ep.get("summary", ""),
            "source_block_ranges": ep.get("source_block_ranges", []),
            "asset_requirements": ep.get("asset_requirements", {}),
            "beats": ep.get("beats", []),
        })
    return compact


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _asset_inventory_from_blueprint(
    character_variants: list[dict],
    scenes: list[dict],
    props: list[dict],
) -> dict[str, list[dict]]:
    characters = []
    for item in character_variants:
        if not isinstance(item, dict):
            continue
        characters.append({
            "name": item.get("name") or item.get("asset_name") or item.get("character_name", ""),
            "character_name": item.get("character_name", ""),
            "asset_package": item.get("asset_package") or item.get("character_name", ""),
            "face_identity": item.get("face_identity", ""),
            "voice_profile": item.get("voice_profile", ""),
            "scene_scope": item.get("scene_scope", ""),
            "appearance_stage": item.get("appearance_stage") or item.get("state", ""),
            "view_requirements": item.get("view_requirements", "面部特写、全身形象、侧面视角"),
            "description": item.get("description", ""),
            "prompt": item.get("prompt") or item.get("description", ""),
        })

    scene_assets = []
    for item in scenes:
        if not isinstance(item, dict):
            continue
        scene_assets.append({
            "name": item.get("name") or item.get("scene_package", ""),
            "description": item.get("description", ""),
            "prompt": item.get("prompt") or item.get("description", ""),
            "scene_package": item.get("scene_package", ""),
            "state": item.get("state", ""),
            "episode_range": item.get("episode_range", ""),
        })

    prop_assets = []
    for item in props:
        if not isinstance(item, dict):
            continue
        prop_assets.append({
            "name": item.get("name") or item.get("prop_package", ""),
            "description": item.get("description", ""),
            "prompt": item.get("prompt") or item.get("description", ""),
            "prop_package": item.get("prop_package", ""),
            "state": item.get("state", ""),
            "owner": item.get("owner", ""),
            "episode_range": item.get("episode_range", ""),
        })

    return {"characters": characters, "scenes": scene_assets, "props": prop_assets}


def _fallback_character_variants(character_bible: list[dict]) -> list[dict]:
    variants = []
    for item in character_bible:
        if not isinstance(item, dict):
            continue
        character_name = item.get("character_name") or item.get("name", "")
        if not character_name:
            continue
        variants.append({
            "name": f"{character_name}-常规状态",
            "character_name": character_name,
            "asset_package": item.get("asset_package") or character_name,
            "face_identity": item.get("face_identity", ""),
            "voice_profile": item.get("voice_profile", ""),
            "scene_scope": "全剧常规场景",
            "appearance_stage": "常规状态",
            "episode_range": "全剧",
            "view_requirements": "面部特写、全身形象、侧面视角",
            "description": item.get("role", ""),
            "prompt": (
                f"{character_name}，沿用同一人物资产包的共享面部基准，"
                "写实电影质感定妆参考照，真实摄影基础，真实影视布光，克制真实氛围。"
            ),
        })
    return variants


def _fallback_character_bible_from_requirements(episodes: list[dict]) -> list[dict]:
    characters: dict[str, dict] = {}
    for ep in episodes:
        req = ep.get("asset_requirements", {}) if isinstance(ep, dict) else {}
        for item in _as_list(req.get("characters") if isinstance(req, dict) else []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            if not name or name in characters:
                continue
            characters[name] = {
                "character_id": name,
                "character_name": name,
                "asset_package": name,
                "role": item.get("role_in_episode", ""),
                "arc": "",
                "face_identity": "写实电影人物面部基准，真实五官比例和自然皮肤质感，全剧保持一致",
                "voice_profile": item.get("voice_hint", "自然真实人声，语气随剧情变化但音色保持一致"),
                "allowed_changes": ["服装", "妆发", "伤势", "随身道具", "场景状态"],
                "locked_traits": ["面部基准", "五官比例", "音色基准"],
                "face_change_rules": "全剧不改变面部基准，除非后续人工明确修改",
            }
    return list(characters.values())


def _fallback_assets_from_requirements(episodes: list[dict], key: str) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for ep in episodes:
        req = ep.get("asset_requirements", {}) if isinstance(ep, dict) else {}
        for item in _as_list(req.get(key) if isinstance(req, dict) else []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            state = item.get("state", "")
            result.append({
                "name": f"{name}-{state}" if state else name,
                "scene_package" if key == "scenes" else "prop_package": name,
                "state": state,
                "owner": item.get("owner", ""),
                "episode_range": f"第{ep.get('number')}集",
                "description": item.get("episode_usage") or item.get("usage") or state,
                "prompt": (
                    f"{name}，{state}，写实电影质感参考，真实摄影基础，"
                    "真实影视布光，真实材质，克制真实氛围。"
                ),
            })
    return result


@celery_app.task(bind=True, name="app.tasks.llm.parse_script", queue="llm")
def parse_script_task(self, project_id: str):
    """Parse script and generate episode plan + asset list."""
    return run_async(_parse_script_async(self.request.id, project_id))


async def _parse_script_async(celery_id: str, project_id: str):
    from app.database import init_db
    await init_db()

    import json
    from datetime import datetime
    from beanie import PydanticObjectId
    from app.models.project import Project
    from app.models.episode import Episode, EpisodeStatus
    from app.models.asset import Asset, AssetType, AssetStatus
    from app.models.production_blueprint import ProductionBlueprint, ProductionBlueprintStatus
    from app.models.shot import Shot
    from app.models.task_record import TaskRecord
    from app.services import llm_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope
    from app.utils.script_indexer import (
        SCRIPT_INDEX_VERSION,
        build_excerpt,
        build_index_digest,
        create_script_index,
        explicit_episode_ranges,
        fallback_even_ranges,
    )

    async def log(msgs: list[str], progress: int):
        """Append log lines and update progress atomically."""
        if record:
            current = record.logs or []
            await record.set({"logs": current + msgs, "progress": progress})

    record = None
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

        # 重新解析视为重建初始化产物；旧项目不会自动迁移，只有用户主动触发时才会重建。
        await Shot.find(Shot.project_id == project.id).delete()
        await Episode.find(Episode.project_id == project.id).delete()
        await Asset.find(Asset.project_id == project.id).delete()
        await ProductionBlueprint.find(ProductionBlueprint.project_id == project.id).delete()

        blocks = await create_script_index(project.id, project.script_text)
        if not blocks:
            raise ValueError("Script index is empty")
        await project.set({
            "script_index_version": SCRIPT_INDEX_VERSION,
            "script_indexed_at": datetime.utcnow(),
        })
        explicit_ranges = explicit_episode_ranges(blocks)
        target_count = project.target_episode_count or len(explicit_ranges) or 1
        digest_limit = 22000 if script_len <= DIRECT_INDEX_THRESHOLD else 18000
        script_index = build_index_digest(blocks, max_chars=digest_limit)
        await log([
            f"[index] 原文索引完成：{len(blocks)} 个块，显式分集边界 {len(explicit_ranges)} 个",
        ], 25)

        # SeriesPlannerAgent：只生成全剧规划，不承载分集正文。
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.series_plan,
            {
                "script_index": script_index,
                "target_episodes": target_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
            },
        )
        series_result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=8192)
        if not isinstance(series_result, dict):
            series_result = {}
        await log([
            "[series] 全剧规划完成",
        ], 40)

        series_prompt = series_result.get("series_prompt") or project.series_prompt or ""
        continuity_notes = series_result.get("continuity_notes", "")
        await project.set({"series_prompt": series_prompt})

        # EpisodePlannerAgent：输出分集蓝图和每集资产需求，正文仍由后端原文块回填。
        suggested_ranges = explicit_ranges if explicit_ranges else []
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.episode_split,
            {
                "script_index": script_index,
                "series_context": json.dumps(series_result, ensure_ascii=False),
                "target_episodes": target_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
                "suggested_ranges": json.dumps(_ranges_to_jsonable(suggested_ranges), ensure_ascii=False),
            },
        )
        try:
            split_result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=24000)
            episodes_data = split_result.get("episodes", []) if isinstance(split_result, dict) else []
        except Exception as exc:
            episodes_data = []
            await log([f"[warn] 分集蓝图生成失败，使用后端原文边界兜底：{exc}"], 52)

        source_ranges = _extract_ranges_from_episode_plan(episodes_data, blocks, target_count)
        if not source_ranges:
            grouped = _group_ranges(explicit_ranges, target_count)
            source_ranges = grouped or explicit_ranges or fallback_even_ranges(blocks, target_count)
            if explicit_ranges:
                await log(["[episodes] 使用剧本显式第X集边界，资产需求按后续蓝图补充"], 55)
            else:
                await log(["[warn] 分集范围不完整，已使用后端原文块兜底切分"], 55)
        else:
            await log(["[episodes] 分集蓝图与 block 范围规划完成"], 55)

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
        final_episodes: list[dict] = []
        for idx, source_range in enumerate(source_ranges[:target_count], start=1):
            ep_data = episodes_data[idx - 1] if idx - 1 < len(episodes_data) and isinstance(episodes_data[idx - 1], dict) else {}
            excerpt, block_ids, start_line, end_line, dialogue_count = build_excerpt(blocks, source_range)
            wc = len(excerpt)
            llm_dur = int(ep_data.get("estimated_duration", 0) or 0)
            duration = calc_duration(wc, llm_dur, project.min_episode_duration or 30)
            title = ep_data.get("title") or _episode_title_from_range(blocks, source_range, f"第{idx}集")
            summary = ep_data.get("summary") or excerpt[:80]
            ep = Episode(
                project_id=project.id,
                number=idx,
                title=title,
                summary=summary,
                script_excerpt=excerpt,
                word_count=wc,
                estimated_duration=duration,
                continuity_notes=continuity_notes,
                source_block_ids=block_ids,
                source_start_line=start_line,
                source_end_line=end_line,
                dialogue_count=dialogue_count,
                source_integrity="original" if excerpt else "summary_fallback",
                status=EpisodeStatus.not_started,
            )
            await ep.insert()
            created_eps += 1
            final_episodes.append({
                "number": ep.number,
                "title": ep.title,
                "summary": ep.summary,
                "script_excerpt": ep.script_excerpt,
                "word_count": ep.word_count,
                "estimated_duration": ep.estimated_duration,
                "source_start_line": start_line,
                "source_end_line": end_line,
                "source_integrity": ep.source_integrity,
                "source_block_ranges": [{"start_block": source_range.start_block, "end_block": source_range.end_block}],
                "dialogue_count": dialogue_count,
                "beats": ep_data.get("beats", []) if isinstance(ep_data.get("beats", []), list) else [],
                "emotion_curve": ep_data.get("emotion_curve", ""),
                "ending_hook": ep_data.get("ending_hook", ""),
                "asset_requirements": _episode_asset_requirements(ep_data),
            })
        await log([f"[episodes] 已按原文创建 {created_eps} 集"], 75)

        # ProductionBlueprint：解析阶段先产出制作蓝图，再由资产流水线消费蓝图创建资产卡片。
        blueprint_episodes = [
            {
                "number": ep["number"],
                "title": ep["title"],
                "summary": ep["summary"],
                "word_count": ep["word_count"],
                "estimated_duration": ep["estimated_duration"],
                "source_start_line": ep["source_start_line"],
                "source_end_line": ep["source_end_line"],
                "source_integrity": ep["source_integrity"],
                "source_block_ranges": ep["source_block_ranges"],
                "dialogue_count": ep["dialogue_count"],
                "beats": ep.get("beats", []),
                "emotion_curve": ep.get("emotion_curve", ""),
                "ending_hook": ep.get("ending_hook", ""),
                "asset_requirements": ep.get("asset_requirements", {}),
            }
            for ep in final_episodes
        ]
        await log(["[blueprint] 分集蓝图已生成，开始建立人物/场景/道具圣经"], 78)

        episode_requirements_json = json.dumps(_compact_episode_requirements(blueprint_episodes), ensure_ascii=False)

        try:
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.character_bible,
                {
                    "series_context": json.dumps(series_result, ensure_ascii=False),
                    "episode_asset_requirements": episode_requirements_json,
                },
            )
            character_bible_result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=12000)
            character_bible = _as_list(character_bible_result.get("characters")) if isinstance(character_bible_result, dict) else []
            if not character_bible and isinstance(character_bible_result, dict):
                legacy_assets = character_bible_result.get("assets", {})
                character_bible = _as_list(legacy_assets.get("characters")) if isinstance(legacy_assets, dict) else []
        except Exception as exc:
            character_bible = _fallback_character_bible_from_requirements(blueprint_episodes)
            await log([f"[warn] 人物圣经生成失败，已使用分集资产需求兜底：{exc}"], 82)
        await log([f"[blueprint] 人物圣经完成：{len(character_bible)} 个角色"], 82)

        character_variants: list[dict] = []

        async def plan_character_variants(batch_start: int, batch_end: int, label: str, max_tokens: int = 16000):
            batch_index = _build_range_index_digest(blocks, source_ranges[batch_start:batch_end], max_chars=9000)
            batch_requirements = json.dumps(
                _compact_episode_requirements(blueprint_episodes, batch_start, batch_end),
                ensure_ascii=False,
            )
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.character_variant_plan,
                {
                    "character_bible": json.dumps(character_bible, ensure_ascii=False),
                    "episode_asset_requirements": batch_requirements,
                    "script_index": batch_index,
                },
            )
            result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=max_tokens)
            if not isinstance(result, dict):
                return []
            variants = _as_list(result.get("character_variants"))
            if not variants:
                legacy_assets = result.get("assets", {})
                variants = _as_list(legacy_assets.get("characters")) if isinstance(legacy_assets, dict) else []
            return variants

        async def plan_character_variants_resilient(batch_start: int, batch_end: int, label: str):
            try:
                character_variants.extend(await plan_character_variants(batch_start, batch_end, label))
                await log([f"[blueprint] 人物阶段规划完成：{label}"], min(90, 82 + len(character_variants)))
            except ValueError as exc:
                if "truncated" not in str(exc).lower():
                    raise
                if batch_end - batch_start <= 1:
                    await log([f"[warn] {label} 人物阶段输出过长，提高输出上限后重试"], 86)
                    character_variants.extend(await plan_character_variants(batch_start, batch_end, label, max_tokens=24000))
                    return
                mid = batch_start + (batch_end - batch_start) // 2
                await log([f"[warn] {label} 人物阶段输出过长，自动拆分后重试"], 86)
                await plan_character_variants_resilient(batch_start, mid, f"{label}-前半")
                await plan_character_variants_resilient(mid, batch_end, f"{label}-后半")

        batch_size = 3
        for start in range(0, len(blueprint_episodes), batch_size):
            end = min(start + batch_size, len(blueprint_episodes))
            await plan_character_variants_resilient(start, end, f"第{start + 1}-{end}集")
        if not character_variants:
            character_variants = _fallback_character_variants(character_bible)

        try:
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.scene_bible,
                {
                    "series_context": json.dumps(series_result, ensure_ascii=False),
                    "episode_asset_requirements": episode_requirements_json,
                },
            )
            scene_result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=12000)
            scene_bible = _as_list(scene_result.get("scenes")) if isinstance(scene_result, dict) else []
            if not scene_bible and isinstance(scene_result, dict):
                legacy_assets = scene_result.get("assets", {})
                scene_bible = _as_list(legacy_assets.get("scenes")) if isinstance(legacy_assets, dict) else []
        except Exception as exc:
            scene_bible = _fallback_assets_from_requirements(blueprint_episodes, "scenes")
            await log([f"[warn] 场景圣经生成失败，已使用分集场景需求兜底：{exc}"], 90)
        await log([f"[blueprint] 场景圣经完成：{len(scene_bible)} 个阶段场景"], 90)

        try:
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.prop_bible,
                {
                    "series_context": json.dumps(series_result, ensure_ascii=False),
                    "episode_asset_requirements": episode_requirements_json,
                },
            )
            prop_result = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=10000)
            prop_bible = _as_list(prop_result.get("props")) if isinstance(prop_result, dict) else []
            if not prop_bible and isinstance(prop_result, dict):
                legacy_assets = prop_result.get("assets", {})
                prop_bible = _as_list(legacy_assets.get("props")) if isinstance(legacy_assets, dict) else []
        except Exception as exc:
            prop_bible = _fallback_assets_from_requirements(blueprint_episodes, "props")
            await log([f"[warn] 道具圣经生成失败，已使用分集道具需求兜底：{exc}"], 91)

        assets_data = _asset_inventory_from_blueprint(character_variants, scene_bible, prop_bible)
        blueprint_payload = {
            "series": series_result,
            "episodes": blueprint_episodes,
            "character_bible": character_bible,
            "scene_bible": scene_bible,
            "prop_bible": prop_bible,
            "character_variants": character_variants,
            "scene_variants": scene_bible,
            "prop_variants": prop_bible,
            "asset_inventory": assets_data,
        }
        try:
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.blueprint_validate,
                {"blueprint": json.dumps(blueprint_payload, ensure_ascii=False)},
            )
            continuity_report = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=12000)
            if not isinstance(continuity_report, dict):
                continuity_report = {"issues": [], "warnings": [], "status": "validated"}
        except Exception as exc:
            continuity_report = {"issues": [], "warnings": [f"蓝图校验跳过：{exc}"], "status": "needs_review"}

        blueprint = ProductionBlueprint(
            project_id=project.id,
            script_index_version=SCRIPT_INDEX_VERSION,
            series=series_result,
            episodes=blueprint_episodes,
            character_bible=character_bible,
            scene_bible=scene_bible,
            prop_bible=prop_bible,
            character_variants=character_variants,
            scene_variants=scene_bible,
            prop_variants=prop_bible,
            asset_inventory=assets_data,
            continuity_report=continuity_report,
            status=(
                ProductionBlueprintStatus.validated
                if continuity_report.get("status") == "validated"
                else ProductionBlueprintStatus.needs_review
            ),
        )
        await blueprint.insert()
        await log(["[blueprint] 制作蓝图已写入，开始派生资产卡片"], 92)

        # 立即创建 Asset 记录（status=pending，无图），供步骤3 Agent 操作
        if not isinstance(assets_data, dict):
            assets_data = {}
        type_map = {
            "characters": AssetType.character,
            "scenes": AssetType.scene,
            "props": AssetType.prop,
        }
        asset_counts: dict[str, int] = {}
        for key, asset_type in type_map.items():
            count = 0
            for a in assets_data.get(key, []):
                if not isinstance(a, dict):
                    continue
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
                        voice_profile=a.get("voice_profile", "") if asset_type == AssetType.character else "",
                        character_name=a.get("character_name", "") if asset_type == AssetType.character else "",
                        asset_package=(
                            a.get("asset_package") or a.get("character_name") or a.get("name", "")
                        ) if asset_type == AssetType.character else "",
                        face_identity=a.get("face_identity", "") if asset_type == AssetType.character else "",
                        scene_scope=a.get("scene_scope", "") if asset_type == AssetType.character else "",
                        appearance_stage=a.get("appearance_stage", "") if asset_type == AssetType.character else "",
                        view_requirements=a.get("view_requirements", "面部特写、全身形象、侧面视角") if asset_type == AssetType.character else "",
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
            "episodes": final_episodes,
            "assets": assets_data,
            "series": series_result,
            "blueprint_id": str(blueprint.id),
            "continuity_report": continuity_report,
        })
        return {
            "episodes": final_episodes,
            "assets": assets_data,
            "series": series_result,
            "blueprint_id": str(blueprint.id),
            "continuity_report": continuity_report,
        }

    except Exception as e:
        if record:
            await record.set({"logs": (record.logs or []) + [f"[error] {e}"]})
        await finish_task_record(celery_id, error=str(e))
        raise


def _duration_bounds_for_function(shot_function: str, max_shot_duration: int) -> tuple[int, int]:
    """Return the preferred duration range for a functional shot type."""
    fn = shot_function or ""
    if "建立" in fn:
        lo, hi = 5, 8
    elif "关系" in fn:
        lo, hi = 5, 7
    elif "台词" in fn or "对话" in fn:
        lo, hi = 4, 6
    elif "动作" in fn or "冲突" in fn:
        lo, hi = 3, 5
    elif "反应" in fn:
        lo, hi = 2, 4
    elif "悬念" in fn or "落点" in fn or "钩子" in fn:
        lo, hi = 2, 4
    elif "过渡" in fn or "转场" in fn:
        lo, hi = 2, 5
    else:
        lo, hi = 3, 6

    hi = min(hi, max(max_shot_duration, 1))
    lo = min(lo, hi)
    return lo, hi


def _normalize_shot_duration(raw_duration, shot_function: str, max_shot_duration: int) -> int:
    """Clamp LLM duration to a functional range instead of accepting fixed repeated values."""
    lo, hi = _duration_bounds_for_function(shot_function, max_shot_duration)
    try:
        duration = int(raw_duration)
    except (TypeError, ValueError):
        duration = round((lo + hi) / 2)
    return max(lo, min(duration, hi))


def _extract_shot_list(result) -> list[tuple[dict, dict]]:
    """Flatten new segments[] output while preserving compatibility with old flat shot arrays."""
    if isinstance(result, list):
        return [({}, s) for s in result if isinstance(s, dict)]
    if isinstance(result, dict) and "shot_code" in result:
        return [({}, result)]
    if not isinstance(result, dict):
        return []

    segments = result.get("segments")
    if isinstance(segments, list):
        flattened: list[tuple[dict, dict]] = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            shots = seg.get("shots") or seg.get("shot_list") or seg.get("storyboard") or []
            if isinstance(shots, dict) and "shot_code" in shots:
                shots = [shots]
            if not isinstance(shots, list):
                continue
            for shot in shots:
                if isinstance(shot, dict):
                    flattened.append((seg, shot))
        if flattened:
            return flattened

    shots_data = result.get("shots") or result.get("storyboard") or result.get("shot_list") or []
    if isinstance(shots_data, dict) and "shot_code" in shots_data:
        shots_data = [shots_data]
    return [({}, s) for s in shots_data if isinstance(s, dict)]


def _infer_transition_type(transition_in: str, transition_out: str, segment: dict, shot: dict) -> str:
    """Infer a conservative transition type when the LLM omits it."""
    raw = str(
        shot.get("transition_type")
        or shot.get("transition")
        or segment.get("transition_type")
        or ""
    ).strip()
    allowed = {"hard_cut", "match_cut", "audio_bridge", "crossfade", "black_gap"}
    if raw in allowed:
        return raw

    text = f"{transition_in} {transition_out} {shot.get('shot_function', '')} {segment.get('segment_function', '')}"
    if any(word in text for word in ("黑场", "停顿", "章节", "大幅跳跃", "时间跳跃", "数日后")):
        return "black_gap"
    if any(word in text for word in ("叠化", "淡入", "淡出", "情绪过渡", "回忆", "时间流逝")):
        return "crossfade"
    if any(word in text for word in ("声音", "台词尾音", "环境声", "音效", "呼吸声")):
        return "audio_bridge"
    if any(word in text for word in ("动作", "视线", "道具", "姿态", "构图", "匹配")):
        return "match_cut"
    return "hard_cut"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是", "会", "开口"}
    return bool(value)


def _as_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    return []


def _asset_binding_name(raw) -> str:
    if isinstance(raw, dict):
        return str(raw.get("name") or raw.get("asset_name") or raw.get("asset") or "").strip()
    return str(raw or "").strip()


def _resolve_asset_for_binding(raw, asset_map: dict, asset_alias_map: dict):
    """Resolve structured or legacy asset binding to an Asset document."""
    name = _asset_binding_name(raw)
    if name in asset_map:
        return asset_map[name]
    if name in asset_alias_map:
        return asset_alias_map[name]
    if isinstance(raw, dict):
        for key in ("character_name", "asset_package"):
            alias = str(raw.get(key) or "").strip()
            if alias in asset_alias_map:
                return asset_alias_map[alias]
    return None


async def _repair_storyboard_continuity(
    *,
    result: dict,
    llm_service,
    render,
    scope,
    series_prompt: str,
    script_excerpt: str,
    continuity_notes: str,
    asset_list: list[dict],
    record=None,
) -> dict:
    """Run a lightweight continuity repair pass after storyboard generation.

    This is best-effort: if the repair LLM fails or returns a malformed shape,
    the original storyboard is preserved so generation remains usable.
    """
    import json

    if not isinstance(result, dict):
        return result
    if not _extract_shot_list(result):
        return result

    try:
        system_prompt, user_prompt, _ = await render(
            scope,
            {
                "series_prompt": series_prompt,
                "script_excerpt": script_excerpt,
                "continuity_notes": continuity_notes,
                "asset_list": json.dumps(asset_list, ensure_ascii=False),
                "storyboard_json": json.dumps(result, ensure_ascii=False),
            },
        )
        repaired = await llm_service.chat_json(system_prompt, user_prompt, max_tokens=20000)
        if isinstance(repaired, dict) and _extract_shot_list(repaired):
            if record:
                issues = repaired.get("issues") or []
                issue_count = len(issues) if isinstance(issues, list) else 0
                await record.set({
                    "logs": (record.logs or []) + [f"[continuity] 分镜连续性校验完成，修复/提示 {issue_count} 项"],
                })
            return repaired
    except Exception as exc:
        if record:
            await record.set({
                "logs": (record.logs or []) + [f"[continuity] 连续性校验跳过：{exc}"],
            })
    return result


@celery_app.task(bind=True, name="app.tasks.llm.gen_shot_script", queue="llm")
def gen_shot_script_task(self, episode_id: str, max_shot_duration: int = 8, feedback: str | None = None):
    """Generate storyboard script for an episode."""
    return run_async(_gen_shot_script_async(self.request.id, episode_id, max_shot_duration, feedback))


async def _gen_shot_script_async(celery_id: str, episode_id: str, max_shot_duration: int = 8, feedback: str | None = None):
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
        asset_list = [
            {
                "name": a.name,
                "type": a.asset_type,
                "character_name": a.character_name,
                "asset_package": a.asset_package,
                "face_identity": a.face_identity,
                "scene_scope": a.scene_scope,
                "appearance_stage": a.appearance_stage,
                "view_requirements": a.view_requirements,
                "preview_url": a.preview_url,
            }
            for a in assets
        ]

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
                "max_dialogue_chars": max_shot_duration * 6,
                "feedback_section": f"\n\n修改意见：\n{feedback}" if feedback else "",
            },
        )

        if record:
            await record.set({"progress": 30})

        result = await llm_service.chat_json(system_prompt, user_prompt)
        result = await _repair_storyboard_continuity(
            result=result,
            llm_service=llm_service,
            render=render,
            scope=PromptConfigScope.shot_continuity_repair,
            series_prompt=project.series_prompt or "",
            script_excerpt=episode.script_excerpt or episode.summary or "",
            continuity_notes=episode.continuity_notes or "无",
            asset_list=asset_list,
            record=record,
        )

        if record:
            await record.set({"progress": 70})

        # 重新生成时先删除旧分镜，避免追加导致数量翻倍
        # 同时回退步骤到 storyboard_script，等用户重新审批后再推进
        is_regen = episode.current_step != EpisodeStep.storyboard_script
        if is_regen:
            await episode.set({"current_step": EpisodeStep.storyboard_script})
        await Shot.find(Shot.episode_id == episode.id).delete()

        # Create shots — supports the new segments[].shots structure and the old flat formats.
        flattened_shots = _extract_shot_list(result)
        # Build asset name/alias → document map once for efficiency.
        asset_map = {a.name: a for a in assets}
        asset_alias_map = {}
        for asset in assets:
            for alias in (
                asset.name,
                asset.character_name,
                asset.asset_package,
                f"{asset.character_name}-{asset.appearance_stage}" if asset.character_name and asset.appearance_stage else "",
            ):
                if alias and alias not in asset_alias_map:
                    asset_alias_map[alias] = asset
        previous_created_shot: Shot | None = None
        for idx, (segment, s) in enumerate(flattened_shots):
            segment_code = str(segment.get("segment_code") or segment.get("code") or "")
            segment_name = str(segment.get("segment_name") or segment.get("name") or segment.get("title") or "")
            segment_function = str(segment.get("segment_function") or segment.get("function") or "")
            shot_function = str(s.get("shot_function") or s.get("function") or "")

            # Resolve asset bindings from LLM output
            required_assets: list[ShotAssetBinding] = []
            raw_required_assets = s.get("required_assets", [])
            if isinstance(raw_required_assets, (str, dict)):
                raw_required_assets = [raw_required_assets]
            if not isinstance(raw_required_assets, list):
                raw_required_assets = []
            for ra in raw_required_assets:
                matched = _resolve_asset_for_binding(ra, asset_map, asset_alias_map)
                if matched:
                    ra_dict = ra if isinstance(ra, dict) else {}
                    role_in_shot = str(ra_dict.get("role_in_shot") or "")
                    speaking = _as_bool(ra_dict.get("speaking")) or role_in_shot == "speaker"
                    muted = _as_bool(ra_dict.get("muted")) or role_in_shot in {"listener", "background"}
                    required_assets.append(ShotAssetBinding(
                        asset_id=matched.id,
                        asset_name=matched.name,
                        asset_type=str(ra_dict.get("type") or matched.asset_type.value),
                        role_in_shot=role_in_shot,
                        character_name=str(ra_dict.get("character_name") or matched.character_name or ""),
                        asset_package=str(ra_dict.get("asset_package") or matched.asset_package or matched.character_name or ""),
                        appearance_stage=str(ra_dict.get("appearance_stage") or matched.appearance_stage or ""),
                        reference_purpose=str(ra_dict.get("reference_purpose") or ""),
                        required_views=_as_str_list(ra_dict.get("required_views")),
                        screen_position=str(ra_dict.get("screen_position") or ""),
                        action_requirement=str(ra_dict.get("action_requirement") or ""),
                        expression_requirement=str(ra_dict.get("expression_requirement") or ""),
                        continuity_requirement=str(ra_dict.get("continuity_requirement") or ""),
                        voice_required=_as_bool(ra_dict.get("voice_required")) or speaking,
                        speaking=speaking,
                        muted=muted,
                        binding_source="llm" if isinstance(ra, dict) else "legacy",
                    ))

            raw_code = s.get("shot_code")
            shot_code = str(raw_code) if raw_code is not None else f"EP{episode.number:02d}-S{idx+1:02d}"

            # 解析 dialogues 列表，兼容旧格式（dialogue/speaker 字符串）
            raw_dialogues = s.get("dialogues")
            if isinstance(raw_dialogues, list):
                from app.models.shot import ShotDialogueLine
                dialogues = [
                    ShotDialogueLine(
                        speaker=d.get("speaker", ""),
                        text=d.get("text", ""),
                        emotion=d.get("emotion", ""),
                        delivery=d.get("delivery", ""),
                        action=d.get("action", ""),
                        expression=d.get("expression", ""),
                    )
                    for d in raw_dialogues if isinstance(d, dict) and d.get("text")
                ]
            else:
                # 兼容旧格式：dialogue + speaker 字符串
                from app.models.shot import ShotDialogueLine
                old_text = s.get("dialogue", "")
                old_speaker = s.get("speaker", "")
                dialogues = [ShotDialogueLine(speaker=old_speaker, text=old_text)] if old_text else []

            transition_in = str(s.get("transition_in") or segment.get("transition_in") or "")
            transition_out = str(s.get("transition_out") or segment.get("transition_out") or "")
            use_prev_last_frame = bool(s.get("use_prev_last_frame", False))
            depends_on_last_frame_shot_id = previous_created_shot.id if (use_prev_last_frame and previous_created_shot) else None

            shot = Shot(
                project_id=episode.project_id,
                episode_id=episode.id,
                shot_code=shot_code,
                order=idx + 1,
                duration=_normalize_shot_duration(s.get("duration"), shot_function, max_shot_duration),
                segment_code=segment_code,
                segment_name=segment_name,
                segment_function=segment_function,
                shot_function=shot_function,
                transition_in=transition_in,
                transition_out=transition_out,
                transition_type=_infer_transition_type(transition_in, transition_out, segment, s),
                start_state=str(s.get("start_state") or ""),
                end_state=str(s.get("end_state") or ""),
                screen_direction=str(s.get("screen_direction") or ""),
                continuity_notes=str(s.get("continuity_notes") or ""),
                use_prev_last_frame=use_prev_last_frame,
                depends_on_last_frame_shot_id=depends_on_last_frame_shot_id,
                description=s.get("description", ""),
                dialogues=dialogues,
                prompt=s.get("prompt", ""),
                required_assets=required_assets,
                state=ShotState.planned,
            )
            await shot.insert()
            previous_created_shot = shot

        await finish_task_record(celery_id, result={"shots": len(flattened_shots)})

        # 生成完成后停留在 storyboard_script，等待用户手动审批后再推进
        # （前端点击"全部通过"时由 episodeAPI.setStep 推进到 storyboard_videos）

        return result

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
