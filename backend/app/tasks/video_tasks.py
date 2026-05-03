"""Video generation Celery tasks using Seedance."""
from __future__ import annotations
import logging
from datetime import datetime
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
    from beanie import PydanticObjectId
    from app.agent.shot_prompt_agent import ShotPromptAgent, ShotPromptInput
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord
    from app.services import video_service
    from app.services.shot_reference_builder import ShotReferenceBuilder, fallback_voice_profile

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        # Mark as rendering immediately so frontend shows loading
        await shot.set({"state": ShotState.rendering, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id) if manage_record else None
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

        MAX_RETRIES = 3
        result = None
        for attempt in range(MAX_RETRIES):
            # 每次重试都重新生成 prompt，注入最新黑名单
            blocked = await sensitive_word_service.get_all_words()

            prompt_output = await shot_prompt_agent.generate(
                prompt_input,
                blocked_words=blocked,
            )
            if prompt_output.error and record:
                await record.set({"logs": (record.logs or []) + [f"[prompt-agent] LLM 优化失败：{prompt_output.error}"]})
            if prompt_output.used_fallback and record:
                # 兜底：不含敏感词的中文视觉描述
                await record.set({"logs": (record.logs or []) + ["[prompt-agent] 使用兜底通用提示词"]})

            submitted_prompt = prompt_output.submitted_prompt

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
                len(reference_context.reference_images), submitted_prompt,
            )

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda vp=submitted_prompt: video_service.generate_video_sync(
                        prompt=vp,
                        reference_images=reference_context.reference_images if reference_context.reference_images else None,
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
            "continuity_dirty": bool(reference_context.warnings),
            "continuity_dirty_reason": "；".join(reference_context.warnings) if reference_context.warnings else "",
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
