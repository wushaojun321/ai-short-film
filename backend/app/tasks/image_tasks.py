"""Image generation Celery tasks: asset images, shot storyboard images."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.image.gen_asset", queue="image")
def gen_asset_image_task(self, asset_id: str):
    """Generate preview image for an asset using Seedream."""
    return run_async(_gen_asset_image_async(self.request.id, asset_id))


async def _gen_asset_image_async(celery_id: str, asset_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetStatus, AssetVersion
    from app.models.project import Project
    from app.models.task_record import TaskRecord
    from app.services import image_service, llm_service, sensitive_word_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope
    from datetime import datetime
    import json

    try:
        asset = await Asset.get(PydanticObjectId(asset_id))
        if not asset:
            raise ValueError("Asset not found")

        # Mark as generating immediately so frontend can show loading
        await asset.set({"status": AssetStatus.generating, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 5, "logs": ["[prompt] 正在用 LLM 优化图像提示词…"]})

        # Load series_prompt for style consistency
        project = await Project.get(asset.project_id)
        series_prompt = (project.series_prompt or "") if project else ""
        asset_type_str = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)

        system_prompt, user_prompt_tpl, _ = await render(
            PromptConfigScope.asset_prompt_gen,
            {
                "asset_description": f"名称：{asset.name}\n类型：{asset_type_str}\n描述：{asset.prompt}",
                "style_guide": series_prompt or "写实风格，电影质感",
                "negative_prompt_rules": "避免模糊、变形、多余肢体、不自然比例",
            },
        )

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        MAX_RETRIES = 3
        image_url = None
        optimized_prompt = asset.prompt  # 默认回退到原始 prompt

        for attempt in range(MAX_RETRIES):
            # 每次重试都注入最新黑名单
            blocked = await sensitive_word_service.get_all_words()
            blocked_note = (
                f"\n\n## 以下词语已确认会触发审核，生成提示词时必须完全规避：\n{', '.join(blocked)}"
                if blocked else ""
            )

            full_prompt = None
            try:
                raw = await llm_service.chat_json(
                    system_prompt=system_prompt + blocked_note,
                    user_prompt=user_prompt_tpl,
                )
                if isinstance(raw, str):
                    raw = json.loads(raw)
                positive = raw.get("positive_prompt", "")
                if positive:
                    full_prompt = positive
                    optimized_prompt = positive
            except Exception as e:
                if record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败：{e}"]})

            if not full_prompt:
                full_prompt = asset.prompt  # 回退到原始 prompt

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 30, "logs": (record.logs or []) + [f"[image] {attempt_label}正在生成图像…"]})

            try:
                image_url = await image_service.generate_image(
                    prompt=full_prompt,
                    size="2048x2048",
                )
                # 将最终使用的优化 prompt 存回 asset
                await asset.set({"prompt": optimized_prompt})
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    words = await sensitive_word_service.extract_and_save(full_prompt, "image")
                    log_msg = f"[retry {attempt + 1}/{MAX_RETRIES}] 敏感词触发审核，已记录词汇：{words or '(提取失败)'}"
                    if record:
                        await record.set({"logs": (record.logs or []) + [log_msg]})
                    if attempt == MAX_RETRIES - 1:
                        raise  # 最后一次仍失败，向上抛出
                    continue  # 重试
                raise  # 非敏感词错误直接抛出

        # Record version
        version_str = f"v{len(asset.versions) + 1}"
        new_version = AssetVersion(
            version=version_str,
            url=image_url,
            prompt=full_prompt,
            created_at=datetime.utcnow(),
        )

        versions = asset.versions + [new_version]
        await asset.set({
            "preview_url": image_url,
            "versions": versions,
            "status": AssetStatus.pending,  # needs user confirmation
            "generation_task_id": celery_id,
        })

        await finish_task_record(celery_id, result={"image_url": image_url})
        return {"image_url": image_url}

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
        if shot.required_assets:
            asset_ids = [binding.asset_id for binding in shot.required_assets]
            assets = await Asset.find({"_id": {"$in": asset_ids}}).to_list()
            asset_map = {a.id: a for a in assets}
            parts = []
            for binding in shot.required_assets:
                a = asset_map.get(binding.asset_id)
                if a:
                    parts.append(f"{binding.asset_name}：{a.prompt}")
            required_assets_prompts = "\n".join(parts)

        # Get episode continuity notes
        episode = await Episode.get(shot.episode_id)
        continuity_notes = (episode.continuity_notes or "无") if episode else "无"

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_image_gen,
            {
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
                # 兜底：不含敏感词的纯英文视觉描述
                full_prompt = (
                    "cinematic vertical 9:16 shot, realistic film style, "
                    "indoor scene with people and computer screens showing colorful charts, "
                    "dramatic lighting"
                )
                if record:
                    await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底通用提示词"]})

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 30, "logs": (record.logs or []) + [f"[image] {attempt_label}正在生成图像…"]})

            try:
                image_url = await image_service.generate_image(
                    prompt=full_prompt,
                    size="2048x3640",  # ~9:16 vertical, ≥3.6M pixels
                )
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    # 提取并保存敏感词，下次重试时会注入黑名单
                    words = await sensitive_word_service.extract_and_save(full_prompt, "image")
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
