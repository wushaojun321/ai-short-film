"""Video generation Celery tasks using Seedance."""
from __future__ import annotations
import logging
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video", queue="video")
def gen_shot_video_task(self, shot_id: str):
    """Generate video for a shot using its image as first frame."""
    return run_async(_gen_shot_video_async(self.request.id, shot_id))


@celery_app.task(bind=True, name="app.tasks.video.gen_episode_videos", queue="video")
def gen_episode_videos_task(self, episode_id: str):
    """Generate all missing shot videos for an episode in order."""
    return run_async(_gen_episode_videos_async(self.request.id, episode_id))


def _should_use_prev_last_frame(shot, prev_shot) -> bool:
    if not prev_shot or not getattr(prev_shot, "last_frame_url", None):
        return False
    if getattr(shot, "use_prev_last_frame", False):
        return True
    return bool(shot.segment_code and prev_shot.segment_code == shot.segment_code)


async def _gen_episode_videos_async(celery_id: str, episode_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.episode import Episode
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord
    from app.tasks.base import finish_task_record

    try:
        episode = await Episode.get(PydanticObjectId(episode_id))
        if not episode:
            raise ValueError("Episode not found")

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        shots = await Shot.find(Shot.episode_id == episode.id).sort("+order").to_list()
        targets = [
            shot for shot in shots
            if not shot.video_url and shot.state not in (ShotState.rendering, ShotState.approved)
        ]
        total = len(targets)
        if record:
            await record.set({
                "progress": 5,
                "logs": [f"[video] 按镜头顺序生成本集视频，共 {total} 个待生成镜头"],
            })

        if not targets:
            await finish_task_record(celery_id, result={"shots": 0})
            return {"shots": 0}

        for idx, shot in enumerate(targets):
            if record:
                await record.set({
                    "progress": 5 + int(idx / total * 90),
                    "logs": (record.logs or []) + [f"[video] 开始生成 {shot.shot_code}（{idx + 1}/{total}）"],
                })
            await _gen_shot_video_async(celery_id, str(shot.id), manage_record=False)
            if record:
                await record.set({
                    "progress": 5 + int((idx + 1) / total * 90),
                    "logs": (record.logs or []) + [f"[video] {shot.shot_code} 生成完成"],
                })

        await finish_task_record(celery_id, result={"shots": total})
        return {"shots": total}

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise


async def _gen_shot_video_async(celery_id: str, shot_id: str, manage_record: bool = True):
    from app.database import init_db
    await init_db()

    import asyncio
    import json as _json
    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.asset import Asset, AssetType
    from app.models.task_record import TaskRecord
    from app.services import video_service, llm_service
    from app.services.prompt_service import render
    from app.services.storage_service import presign_if_cos
    from app.models.prompt_config import PromptConfigScope

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        # Mark as rendering immediately so frontend shows loading
        await shot.set({"state": ShotState.rendering, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id) if manage_record else None
        if record:
            await record.set({"progress": 5})

        # Build video prompt: gather asset references categorized by type.
        character_parts = []
        scene_parts = []
        prop_parts = []
        reference_image_parts = []
        reference_images: list[str] = []
        if shot.required_assets:
            asset_ids = [binding.asset_id for binding in shot.required_assets]
            assets = await Asset.find({"_id": {"$in": asset_ids}}).to_list()
            asset_map = {str(asset.id): asset for asset in assets}
        else:
            asset_map = {}

        for binding in shot.required_assets:
            asset = asset_map.get(str(binding.asset_id))
            if asset:
                asset_type_label = {
                    AssetType.character: "人物",
                    AssetType.scene: "场景",
                    AssetType.prop: "道具",
                    AssetType.template: "模板",
                }.get(asset.asset_type, "资产")
                if asset.preview_url and len(reference_images) < 9:
                    image_index = len(reference_images) + 1
                    reference_images.append(presign_if_cos(asset.preview_url))
                    reference_image_parts.append(f"[图{image_index}] {binding.asset_name}（{asset_type_label}）")
                    asset_ref = f"[图{image_index}]{binding.asset_name}"
                else:
                    asset_ref = binding.asset_name
                if asset.asset_type == AssetType.character:
                    character_parts.append(f"{asset_ref}（{asset_type_label}）")
                elif asset.asset_type == AssetType.scene:
                    scene_parts.append(f"{asset_ref}（{asset_type_label}）")
                elif asset.asset_type == AssetType.prop:
                    prop_parts.append(f"{asset_ref}（{asset_type_label}）")

        prev_shots = await Shot.find(
            Shot.episode_id == shot.episode_id,
            Shot.order < shot.order,
        ).sort("-order").limit(1).to_list()
        prev_shot = prev_shots[0] if prev_shots else None
        previous_last_frame_label = "无"
        previous_last_frame_url = None
        if _should_use_prev_last_frame(shot, prev_shot) and len(reference_images) < 10:
            previous_last_frame_url = presign_if_cos(prev_shot.last_frame_url)
            image_index = len(reference_images) + 1
            reference_images.append(previous_last_frame_url)
            previous_last_frame_label = f"[图{image_index}] 上一镜尾帧（仅作连续性辅助）"
            reference_image_parts.append(previous_last_frame_label)

        reference_image_block = "\n".join(reference_image_parts) if reference_image_parts else "无"
        direct_reference_section = (
            "【直接参考图片】\n"
            f"{reference_image_block}\n"
            "生成时必须按上方图号直接参考请求体中的 reference_image。角色资产和场景资产是身份与空间锚点，上一镜尾帧如存在，只用于动作、站位、光线和情绪承接。"
            if reference_image_parts
            else "【直接参考图片】\n无可用参考图片"
        )

        if shot.dialogues:
            dialogue_text = "；".join(
                f"{d.speaker}：{d.text}" if d.speaker else d.text
                for d in shot.dialogues
            )
        else:
            dialogue_text = "无台词"

        duration = shot.duration or 5
        seg1 = round(duration / 3)
        seg2 = round(duration * 2 / 3)
        continuity_context = "\n".join([
            f"与上一镜衔接：{shot.transition_in or '无'}",
            f"与下一镜衔接：{shot.transition_out or '无'}",
            f"本镜起始状态：{shot.start_state or '无'}",
            f"本镜结束状态：{shot.end_state or '无'}",
            f"画面方向/空间轴线：{shot.screen_direction or '无'}",
            f"连续性硬规则：{shot.continuity_notes or '无'}",
            f"上一镜尾帧辅助图：{previous_last_frame_label}",
        ])

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_video_gen,
            {
                "shot_code": shot.shot_code,
                "segment_code": shot.segment_code or "无",
                "segment_name": shot.segment_name or "无",
                "segment_function": shot.segment_function or "无",
                "shot_function": shot.shot_function or "无",
                "duration": duration,
                "seg1": seg1,
                "seg2": seg2,
                "shot_description": shot.description,
                "continuity_context": continuity_context,
                "reference_images": reference_image_block,
                "character_prompts": "\n".join(character_parts) if character_parts else "无",
                "scene_prompt": "\n".join(scene_parts) if scene_parts else "无",
                "prop_prompts": "\n".join(prop_parts) if prop_parts else "无",
                "dialogue": dialogue_text,
                "shot_prompt": "",
            },
        )

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        from app.services import sensitive_word_service

        submitted_prompt = ""

        MAX_RETRIES = 3
        result = None
        for attempt in range(MAX_RETRIES):
            # 每次重试都重新生成 prompt，注入最新黑名单
            blocked = await sensitive_word_service.get_all_words()
            blocked_note = (
                f"\n\n## 以下词语已确认会触发审核，生成提示词时必须完全规避：\n{', '.join(blocked)}"
                if blocked else ""
            )

            video_prompt = None
            try:
                raw = await llm_service.chat_json(
                    system_prompt=system_prompt + blocked_note,
                    user_prompt=user_prompt,
                )
                if isinstance(raw, str):
                    raw = _json.loads(raw)
                video_prompt = raw.get("prompt", "") or None
            except Exception as e:
                if record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt] LLM 优化失败：{e}"]})

            if not video_prompt:
                # 兜底：不含敏感词的中文视觉描述
                video_prompt = (
                    "竖屏9:16，写实电影风格，根据分镜脚本和资产设定生成短视频，"
                    "镜头运动稳定，人物动作自然，表情清晰，场景连续，光线有层次，高清质感"
                )
                if record:
                    await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底通用提示词"]})

            submitted_prompt = "\n\n".join([
                video_prompt.strip(),
                (
                    "【镜头基础信息】\n"
                    f"镜头编号：{shot.shot_code}\n"
                    f"视频时长：{duration}秒\n"
                    f"分镜描述：{shot.description}\n"
                    f"台词：{dialogue_text}\n"
                    f"连续性上下文：\n{continuity_context}"
                ),
                direct_reference_section,
            ])

            # 立即写入最终真实提交文本，前端生成中即可看到。
            await shot.set({"submitted_prompt": submitted_prompt})
            if record:
                await record.set({"logs": (record.logs or []) + [f"[prompt] 最终提交提示词：{submitted_prompt}"]})

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 10, "logs": (record.logs or []) + [f"[video] {attempt_label}正在生成视频…"]})

            logger.info(
                "[SHOT VIDEO PROMPT] shot_id=%s shot=%s attempt=%d/%d ref_images=%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                shot_id, shot.shot_code, attempt + 1, MAX_RETRIES,
                len(reference_images), submitted_prompt,
            )

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda vp=submitted_prompt: video_service.generate_video_sync(
                        prompt=vp,
                        reference_images=reference_images if reference_images else None,
                        ratio="9:16",
                        duration=duration,
                        resolution="720p",
                        return_last_frame=True,
                    ),
                )
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    words = await sensitive_word_service.extract_and_save(submitted_prompt, "video")
                    log_msg = f"[retry {attempt + 1}/{MAX_RETRIES}] 敏感词触发审核，已记录词汇：{words or '(提取失败)'}"
                    if record:
                        await record.set({"logs": (record.logs or []) + [log_msg]})
                    if attempt == MAX_RETRIES - 1:
                        raise
                    continue
                raise

        if record:
            await record.set({"progress": 80})

        # Re-upload video to COS
        video_url = await video_service.upload_video_to_cos(result["video_url"])
        raw_last_frame_url = result.get("last_frame_url")
        last_frame_url = (
            await video_service.upload_last_frame_to_cos(raw_last_frame_url)
            if raw_last_frame_url else None
        )

        updates: dict = {
            "video_url": video_url,
            "state": ShotState.rendered,
            "generation_task_id": celery_id,
            "submitted_prompt": submitted_prompt,
        }
        if last_frame_url:
            updates["last_frame_url"] = last_frame_url

        await shot.set(updates)

        if manage_record:
            await finish_task_record(celery_id, result={"video_url": video_url, "last_frame_url": last_frame_url})
        return {"video_url": video_url}

    except Exception as e:
        try:
            shot = await Shot.get(PydanticObjectId(shot_id))
            if shot:
                await shot.set({"state": ShotState.asset_ready})
        except Exception:
            pass
        if manage_record:
            await finish_task_record(celery_id, error=str(e))
        raise
