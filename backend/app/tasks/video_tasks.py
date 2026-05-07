"""Video generation Celery tasks using Seedance."""
from __future__ import annotations
import hashlib
import json
import logging
from datetime import datetime
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record

logger = logging.getLogger(__name__)
SHOT_VIDEO_PROMPT_CACHE_VERSION = "shot-video-prompt-v2"


def _exception_message(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


def _shot_prompt_payload(prompt_input, reference_images: list[str], blocked_words: list[str]) -> dict:
    try:
        prompt_data = prompt_input.model_dump(mode="json")
    except TypeError:
        prompt_data = prompt_input.model_dump()
    return {
        "version": SHOT_VIDEO_PROMPT_CACHE_VERSION,
        "prompt_input": prompt_data,
        "reference_images": reference_images,
        "blocked_words": sorted(blocked_words or []),
    }


def _shot_prompt_input_hash(prompt_input, reference_images: list[str], blocked_words: list[str]) -> str:
    raw = json.dumps(
        _shot_prompt_payload(prompt_input, reference_images, blocked_words),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video", queue="video")
def gen_shot_video_task(self, shot_id: str):
    """Generate video for a shot using its image as first frame."""
    return run_async(_gen_shot_video_async(self.request.id, shot_id))


@celery_app.task(bind=True, name="app.tasks.video.gen_episode_videos", queue="video")
def gen_episode_videos_task(self, episode_id: str):
    """Generate all missing shot videos for an episode in order."""
    return run_async(_gen_episode_videos_async(self.request.id, episode_id))


@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video_chain", queue="video")
def gen_shot_video_chain_task(self, shot_ids: list[str], chain_label: str = ""):
    """Generate a contiguous shot chain sequentially so each shot can use the previous last frame."""
    return run_async(_gen_shot_video_chain_async(self.request.id, shot_ids, chain_label))


async def _gen_shot_video_chain_async(celery_id: str, shot_ids: list[str], chain_label: str = ""):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord
    from app.tasks.base import finish_task_record
    from app.services.episode_service import invalidate_final_video

    record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
    total = len(shot_ids)
    completed = 0
    failed: list[dict[str, str]] = []
    current_index = 0

    try:
        if record:
            label = chain_label or "未命名片段"
            await record.set({
                "progress": 5,
                "logs": [f"[video-chain] 片段链开始：{label}，共 {total} 个镜头；片段内按顺序生成，后镜头等待上一镜尾帧"],
            })

        for idx, shot_id in enumerate(shot_ids):
            current_index = idx
            shot = await Shot.get(PydanticObjectId(shot_id))
            if not shot:
                raise ValueError(f"Shot not found: {shot_id}")
            if shot.video_url:
                completed += 1
                if record:
                    await record.set({
                        "progress": 5 + int((idx + 1) / max(total, 1) * 90),
                        "logs": (record.logs or []) + [f"[video-chain] {shot.shot_code} 已有视频，跳过"],
                    })
                continue
            await invalidate_final_video(shot.episode_id)

            if record:
                await record.set({
                    "progress": 5 + int(idx / max(total, 1) * 90),
                    "logs": (record.logs or []) + [f"[video-chain] 开始生成 {shot.shot_code}（{idx + 1}/{total}）"],
                })

            followup_log = f"[video-chain] {shot.shot_code} 生成完成，下一镜可引用本镜尾帧"
            try:
                await _gen_shot_video_async(celery_id, shot_id, manage_record=False, progress_record=record)
                completed += 1
            except Exception as e:
                error_text = _exception_message(e)
                followup_log = f"[video-chain][warn] {shot.shot_code} 生成失败，已标记异常并继续后续镜头：{error_text}"
                failed.append({
                    "shot_id": shot_id,
                    "shot_code": shot.shot_code,
                    "error": error_text,
                })
                logger.exception("Shot video generation failed in chain, continue next shot: %s", shot_id)

            if record:
                await record.set({
                    "progress": 5 + int((idx + 1) / max(total, 1) * 90),
                    "logs": (record.logs or []) + [followup_log],
                })

        result = {
            "shots": completed,
            "shot_ids": shot_ids,
            "chain_label": chain_label,
            "failed": len(failed),
            "failed_shots": failed,
        }
        await finish_task_record(celery_id, result=result)
        return result

    except Exception as e:
        # 基础设施级异常才会到这里；把尚未执行的排队镜头标记为异常，避免前端一直显示生成中。
        for pending_id in shot_ids[current_index + 1:]:
            try:
                pending = await Shot.get(PydanticObjectId(pending_id))
                if (
                    pending
                    and pending.generation_task_id == celery_id
                    and pending.state == ShotState.rendering
                    and not pending.video_url
                ):
                    await pending.set({
                        "state": ShotState.review_failed,
                        "review_comment": f"视频生成链异常中断：{str(e) or '未知错误'}",
                        "continuity_dirty": True,
                        "continuity_dirty_reason": "视频生成链异常中断，需要检查后重新生成。",
                    })
            except Exception:
                logger.exception("Failed to reset pending shot after chain failure: %s", pending_id)
        await finish_task_record(celery_id, error=str(e))
        raise


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
            if not shot.video_url and shot.state != ShotState.rendering
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
            await _gen_shot_video_async(celery_id, str(shot.id), manage_record=False, progress_record=record)
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


async def _gen_shot_video_async(
    celery_id: str,
    shot_id: str,
    manage_record: bool = True,
    progress_record=None,
):
    from app.database import init_db
    await init_db()

    import asyncio
    from beanie import PydanticObjectId
    from app.agent.shot_prompt_agent import ShotPromptAgent, ShotPromptInput
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord
    from app.services import video_service
    from app.services.episode_service import invalidate_final_video
    from app.services.shot_reference_builder import ShotReferenceBuilder, fallback_voice_profile

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        await invalidate_final_video(shot.episode_id)

        # Mark as rendering immediately so frontend shows loading, and clear previous generation warning.
        await shot.set({
            "state": ShotState.rendering,
            "generation_task_id": celery_id,
            "review_comment": "",
        })

        record = (
            await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
            if manage_record else progress_record
        )
        if record:
            await record.set({"progress": 5})

        reference_context = await ShotReferenceBuilder().build(shot)
        if reference_context.warnings:
            warning_text = "；".join(reference_context.warnings)
            await shot.set({
                "continuity_dirty": True,
                "continuity_dirty_reason": warning_text,
            })
            if record:
                await record.set({"logs": (record.logs or []) + [f"[preflight] {warning_text}"]})

        if shot.dialogues:
            dialogue_text = "；".join(
                f"{d.speaker}：{d.text}" if d.speaker else d.text
                for d in shot.dialogues
            )
            speakers = [d.speaker for d in shot.dialogues if d.speaker]
            unique_speakers = []
            for speaker in speakers:
                if speaker not in unique_speakers:
                    unique_speakers.append(speaker)
            muted_characters = [
                name for name in reference_context.visible_character_names
                if name not in unique_speakers
            ]
            dialogue_performance = "\n".join(
                [
                    "\n".join([
                        f"- 说话人：{d.speaker or '未指定'}",
                        f"  台词：{d.text}",
                        f"  固定音色：{reference_context.voice_profile_map.get(d.speaker, fallback_voice_profile(d.speaker or '角色'))}",
                        f"  情绪：{d.emotion or '按剧情情绪自然表达'}",
                        f"  语气/语速/停顿：{d.delivery or '吐字清晰，语速自然，台词与口型同步'}",
                        f"  同步动作：{d.action or '按分镜描述执行，不额外加戏'}",
                        f"  表情眼神：{d.expression or '按分镜描述执行'}",
                    ])
                    for d in shot.dialogues
                ] + (
                    [f"非发声角色必须闭嘴，只做无声反应：{', '.join(muted_characters)}"]
                    if muted_characters else ["除列出的说话人外，其他画面人物不得张嘴发声。"]
                )
            )
        else:
            dialogue_text = "无台词"
            dialogue_performance = (
                "本镜无台词。所有人物必须闭嘴，不得发声，不得出现画外人声；"
                "只通过表情、眼神、身体动作和镜头运动表达剧情。"
            )

        duration = shot.duration or 5
        seg1 = round(duration / 3)
        seg2 = round(duration * 2 / 3)
        continuity_context = "\n".join([
            f"与上一镜衔接：{shot.transition_in or '无'}",
            f"与下一镜衔接：{shot.transition_out or '无'}",
            f"本镜起始状态：{shot.start_state or '无'}",
            f"本镜结束状态：{shot.end_state or '无'}",
            f"画面方向/空间轴线：{shot.screen_direction or '无'}",
            f"转场类型：{getattr(shot, 'transition_type', '') or 'hard_cut'}",
            f"连续性硬规则：{shot.continuity_notes or '无'}",
            f"上一镜尾帧辅助图：{reference_context.previous_last_frame_label}",
        ])

        prompt_input = ShotPromptInput(
            target_model="seedance-2.0",
            shot_code=shot.shot_code,
            segment_code=shot.segment_code or "无",
            segment_name=shot.segment_name or "无",
            segment_function=shot.segment_function or "无",
            shot_function=shot.shot_function or "无",
            transition_type=getattr(shot, "transition_type", "") or "hard_cut",
            duration=duration,
            seg1=seg1,
            seg2=seg2,
            shot_description=shot.description,
            continuity_context=continuity_context,
            voice_profiles=reference_context.voice_profiles,
            dialogue_text=dialogue_text,
            dialogue_performance=dialogue_performance,
            reference_image_block=reference_context.reference_image_block,
            character_prompts=reference_context.character_prompts,
            scene_prompt=reference_context.scene_prompt,
            prop_prompts=reference_context.prop_prompts,
            asset_contract=reference_context.asset_contract,
            shot_prompt=shot.prompt or "",
            direct_reference_section=reference_context.direct_reference_section,
        )
        shot_prompt_agent = ShotPromptAgent()

        # ── 重试循环：最多 3 次，遇到敏感词错误时提取词 + 重新生成 prompt ──────
        from app.services import sensitive_word_service

        submitted_prompt = ""
        submitted_prompt_input_hash = ""

        MAX_RETRIES = 3
        result = None
        for attempt in range(MAX_RETRIES):
            # 每次重试都重新生成 prompt，注入最新黑名单
            blocked = await sensitive_word_service.get_all_words()
            prompt_input_hash = _shot_prompt_input_hash(
                prompt_input,
                reference_context.reference_images,
                blocked,
            )

            if (
                attempt == 0
                and shot.submitted_prompt
                and shot.submitted_prompt_input_hash == prompt_input_hash
            ):
                submitted_prompt = shot.submitted_prompt
                submitted_prompt_input_hash = prompt_input_hash
                if record:
                    await record.set({
                        "logs": (record.logs or []) + ["[prompt-agent] 输入未变化，复用已保存的最终提交提示词"]
                    })
            else:
                prompt_output = await shot_prompt_agent.generate(
                    prompt_input,
                    blocked_words=blocked,
                    audit={
                        "project_id": str(shot.project_id),
                        "episode_id": str(shot.episode_id),
                        "shot_id": str(shot.id),
                        "shot_code": shot.shot_code,
                        "attempt": attempt + 1,
                    },
                )
                if prompt_output.error and record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt-agent] LLM 优化失败：{prompt_output.error}"]})
                if prompt_output.used_fallback and record:
                    # 兜底：不含敏感词的中文视觉描述
                    await record.set({"logs": (record.logs or []) + ["[prompt-agent] 使用兜底通用提示词"]})

                submitted_prompt = prompt_output.submitted_prompt

                # 立即写入最终真实提交文本，前端生成中即可看到。
                prompt_updates = {"submitted_prompt": submitted_prompt}
                if prompt_output.used_fallback:
                    prompt_updates["submitted_prompt_input_hash"] = ""
                    prompt_updates["submitted_prompt_cached_at"] = None
                    submitted_prompt_input_hash = ""
                else:
                    prompt_updates["submitted_prompt_input_hash"] = prompt_input_hash
                    prompt_updates["submitted_prompt_cached_at"] = datetime.utcnow()
                    submitted_prompt_input_hash = prompt_input_hash
                await shot.set(prompt_updates)
                if record:
                    await record.set({"logs": (record.logs or []) + [f"[prompt] 最终提交提示词：{submitted_prompt}"]})

            if record:
                attempt_label = f"第 {attempt + 1} 次" if attempt > 0 else ""
                await record.set({"progress": 10, "logs": (record.logs or []) + [f"[video] {attempt_label}正在生成视频…"]})

            logger.info(
                "[SHOT VIDEO PROMPT] shot_id=%s shot=%s attempt=%d/%d ref_images=%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
                shot_id, shot.shot_code, attempt + 1, MAX_RETRIES,
                len(reference_context.reference_images), submitted_prompt,
            )

            try:
                loop = asyncio.get_running_loop()
                provider_task_id = await loop.run_in_executor(
                    None,
                    lambda vp=submitted_prompt: video_service.create_video_task_sync(
                        prompt=vp,
                        reference_images=reference_context.reference_images if reference_context.reference_images else None,
                        ratio="9:16",
                        duration=duration,
                        resolution="720p",
                        return_last_frame=True,
                    ),
                )
                if record:
                    provider_task_ids = list(record.provider_task_ids or [])
                    if provider_task_id not in provider_task_ids:
                        provider_task_ids.append(provider_task_id)
                    await record.set({
                        "provider": "seedance",
                        "provider_task_id": provider_task_id,
                        "provider_task_ids": provider_task_ids,
                        "logs": (record.logs or []) + [f"[seedance] 已创建平台任务：{provider_task_id}"],
                    })
                result = await loop.run_in_executor(
                    None,
                    lambda task_id=provider_task_id: video_service.poll_video_task_sync(task_id),
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

        from app.models.shot import ShotVersion

        version_label = f"v{len(shot.versions) + 1}"
        new_version = ShotVersion(
            version=version_label,
            video_url=video_url,
            last_frame_url=last_frame_url,
            prompt=submitted_prompt,
            description=shot.description,
            created_at=datetime.utcnow(),
        )

        updates: dict = {
            "video_url": video_url,
            "state": ShotState.rendered,
            "generation_task_id": celery_id,
            "submitted_prompt": submitted_prompt,
            "submitted_prompt_input_hash": submitted_prompt_input_hash,
            "submitted_prompt_cached_at": datetime.utcnow() if submitted_prompt_input_hash else None,
            "continuity_dirty": bool(reference_context.warnings),
            "continuity_dirty_reason": "；".join(reference_context.warnings) if reference_context.warnings else "",
            "review_comment": "",
            "version": version_label,
            "versions": shot.versions + [new_version],
        }
        if last_frame_url:
            updates["last_frame_url"] = last_frame_url

        await shot.set(updates)

        dependent_shots = await Shot.find(Shot.depends_on_last_frame_shot_id == shot.id).to_list()
        if dependent_shots:
            for dependent in dependent_shots:
                if dependent.video_url:
                    await dependent.set({
                        "continuity_dirty": True,
                        "continuity_dirty_reason": f"依赖镜头 {shot.shot_code} 已重新生成，上一镜尾帧发生变化，建议刷新本镜视频。",
                    })

        if manage_record:
            await finish_task_record(celery_id, result={
                "video_url": video_url,
                "last_frame_url": last_frame_url,
                "provider_task_id": result.get("task_id") if result else None,
            })
        return {"video_url": video_url}

    except Exception as e:
        try:
            shot = await Shot.get(PydanticObjectId(shot_id))
            if shot:
                error_text = _exception_message(e)
                await shot.set({
                    "state": ShotState.review_failed,
                    "review_comment": f"视频生成失败：{error_text}",
                    "continuity_dirty": True,
                    "continuity_dirty_reason": "视频生成任务异常，需要检查提示词、资产引用或重新生成。",
                })
        except Exception:
            pass
        if manage_record:
            await finish_task_record(celery_id, error=str(e))
        raise
