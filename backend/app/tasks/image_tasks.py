"""Image generation Celery tasks: asset images, shot storyboard images."""
from __future__ import annotations
import logging
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record
from app.services.asset_prompt_builder import CHARACTER_VIEW_SPECS, build_asset_submitted_prompts

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.image.gen_asset", queue="image")
def gen_asset_image_task(self, asset_id: str):
    """Generate preview image for an asset using Seedream."""
    return run_async(_gen_asset_image_async(self.request.id, asset_id))


async def _gen_asset_image_async(celery_id: str, asset_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetStatus, AssetVersion
    from app.models.task_record import TaskRecord
    from app.services import image_service, sensitive_word_service
    from datetime import datetime

    try:
        asset = await Asset.get(PydanticObjectId(asset_id))
        if not asset:
            raise ValueError("Asset not found")

        # Mark as generating immediately so frontend can show loading
        await asset.set({"status": AssetStatus.generating, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 5, "logs": ["[prompt] 正在构建最终提交提示词…"]})

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        MAX_RETRIES = 3
        image_url = None
        asset_type_str = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
        project_assets = await Asset.find(Asset.project_id == asset.project_id).to_list()
        generated_view_urls: dict[str, str] = {}
        submitted_prompts: dict[str, str] = {}
        submitted_prompt = ""
        final_submitted_prompt = ""
        final_submitted_prompts: dict[str, str] = {}

        for attempt in range(MAX_RETRIES):
            blocked = await sensitive_word_service.get_all_words()
            submitted_prompt, submitted_prompts = build_asset_submitted_prompts(
                asset,
                project_assets,
                blocked_words=blocked,
            )

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 30, "logs": (record.logs or []) + [f"[image] {attempt_label}正在生成图像…"]})

            try:
                generated_view_urls = {}

                if asset_type_str == "character":
                    for view_key, spec in CHARACTER_VIEW_SPECS.items():
                        view_submitted_prompt = submitted_prompts[view_key]
                        if record:
                            await record.set({
                                "progress": 30 + min(55, len(generated_view_urls) * 18),
                                "logs": (record.logs or []) + [f"[image] 正在生成{spec['label']}…"],
                            })
                        logger.info(
                            "[ASSET IMAGE PROMPT] asset_id=%s asset=%s view=%s attempt=%d/%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                            asset_id, asset.name, view_key, attempt + 1, MAX_RETRIES, view_submitted_prompt,
                        )
                        generated_view_urls[view_key] = await image_service.generate_image(
                            prompt=view_submitted_prompt,
                            size="1600x2848",
                        )
                    image_url = generated_view_urls.get("full_body") or next(iter(generated_view_urls.values()))
                    submitted_prompt = "\n\n---\n\n".join(
                        f"{CHARACTER_VIEW_SPECS[key]['label']}：\n{prompt}"
                        for key, prompt in submitted_prompts.items()
                    )
                    final_submitted_prompts = dict(submitted_prompts)
                else:
                    logger.info(
                        "[ASSET IMAGE PROMPT] asset_id=%s asset=%s attempt=%d/%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                        asset_id, asset.name, attempt + 1, MAX_RETRIES, submitted_prompt,
                    )
                    image_url = await image_service.generate_image(
                        prompt=submitted_prompt,
                        size="1600x2848",  # 9:16 vertical 2K, avoids square character-card bias
                    )
                    final_submitted_prompts = {}
                final_submitted_prompt = submitted_prompt
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    words = await sensitive_word_service.extract_and_save(submitted_prompt, "image")
                    log_msg = f"[retry {attempt + 1}/{MAX_RETRIES}] 敏感词触发审核，已记录词汇：{words or '(提取失败)'}"
                    if record:
                        await record.set({"logs": (record.logs or []) + [log_msg]})
                    if attempt == MAX_RETRIES - 1:
                        raise  # 最后一次仍失败，向上抛出
                    continue  # 重试
                raise  # 非敏感词错误直接抛出

        # Record version
        generated_view_urls = generated_view_urls if asset_type_str == "character" else {}
        if generated_view_urls:
            new_versions = [
                AssetVersion(
                    version=f"v{len(asset.versions) + idx + 1}",
                    url=url,
                    prompt=submitted_prompts.get(view_key, submitted_prompt),
                    note=CHARACTER_VIEW_SPECS[view_key]["label"],
                    view_type=view_key,
                    created_at=datetime.utcnow(),
                )
                for idx, (view_key, url) in enumerate(generated_view_urls.items())
            ]
        else:
            new_versions = [
                AssetVersion(
                    version=f"v{len(asset.versions) + 1}",
                    url=image_url,
                    prompt=submitted_prompt,
                    created_at=datetime.utcnow(),
                )
            ]

        versions = asset.versions + new_versions
        await asset.set({
            "submitted_prompt": final_submitted_prompt,
            "submitted_prompts": final_submitted_prompts,
            "preview_url": image_url,
            "view_urls": generated_view_urls or asset.view_urls,
            "versions": versions,
            "status": AssetStatus.pending,  # needs user confirmation
            "generation_task_id": celery_id,
        })

        await finish_task_record(celery_id, result={"image_url": image_url, "view_urls": generated_view_urls})
        return {"image_url": image_url, "view_urls": generated_view_urls}

    except Exception as e:
        # Reset status on failure
        try:
            asset = await Asset.get(PydanticObjectId(asset_id))
            if asset:
                await asset.set({"status": AssetStatus.need_regen})
        except Exception:
            pass
        await finish_task_record(celery_id, error=str(e))
        raise


