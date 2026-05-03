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


def _should_use_prev_last_frame(shot, prev_shot) -> bool:
    if not prev_shot or not getattr(prev_shot, "last_frame_url", None):
        return False
    if getattr(shot, "use_prev_last_frame", False):
        return True
    return bool(shot.segment_code and prev_shot.segment_code == shot.segment_code)


def _fallback_voice_profile(name: str, prompt: str = "") -> str:
    base = prompt or name
    if any(word in base for word in ("女性", "女子", "公主", "长公主", "皇后", "侍女")):
        return f"{name}固定音色：成年女性声线，吐字清晰，情绪随剧情变化但年龄感和音色质感保持一致，不要变成少女撒娇音，不要尖叫失真。"
    if any(word in base for word in ("少年", "年轻")):
        return f"{name}固定音色：年轻男性声线，清晰自然，语速稳定，情绪表达克制，不要变成女性音色或夸张动漫腔。"
    return f"{name}固定音色：成年男性声线，音色稳定，吐字清晰，语速中等，情绪克制，不要变成女性音色，不要忽高忽低。"


def _needs_side_reference(shot_description: str, transition_text: str = "") -> bool:
    text = f"{shot_description} {transition_text}"
    return any(word in text for word in ("侧面", "侧脸", "侧身", "三分之二侧", "回头", "转身", "背身"))


