"""Image generation Celery tasks: asset images, shot storyboard images."""
from __future__ import annotations
import logging
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record

logger = logging.getLogger(__name__)


ASSET_NEGATIVE_PROMPT = (
    "不要动漫风，不要插画风，不要游戏CG，不要3D建模，不要二次元，不要卡通，"
    "不要漫画线条，不要Q版，不要角色立绘，不要设定图，不要塑料皮肤，不要过度磨皮，不要蜡像感，"
    "不要夸张大眼，不要娃娃脸，不要美颜滤镜感，不要低质感服装，不要材质像塑料，"
    "不要多视角拼图，不要三宫格，不要分屏，不要同图展示多张参考，不要模糊、变形、多余肢体、不自然比例"
)


CHARACTER_VIEW_SPECS = {
    "face": {
        "label": "面部特写",
        "instruction": "胸口以上近景，正面脸部为主体，五官、骨相、皮肤纹理、眼神必须清晰，背景简洁，服装只露出领口和肩部",
    },
    "full_body": {
        "label": "全身正面",
        "instruction": "全身正面站姿，从头到脚完整入画，服装、妆发、配饰、道具和身形比例清楚，脸部保持与面部特写同一张脸",
    },
    "side": {
        "label": "侧面视角",
        "instruction": "人物侧面或三分之二侧面视角，脸型轮廓、鼻梁、下颌线、发型和服装侧面结构清楚，脸部身份与正面保持一致",
    },
}


def _merge_negative_prompt(prompt: str, negative_prompt: str | None = None) -> str:
    """Append negative style constraints to the actual Seedream prompt."""
    parts = [ASSET_NEGATIVE_PROMPT]
    if negative_prompt:
        parts.append(negative_prompt.strip())
    merged = "；".join(part for part in parts if part)
    return f"{prompt.strip()}\n\n反向约束：{merged}"


def _character_view_prompt(base_prompt: str, view_key: str) -> str:
    spec = CHARACTER_VIEW_SPECS[view_key]
    sanitized = (
        base_prompt.strip()
        .replace("三视图", "单视角资产参考图")
        .replace("画面必须同时包含：面部特写、全身正面形象、侧面视角", "")
        .replace("画面必须同时包含面部特写、全身正面形象、侧面视角", "")
        .replace("画面包含三部分：面部特写、全身正面形象、侧面视角", "")
    )
    return (
        f"{sanitized}\n\n"
        f"本次只生成一张独立人物资产图：{spec['label']}。{spec['instruction']}。"
        "风格必须偏超现实电影质感：真实人像基础上带有高级电影美术、梦境般光影、细腻材质和强烈氛围，"
        "但仍保持真实皮肤、真实织物和可用于视频参考的可信人物形象。"
        "严禁把面部特写、全身正面、侧面视角拼在同一张图里；严禁三宫格、分屏、多视角合成图；"
        "严禁动漫、卡通、插画、游戏CG、3D建模质感。"
    )


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
                "asset_description": (
                    f"名称：{asset.name}\n"
                    f"类型：{asset_type_str}\n"
                    f"角色本名：{asset.character_name or '无'}\n"
                    f"人物资产包：{asset.asset_package or asset.character_name or '无'}\n"
                    f"共享面部基准：{asset.face_identity or '无'}\n"
                    f"适用场景：{asset.scene_scope or '无'}\n"
                    f"剧情/造型阶段：{asset.appearance_stage or '无'}\n"
                    f"视角要求：{asset.view_requirements or '面部特写、全身形象、侧面视角'}\n"
                    f"描述：{asset.prompt}"
                ),
                "style_guide": series_prompt or "超现实电影质感，真实人像基础，梦境般光影，高级电影美术",
                "negative_prompt_rules": "避免动漫、卡通、插画、游戏CG、3D建模、三宫格、分屏、多视角拼图、模糊、变形、多余肢体、不自然比例",
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
            negative_prompt = None
            try:
                raw = await llm_service.chat_json(
                    system_prompt=system_prompt + blocked_note,
                    user_prompt=user_prompt_tpl,
                )
                if isinstance(raw, str):
                    raw = json.loads(raw)
                positive = raw.get("positive_prompt", "")
                negative_prompt = raw.get("negative_prompt", "")
                if positive:
                    full_prompt = positive
                    optimized_prompt = positive
            except Exception as e:
                if record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败：{e}"]})

            if not full_prompt:
                # 兜底：用资产名称构造中性中文 prompt，避免原始 prompt 中可能的敏感词
                asset_type_label = {"character": "人物", "scene": "场景", "prop": "道具"}.get(asset_type_str, "主体")
                if asset_type_str == "character":
                    full_prompt = (
                        f"竖屏9:16，真人演员古装定妆参考图，超现实电影质感，名称：{asset.name}，"
                        f"角色本名：{asset.character_name or asset.name}，适用场景：{asset.scene_scope or '按剧本场景'}，"
                        f"人物资产包：{asset.asset_package or asset.character_name or asset.name}，"
                        f"共享面部基准：{asset.face_identity or '保持同一脸型、骨相、五官比例和皮肤质感'}，"
                        f"剧情/造型阶段：{asset.appearance_stage or '按剧本阶段'}，同一位演员同一套造型，"
                        "与同一人物资产包内其他造型保持同一张脸、同一骨相、同一五官比例；"
                        "除非剧本明确面部受伤、毁容、年龄变化或伪装改变，否则不得改变面部身份，"
                        "真实皮肤纹理，自然毛孔，真实织物，梦境般电影光影，高级美术置景，高清"
                    )
                else:
                    full_prompt = (
                        f"竖屏9:16，{asset_type_label}影视参考图，名称：{asset.name}，"
                        "超现实电影质感，主体清晰完整，真实材质细节丰富，梦境般电影光影，高级美术置景，高清，"
                        "场景资产使用影视场景参考照风格，道具资产使用真实产品摄影风格"
                    )
                if record:
                    await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底安全提示词（LLM 优化失败）"]})
            submitted_prompt = _merge_negative_prompt(full_prompt, negative_prompt)

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 30, "logs": (record.logs or []) + [f"[image] {attempt_label}正在生成图像…"]})

            try:
                generated_view_urls: dict[str, str] = {}
                submitted_prompts: dict[str, str] = {}

                if asset_type_str == "character":
                    for view_key, spec in CHARACTER_VIEW_SPECS.items():
                        view_submitted_prompt = _merge_negative_prompt(
                            _character_view_prompt(full_prompt, view_key),
                            negative_prompt,
                        )
                        submitted_prompts[view_key] = view_submitted_prompt
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
                else:
                    logger.info(
                        "[ASSET IMAGE PROMPT] asset_id=%s asset=%s attempt=%d/%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                        asset_id, asset.name, attempt + 1, MAX_RETRIES, submitted_prompt,
                    )
                    image_url = await image_service.generate_image(
                        prompt=submitted_prompt,
                        size="1600x2848",  # 9:16 vertical 2K, avoids square character-card bias
                    )
                # 将最终使用的优化 prompt 存回 asset
                await asset.set({"prompt": optimized_prompt})
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
