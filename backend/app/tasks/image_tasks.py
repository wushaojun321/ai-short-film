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
    from app.services import image_service, llm_service
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

        # ── Step 1: LLM 优化 asset.prompt → Seedream 专用提示词 ──────────────
        optimized_prompt = asset.prompt  # 默认回退到原始 prompt
        try:
            system_prompt, user_prompt, _ = await render(
                PromptConfigScope.asset_prompt_gen,
                {
                    "asset_description": f"名称：{asset.name}\n类型：{asset_type_str}\n描述：{asset.prompt}",
                    "style_guide": series_prompt or "写实风格，电影质感",
                    "negative_prompt_rules": "避免模糊、变形、多余肢体、不自然比例",
                },
            )
            # 用 Ark（国内直连），避免 worker-image 无代理时 OpenRouter 403
            from openai import AsyncOpenAI as _AsyncOpenAI
            from app.config import settings as _settings
            import json as _json
            ark_client = _AsyncOpenAI(
                api_key=_settings.ark_api_key,
                base_url=_settings.ark_base_url,
            )
            resp = await ark_client.chat.completions.create(
                model=_settings.ark_llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = _json.loads(resp.choices[0].message.content or "{}")
            positive = raw.get("positive_prompt", "")
            if positive:
                optimized_prompt = positive
                await asset.set({"prompt": optimized_prompt})
        except Exception as e:
            # LLM 优化失败不阻断生图，继续用原始 prompt
            if record:
                await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败，使用原始提示词：{e}"]})

        if record:
            await record.set({"progress": 30, "logs": (record.logs or []) + ["[image] 正在生成图像…"]})

        # ── Step 2: 拼装最终 prompt 发给 Seedream ────────────────────────────
        # series_prompt 已在 asset_prompt_gen 的 style_guide 里注入，这里不重复拼接
        full_prompt = optimized_prompt

        image_url = await image_service.generate_image(
            prompt=full_prompt,
            size="2048x2048",
        )

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
    from app.services import image_service
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

        # ── LLM 优化：用 Ark（国内直连）将 shot 描述转化为纯视觉 Seedream 提示词 ──
        from openai import AsyncOpenAI as _AsyncOpenAI
        from app.config import settings as _settings
        full_prompt = None
        try:
            ark_client = _AsyncOpenAI(
                api_key=_settings.ark_api_key,
                base_url=_settings.ark_base_url,
            )
            resp = await ark_client.chat.completions.create(
                model=_settings.ark_llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            full_prompt = parsed.get("prompt", "") or None
        except Exception as e:
            if record:
                await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败：{e}"]})

        if not full_prompt:
            # 兜底：构造一个不含敏感词的简单描述
            full_prompt = (
                "cinematic vertical 9:16 shot, realistic film style, "
                "indoor living room scene, two young men, computer screens with colorful charts, "
                "dramatic lighting, close-up"
            )
            if record:
                await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底通用提示词"]})

        if record:
            await record.set({"progress": 30, "logs": (record.logs or []) + ["[image] 正在生成图像…"]})

        image_url = await image_service.generate_image(
            prompt=full_prompt,
            size="2048x3640",  # ~9:16 vertical, ≥3.6M pixels
        )

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