def _append_reference_image(
    reference_images: list[str],
    reference_image_parts: list[str],
    *,
    url: str | None,
    label: str,
    asset_type_label: str,
    presign,
    max_images: int = 10,
) -> str | None:
    if not url or len(reference_images) >= max_images:
        return None
    image_index = len(reference_images) + 1
    reference_images.append(presign(url))
    reference_image_parts.append(f"[图{image_index}] {label}（{asset_type_label}）")
    return f"[图{image_index}]"


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
        voice_profile_parts = []
        voice_profile_map: dict[str, str] = {}
        reference_image_parts = []
        reference_images: list[str] = []
        if shot.required_assets:
            asset_ids = [binding.asset_id for binding in shot.required_assets]
            assets = await Asset.find({"_id": {"$in": asset_ids}}).to_list()
            asset_map = {str(asset.id): asset for asset in assets}
        else:
            asset_map = {}

        project_assets = await Asset.find(Asset.project_id == shot.project_id).to_list()
        package_face_refs: dict[str, str] = {}
        for asset in project_assets:
            if asset.asset_type != AssetType.character:
                continue
            package_key = asset.asset_package or asset.character_name or asset.name
            face_url = (asset.view_urls or {}).get("face")
            if package_key and face_url and package_key not in package_face_refs:
                package_face_refs[package_key] = face_url

        side_reference_needed = _needs_side_reference(
            shot.description,
            f"{shot.transition_in} {shot.transition_out} {shot.start_state} {shot.end_state}",
        )

        for binding in shot.required_assets:
            asset = asset_map.get(str(binding.asset_id))
            if asset:
                asset_type_label = {
                    AssetType.character: "人物",
                    AssetType.scene: "场景",
                    AssetType.prop: "道具",
                    AssetType.template: "模板",
                }.get(asset.asset_type, "资产")
                if asset.asset_type == AssetType.character:
                    ref_labels = []
                    package_key = asset.asset_package or asset.character_name or asset.name
                    identity_face_url = (asset.view_urls or {}).get("face") or package_face_refs.get(package_key)
                    face_ref = _append_reference_image(
                        reference_images,
                        reference_image_parts,
                        url=identity_face_url,
                        label=f"{binding.asset_name}-身份面部锚点",
                        asset_type_label=asset_type_label,
                        presign=presign_if_cos,
                    )
                    if face_ref:
                        ref_labels.append(face_ref)

                    current_look_url = (asset.view_urls or {}).get("full_body") or asset.preview_url
                    if current_look_url and current_look_url != identity_face_url:
                        look_ref = _append_reference_image(
                            reference_images,
                            reference_image_parts,
                            url=current_look_url,
                            label=f"{binding.asset_name}-当前造型",
                            asset_type_label=asset_type_label,
                            presign=presign_if_cos,
                        )
                        if look_ref:
                            ref_labels.append(look_ref)

                    side_url = (asset.view_urls or {}).get("side")
                    if side_reference_needed and side_url and side_url not in (identity_face_url, current_look_url):
                        side_ref = _append_reference_image(
                            reference_images,
                            reference_image_parts,
                            url=side_url,
                            label=f"{binding.asset_name}-侧面轮廓辅助",
                            asset_type_label=asset_type_label,
                            presign=presign_if_cos,
                        )
                        if side_ref:
                            ref_labels.append(side_ref)

                    asset_ref = f"{''.join(ref_labels)}{binding.asset_name}" if ref_labels else binding.asset_name
                    character_parts.append(f"{asset_ref}（{asset_type_label}）")
                    voice_profile = asset.voice_profile or _fallback_voice_profile(asset.name, asset.prompt)
                    voice_profile_map[asset.name] = voice_profile
                    voice_profile_parts.append(f"{asset.name}：{voice_profile}")
                elif asset.asset_type == AssetType.scene:
                    ref = _append_reference_image(
                        reference_images,
                        reference_image_parts,
                        url=asset.preview_url,
                        label=binding.asset_name,
                        asset_type_label=asset_type_label,
                        presign=presign_if_cos,
                    )
                    asset_ref = f"{ref}{binding.asset_name}" if ref else binding.asset_name
                    scene_parts.append(f"{asset_ref}（{asset_type_label}）")
                elif asset.asset_type == AssetType.prop:
                    ref = _append_reference_image(
                        reference_images,
                        reference_image_parts,
                        url=asset.preview_url,
                        label=binding.asset_name,
                        asset_type_label=asset_type_label,
                        presign=presign_if_cos,
                    )
                    asset_ref = f"{ref}{binding.asset_name}" if ref else binding.asset_name
                    prop_parts.append(f"{asset_ref}（{asset_type_label}）")

        dependency_shot = None
        if getattr(shot, "depends_on_last_frame_shot_id", None):
            dependency_shot = await Shot.get(shot.depends_on_last_frame_shot_id)

        prev_shots = await Shot.find(
            Shot.episode_id == shot.episode_id,
            Shot.order < shot.order,
        ).sort("-order").limit(1).to_list()
        prev_shot = dependency_shot or (prev_shots[0] if prev_shots else None)
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
            speakers = [d.speaker for d in shot.dialogues if d.speaker]
            unique_speakers = []
            for speaker in speakers:
                if speaker not in unique_speakers:
                    unique_speakers.append(speaker)
            muted_characters = [
                name for name in voice_profile_map
                if name not in unique_speakers
            ]
            dialogue_performance = "\n".join(
                [
                    "\n".join([
                        f"- 说话人：{d.speaker or '未指定'}",
                        f"  台词：{d.text}",
                        f"  固定音色：{voice_profile_map.get(d.speaker, _fallback_voice_profile(d.speaker or '角色'))}",
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

        voice_profiles = "\n".join(voice_profile_parts) if voice_profile_parts else "无可用角色音色设定；按角色身份保持自然、稳定、写实的中文声线。"

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
                "transition_type": getattr(shot, "transition_type", "") or "hard_cut",
                "duration": duration,
                "seg1": seg1,
                "seg2": seg2,
                "shot_description": shot.description,
                "continuity_context": continuity_context,
                "voice_profiles": voice_profiles,
                "dialogue_performance": dialogue_performance,
                "reference_images": reference_image_block,
                "character_prompts": "\n".join(character_parts) if character_parts else "无",
                "scene_prompt": "\n".join(scene_parts) if scene_parts else "无",
                "prop_prompts": "\n".join(prop_parts) if prop_parts else "无",
                "dialogue": dialogue_text,
                "shot_prompt": shot.prompt or "",
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
                    f"角色音色设定：\n{voice_profiles}\n"
                    f"台词与表演：\n{dialogue_performance}\n"
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
            "continuity_dirty": False,
            "continuity_dirty_reason": "",
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