@celery_app.task(bind=True, name="app.tasks.image.gen_shot_image", queue="image")
def gen_shot_image_task(self, shot_id: str):
    """Generate storyboard image for a shot."""
    return run_async(_gen_shot_image_async(self.request.id, shot_id))


async def _gen_shot_image_async(celery_id: str, shot_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.project import Project
    from app.models.task_record import TaskRecord
    from app.services import image_service, llm_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope
    import json

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        # Mark as generating immediately
        await shot.set({"state": ShotState.generating, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 5, "logs": ["[prompt] 正在用 LLM 优化图像提示词…"]})

        # Load series_prompt
        project = await Project.get(shot.project_id)
        series_prompt = (project.series_prompt or "") if project else ""

        # Build required_assets_prompts from asset bindings
        from app.models.asset import Asset
        from app.models.episode import Episode
        required_assets_prompts = ""
        asset_prompt_parts = []
        if shot.required_assets:
            asset_ids = [binding.asset_id for binding in shot.required_assets]
            assets = await Asset.find({"_id": {"$in": asset_ids}}).to_list()
            asset_map = {str(a.id): a for a in assets}
            parts = []
            for binding in shot.required_assets:
                a = asset_map.get(str(binding.asset_id))
                if a:
                    asset_type = {
                        "character": "人物",
                        "scene": "场景",
                        "prop": "道具",
                        "template": "模板",
                    }.get(a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type), "资产")
                    line = f"{binding.asset_name}（{asset_type}）：{a.prompt or binding.asset_name}"
                    parts.append(line)
                    asset_prompt_parts.append(f"- {line}")
            required_assets_prompts = "\n".join(parts)
        asset_prompt_block = "\n".join(asset_prompt_parts) if asset_prompt_parts else "无"

        # Get episode continuity notes
        episode = await Episode.get(shot.episode_id)
        continuity_notes = (episode.continuity_notes or "无") if episode else "无"

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_image_gen,
            {
                "shot_code": shot.shot_code,
                "shot_description": shot.description,
                "required_assets_prompts": required_assets_prompts or "无",
                "continuity_notes": continuity_notes,
                "style_guide": series_prompt or "写实风格，电影质感，竖屏9:16",
            },
        )

        from app.services import sensitive_word_service

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        MAX_RETRIES = 3
        image_url = None
        submitted_prompt = ""
        for attempt in range(MAX_RETRIES):
            # 每次重试都重新生成 prompt，注入最新黑名单
            blocked = await sensitive_word_service.get_all_words()
            blocked_note = (
                f"\n\n## 以下词语已确认会触发审核，生成提示词时必须完全规避：\n{', '.join(blocked)}"
                if blocked else ""
            )

            full_prompt = None
            try:
                raw = await llm_service.chat_json(
                    system_prompt=system_prompt + blocked_note,
                    user_prompt=user_prompt,
                )
                if isinstance(raw, str):
                    raw = json.loads(raw)
                full_prompt = raw.get("prompt", "") or None
            except Exception as e:
                if record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败：{e}"]})

            if not full_prompt:
                # 兜底：不含敏感词的中文视觉描述
                full_prompt = (
                    "竖屏9:16，写实电影风格，当前分镜的第一帧静止画面，"
                    "人物和场景清晰可辨，构图稳定，光线有层次，高清质感，"
                    "避免模糊、变形、多余肢体、不自然比例"
                )
                if record:
                    await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底通用提示词"]})

            submitted_prompt = "\n\n".join([
                full_prompt.strip(),
                (
                    "【镜头基础信息】\n"
                    f"镜头编号：{shot.shot_code}\n"
                    f"分镜描述：{shot.description}\n"
                    f"连续性约束：{continuity_notes}"
                ),
                f"【引用资产】\n{asset_prompt_block}",
            ])
            await shot.set({"prompt": submitted_prompt, "submitted_prompt": submitted_prompt})

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 30, "logs": (record.logs or []) + [f"[image] {attempt_label}正在生成图像…"]})

            logger.info(
                "[SHOT IMAGE PROMPT] shot_id=%s shot=%s attempt=%d/%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                shot_id, shot.shot_code, attempt + 1, MAX_RETRIES, submitted_prompt,
            )

            try:
                image_url = await image_service.generate_image(
                    prompt=submitted_prompt,
                    size="2048x3640",  # ~9:16 vertical, ≥3.6M pixels
                )
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    # 提取并保存敏感词，下次重试时会注入黑名单
                    words = await sensitive_word_service.extract_and_save(submitted_prompt, "image")
                    log_msg = f"[retry {attempt + 1}/{MAX_RETRIES}] 敏感词触发审核，已记录词汇：{words or '(提取失败)'}"
                    if record:
                        await record.set({"logs": (record.logs or []) + [log_msg]})
                    if attempt == MAX_RETRIES - 1:
                        raise  # 最后一次仍失败，向上抛出
                    continue  # 重试
                raise  # 非敏感词错误直接抛出

        await shot.set({
            "image_url": image_url,
            "state": ShotState.asset_ready,
            "generation_task_id": celery_id,
            "prompt": submitted_prompt,
            "submitted_prompt": submitted_prompt,
        })

        await finish_task_record(celery_id, result={"image_url": image_url})
        return {"image_url": image_url}

    except Exception as e:
        try:
            shot = await Shot.get(PydanticObjectId(shot_id))
            if shot:
                await shot.set({"state": ShotState.planned})
        except Exception:
            pass
        await finish_task_record(celery_id, error=str(e))
        raise
