"""Video generation Celery tasks using Seedance."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video", queue="video")
def gen_shot_video_task(self, shot_id: str):
    """Generate video for a shot using its image as first frame."""
    return run_async(_gen_shot_video_async(self.request.id, shot_id))


async def _gen_shot_video_async(celery_id: str, shot_id: str):
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

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 5})

        # Build video prompt: gather asset prompts categorized by type
        character_parts = []
        scene_parts = []
        for binding in shot.required_assets:
            asset = await Asset.find_one(
                Asset.project_id == shot.project_id,
                Asset.name == binding.asset_name,
            )
            if asset:
                if asset.asset_type == AssetType.character:
                    character_parts.append(f"{binding.asset_name}：{asset.prompt or binding.asset_name}")
                elif asset.asset_type == AssetType.scene:
                    scene_parts.append(asset.prompt or binding.asset_name)

        if shot.dialogues:
            dialogue_text = "；".join(
                f"{d.speaker}：{d.text}" if d.speaker else d.text
                for d in shot.dialogues
            )
        else:
            dialogue_text = "无台词"

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_video_gen,
            {
                "shot_code": shot.shot_code,
                "shot_description": shot.description,
                "character_prompts": "\n".join(character_parts) if character_parts else "无",
                "scene_prompt": "；".join(scene_parts) if scene_parts else "无",
                "dialogue": dialogue_text,
                "shot_prompt": shot.prompt or "",
            },
        )

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        from app.services import sensitive_word_service

        # Gather reference asset images (pre-signed so Volcano Engine can access COS)
        reference_images: list[str] = []
        for binding in shot.required_assets:
            asset = await Asset.find_one(
                Asset.project_id == shot.project_id,
                Asset.name == binding.asset_name,
            )
            if asset and asset.preview_url:
                reference_images.append(presign_if_cos(asset.preview_url))

        first_frame_url = presign_if_cos(shot.image_url) if shot.image_url else None

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
                # 兜底：不含敏感词的纯英文视觉描述
                video_prompt = (
                    "cinematic vertical 9:16 shot, realistic film style, "
                    "indoor scene with people and computer screens, "
                    "dramatic lighting, high quality"
                )
                if record:
                    await record.set({"logs": (record.logs or []) + ["[prompt] 使用兜底通用提示词"]})

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 10, "logs": (record.logs or []) + [f"[video] {attempt_label}正在生成视频…"]})

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda vp=video_prompt: video_service.generate_video_sync(
                        prompt=vp,
                        first_frame_url=first_frame_url,
                        reference_images=reference_images if reference_images else None,
                        ratio="9:16",
                        duration=shot.duration or 5,
                        resolution="720p",
                        return_last_frame=True,
                    ),
                )
                break  # 成功，退出重试循环
            except Exception as gen_err:
                err_str = str(gen_err)
                if "SensitiveContent" in err_str:
                    words = await sensitive_word_service.extract_and_save(video_prompt, "video")
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
        last_frame_url = result.get("last_frame_url")

        updates: dict = {
            "video_url": video_url,
            "state": ShotState.rendered,
            "generation_task_id": celery_id,
            "prompt": video_prompt,
        }
        if last_frame_url:
            updates["last_frame_url"] = last_frame_url

        await shot.set(updates)

        await finish_task_record(celery_id, result={"video_url": video_url, "last_frame_url": last_frame_url})
        return {"video_url": video_url}

    except Exception as e:
        try:
            shot = await Shot.get(PydanticObjectId(shot_id))
            if shot:
                await shot.set({"state": ShotState.asset_ready})
        except Exception:
            pass
        await finish_task_record(celery_id, error=str(e))
        raise
