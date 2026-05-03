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


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _text_value(*values, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _norm_token(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _should_materialize_asset(item: dict, parent: dict | None = None) -> bool:
    """Qualitative asset gate: skip background/reference-only entries without a hard count cap."""
    parent = parent or {}
    level = _norm_token(item.get("asset_level") or item.get("build_level") or parent.get("asset_level"))
    importance = _norm_token(item.get("importance") or parent.get("importance"))
    text = f"{level} {importance} {item.get('reason', '')} {item.get('description', '')}"
    blocked = (
        "background",
        "ignored",
        "ignore",
        "reference_only",
        "no_asset",
        "not_required",
        "optional",
        "不建模",
        "不需要",
        "忽略",
        "背景",
        "路人",
        "群众",
    )
    return not any(token in text for token in blocked)


def _merge_key(*parts: str) -> str:
    raw = "|".join(str(part or "").strip() for part in parts if str(part or "").strip())
    return raw.lower() or "unnamed"


def _append_unique(target: list[dict], seen: set[str], key: str, item: dict):
    if key in seen:
        return
    seen.add(key)
    target.append(item)


def _registry_from_plan(plan_result: dict) -> dict:
    registry = _as_dict(plan_result.get("asset_registry"))
    if registry:
        return registry
    assets = _as_dict(plan_result.get("assets"))
    if assets:
        return assets
    return {"characters": [], "scenes": [], "props": []}


def _character_bible_from_registry(characters: list[dict]) -> list[dict]:
    bible: list[dict] = []
    seen: set[str] = set()
    for item in characters:
        if not isinstance(item, dict):
            continue
        character_name = _text_value(item.get("character_name"), item.get("name"))
        if not character_name:
            continue
        asset_package = _text_value(item.get("asset_package"), character_name)
        key = _merge_key(asset_package)
        if key in seen:
            continue
        seen.add(key)
        bible.append({
            "character_id": item.get("character_id") or asset_package,
            "character_name": character_name,
            "asset_package": asset_package,
            "role": _text_value(item.get("role"), item.get("description")),
            "arc": item.get("arc", ""),
            "importance": item.get("importance", ""),
            "reuse_scope": item.get("reuse_scope", ""),
            "face_identity": _text_value(
                item.get("face_identity"),
                "写实电影人物面部基准，真实五官比例和自然皮肤质感，全剧保持一致",
            ),
            "voice_profile": _text_value(
                item.get("voice_profile"),
                item.get("voice_hint"),
                "自然真实人声，语气随剧情变化但音色保持一致",
            ),
            "allowed_changes": item.get("allowed_changes", ["服装", "妆发", "伤势", "随身道具", "场景状态"]),
            "locked_traits": item.get("locked_traits", ["面部基准", "五官比例", "音色基准"]),
            "face_change_rules": item.get("face_change_rules", "全剧不改变面部基准，除非剧本明确说明"),
        })
    return bible


def _character_variants_from_registry(characters: list[dict]) -> list[dict]:
    variants: list[dict] = []
    seen: set[str] = set()
    for item in characters:
        if not isinstance(item, dict):
            continue
        character_name = _text_value(item.get("character_name"), item.get("name"))
        if not character_name:
            continue
        asset_package = _text_value(item.get("asset_package"), character_name)
        face_identity = _text_value(
            item.get("face_identity"),
            "写实电影人物面部基准，真实五官比例和自然皮肤质感，全剧保持一致",
        )
        voice_profile = _text_value(
            item.get("voice_profile"),
            item.get("voice_hint"),
            "自然真实人声，语气随剧情变化但音色保持一致",
        )
        raw_variants = _as_list(item.get("variants"))
        if not raw_variants:
            raw_variants = [item]
        for variant in raw_variants:
            if not isinstance(variant, dict) or not _should_materialize_asset(variant, item):
                continue
            scene_scope = _text_value(variant.get("scene_scope"), item.get("scene_scope"), "按剧本主要场景")
            appearance_stage = _text_value(
                variant.get("appearance_stage"),
                variant.get("state"),
                item.get("appearance_stage"),
                item.get("state"),
                "常规状态",
            )
            name = _text_value(
                variant.get("name"),
                item.get("asset_name"),
                item.get("name"),
                f"{character_name}-{appearance_stage}",
            )
            key = _merge_key(variant.get("merge_key") or f"{asset_package}|{appearance_stage}|{scene_scope}|{name}")
            prompt_seed = _text_value(
                variant.get("prompt_seed"),
                variant.get("prompt"),
                item.get("prompt_seed"),
                item.get("prompt"),
                f"{name}，沿用{asset_package}人物资产包共享面部基准，写实电影质感定妆参考照，真实摄影基础，真实影视布光。",
            )
            _append_unique(variants, seen, key, {
                "name": name,
                "character_name": character_name,
                "asset_package": asset_package,
                "face_identity": face_identity,
                "voice_profile": voice_profile,
                "scene_scope": scene_scope,
                "appearance_stage": appearance_stage,
                "episode_range": _text_value(variant.get("episode_range"), item.get("reuse_scope"), item.get("episode_range")),
                "view_requirements": _text_value(variant.get("view_requirements"), item.get("view_requirements"), "面部特写、全身形象、侧面视角"),
                "description": _text_value(variant.get("description"), item.get("description"), item.get("role")),
                "prompt": prompt_seed,
                "importance": variant.get("importance", item.get("importance", "")),
                "asset_level": variant.get("asset_level", item.get("asset_level", "")),
                "reuse_scope": variant.get("reuse_scope", item.get("reuse_scope", "")),
                "stage_change_reason": variant.get("stage_change_reason", ""),
                "merge_key": variant.get("merge_key", key),
            })
    return variants


def _bucket_variants_from_registry(items: list[dict], bucket: str) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    package_key = "scene_package" if bucket == "scenes" else "prop_package"
    state_fallback = "常规状态"
    for item in items:
        if not isinstance(item, dict):
            continue
        package = _text_value(item.get(package_key), item.get("name"))
        if not package:
            continue
        raw_variants = _as_list(item.get("variants"))
        if not raw_variants:
            raw_variants = [item]
        for variant in raw_variants:
            if not isinstance(variant, dict) or not _should_materialize_asset(variant, item):
                continue
            state = _text_value(variant.get("state"), item.get("state"), state_fallback)
            name = _text_value(variant.get("name"), item.get("asset_name"), item.get("name"), f"{package}-{state}")
            key = _merge_key(variant.get("merge_key") or f"{package}|{state}|{name}")
            prompt_seed = _text_value(
                variant.get("prompt_seed"),
                variant.get("prompt"),
                item.get("prompt_seed"),
                item.get("prompt"),
                f"{name}，写实电影质感参考，真实摄影基础，真实影视布光，真实材质，克制真实氛围。",
            )
            payload = {
                "name": name,
                package_key: package,
                "state": state,
                "episode_range": _text_value(variant.get("episode_range"), item.get("reuse_scope"), item.get("episode_range")),
                "description": _text_value(variant.get("description"), item.get("description")),
                "prompt": prompt_seed,
                "importance": variant.get("importance", item.get("importance", "")),
                "asset_level": variant.get("asset_level", item.get("asset_level", "")),
                "reuse_scope": variant.get("reuse_scope", item.get("reuse_scope", "")),
                "stage_change_reason": variant.get("stage_change_reason", ""),
                "merge_key": variant.get("merge_key", key),
            }
            if bucket == "props":
                payload["owner"] = _text_value(variant.get("owner"), item.get("owner"))
            _append_unique(result, seen, key, payload)
    return result


def _assets_from_production_plan(asset_registry: dict, blueprint_episodes: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    characters = _as_list(asset_registry.get("characters"))
    scenes = _as_list(asset_registry.get("scenes"))
    props = _as_list(asset_registry.get("props"))

    character_bible = _character_bible_from_registry(characters)
    character_variants = _character_variants_from_registry(characters)
    scene_variants = _bucket_variants_from_registry(scenes, "scenes")
    prop_variants = _bucket_variants_from_registry(props, "props")

    if not character_bible:
        character_bible = _fallback_character_bible_from_requirements(blueprint_episodes)
    if not character_variants:
        character_variants = _fallback_character_variants(character_bible)
    if not scene_variants:
        scene_variants = _fallback_assets_from_requirements(blueprint_episodes, "scenes")
    if not prop_variants:
        prop_variants = _fallback_assets_from_requirements(blueprint_episodes, "props")

    return character_bible, character_variants, scene_variants, prop_variants


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

    import asyncio
    import json
    import time
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

    async def chat_json_step(
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        timeout_seconds: int = 240,
        label: str = "",
        progress: int = 25,
    ) -> dict:
        """Bound non-critical planning calls so parse jobs can fall back instead of hanging."""
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                llm_service.chat_json(system_prompt, user_prompt, max_tokens=max_tokens),
                timeout=timeout_seconds,
            )
        except Exception as exc:
            if label:
                elapsed = time.perf_counter() - started
                await log([
                    f"[timing] {label} 失败：{elapsed:.1f}s，输入约 {len(system_prompt) + len(user_prompt)} 字，输出上限 {max_tokens}"
                ], progress)
            raise
        if label:
            elapsed = time.perf_counter() - started
            await log([
                f"[timing] {label} 完成：{elapsed:.1f}s，输入约 {len(system_prompt) + len(user_prompt)} 字，输出上限 {max_tokens}"
            ], progress)
        return result

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
        # 5 万字以内尽量把完整索引交给单次综合规划；索引会比原文略长，按原文长度放大预留。
        digest_limit = min(max(script_len * 3, 22000), 140000) if script_len <= DIRECT_INDEX_THRESHOLD else 90000
        script_index = build_index_digest(blocks, max_chars=digest_limit)
        await log([
            f"[index] 原文索引完成：{len(blocks)} 个块，显式分集边界 {len(explicit_ranges)} 个",
        ], 25)

        # ScriptProductionPlanAgent：一次完成全剧、分集、资产注册表规划；正文仍由后端原文块回填。
        suggested_ranges = explicit_ranges if explicit_ranges else []
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.script_production_plan,
            {
                "script_index": script_index,
                "target_episodes": target_count,
                "min_duration": project.min_episode_duration,
                "parse_notes": project.parse_notes or "",
                "suggested_ranges": json.dumps(_ranges_to_jsonable(suggested_ranges), ensure_ascii=False),
            },
        )
        try:
            production_result = await chat_json_step(
                system_prompt,
                user_prompt,
                max_tokens=22000,
                timeout_seconds=420,
                label="script_production_plan",
                progress=45,
            )
        except Exception as exc:
            production_result = {}
            await log([f"[warn] 综合制作规划失败，使用后端原文边界兜底：{exc}"], 45)
        if not isinstance(production_result, dict):
            production_result = {}

        series_result = _as_dict(production_result.get("series"))
        if not series_result:
            series_result = {
                "series_prompt": production_result.get("series_prompt") or "",
                "main_storyline": production_result.get("main_storyline") or "",
                "continuity_notes": production_result.get("continuity_notes") or "",
            }
        series_prompt = series_result.get("series_prompt") or project.series_prompt or (
            "写实电影质感，真实摄影基础，真实影视布光，真实材质，电影级调色，克制真实氛围"
        )
        series_result["series_prompt"] = series_prompt
        continuity_notes = series_result.get("continuity_notes") or production_result.get("continuity_notes", "")
        await project.set({"series_prompt": series_prompt})
        await log(["[plan] 综合制作规划完成，开始按原文块回填分集"], 50)

        episodes_data = _as_list(production_result.get("episodes"))
        planned_ranges = _extract_ranges_from_episode_plan(episodes_data, blocks, target_count)
        if explicit_ranges and len(explicit_ranges) == target_count:
            source_ranges = explicit_ranges
            await log(["[episodes] 使用剧本显式第X集边界，LLM 仅补充标题、概要和资产需求"], 55)
        elif planned_ranges:
            source_ranges = planned_ranges
            await log(["[episodes] 使用综合规划返回的 block 范围"], 55)
        else:
            grouped = _group_ranges(explicit_ranges, target_count)
            source_ranges = grouped or explicit_ranges or fallback_even_ranges(blocks, target_count)
            if explicit_ranges:
                await log(["[episodes] 综合规划范围不完整，已按剧本显式第X集边界兜底"], 55)
            else:
                await log(["[warn] 分集范围不完整，已使用后端原文块兜底切分"], 55)

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

        # ProductionBlueprint：解析阶段只使用综合规划结果和后端归并规则，不再串行调用人物/场景/道具圣经。
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
        await log(["[blueprint] 分集蓝图已生成，开始后端归并资产注册表"], 78)

        asset_registry = _registry_from_plan(production_result)
        character_bible, character_variants, scene_bible, prop_bible = _assets_from_production_plan(
            asset_registry,
            blueprint_episodes,
        )
        assets_data = _asset_inventory_from_blueprint(character_variants, scene_bible, prop_bible)
        continuity_report = _as_dict(production_result.get("continuity_report"))
        if not continuity_report:
            continuity_report = {"issues": [], "warnings": [], "status": "needs_review"}
        continuity_report.setdefault("status", "needs_review")
        continuity_report.setdefault("issues", [])
        continuity_report.setdefault("warnings", [])
        ignored_assets = _as_list(production_result.get("ignored_assets"))
        if ignored_assets:
            continuity_report["ignored_assets"] = ignored_assets

        await log([
            (
                "[blueprint] 资产注册表归并完成："
                f"{len(character_bible)} 个角色包、{len(character_variants)} 个人物阶段、"
                f"{len(scene_bible)} 个场景阶段、{len(prop_bible)} 个道具阶段"
            )
        ], 90)

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
