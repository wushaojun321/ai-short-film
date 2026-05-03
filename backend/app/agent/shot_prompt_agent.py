"""Shot video prompt agent.

This module owns the prompt-engineering step for converting a storyboard shot
into the final prompt submitted to the video generation model. The video task
still owns orchestration and external API calls.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.models.prompt_config import PromptConfigScope
from app.services import llm_service
from app.services.prompt_service import render


class ShotPromptInput(BaseModel):
    target_model: str = "seedance-2.0"
    shot_code: str
    segment_code: str = "无"
    segment_name: str = "无"
    segment_function: str = "无"
    shot_function: str = "无"
    transition_type: str = "hard_cut"
    duration: int = 5
    seg1: int = 2
    seg2: int = 4
    shot_description: str = ""
    continuity_context: str = ""
    voice_profiles: str = ""
    dialogue_text: str = "无台词"
    dialogue_performance: str = ""
    reference_image_block: str = "无"
    character_prompts: str = "无"
    scene_prompt: str = "无"
    prop_prompts: str = "无"
    asset_contract: str = "无"
    shot_prompt: str = ""
    direct_reference_section: str = "【直接参考图片】\n无可用参考图片"


class ShotPromptOutput(BaseModel):
    target_model: str
    prompt: str
    submitted_prompt: str
    raw_response: dict[str, Any] = Field(default_factory=dict)
    used_fallback: bool = False
    system_prompt: str = ""
    user_prompt: str = ""
    error: str = ""


class ShotPromptAgent:
    """Generate final per-shot video prompts for Seedance and future models."""

    fallback_prompt = (
        "竖屏9:16，写实电影风格，根据分镜脚本和资产设定生成短视频，"
        "镜头运动稳定，人物动作自然，表情清晰，场景连续，光线有层次，高清质感；"
        "如本镜包含台词，必须按台词原文同步口型和配音，保持角色固定音色"
    )

    async def generate(
        self,
        data: ShotPromptInput,
        blocked_words: list[str] | None = None,
    ) -> ShotPromptOutput:
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_video_gen,
            {
                "target_model": data.target_model,
                "shot_code": data.shot_code,
                "segment_code": data.segment_code or "无",
                "segment_name": data.segment_name or "无",
                "segment_function": data.segment_function or "无",
                "shot_function": data.shot_function or "无",
                "transition_type": data.transition_type or "hard_cut",
                "duration": data.duration,
                "seg1": data.seg1,
                "seg2": data.seg2,
                "shot_description": data.shot_description,
                "continuity_context": data.continuity_context,
                "voice_profiles": data.voice_profiles,
                "dialogue_performance": data.dialogue_performance,
                "reference_images": data.reference_image_block,
                "character_prompts": data.character_prompts or "无",
                "scene_prompt": data.scene_prompt or "无",
                "prop_prompts": data.prop_prompts or "无",
                "asset_contract": data.asset_contract or "无",
                "dialogue": data.dialogue_text,
                "shot_prompt": data.shot_prompt or "",
            },
        )

        blocked_note = (
            "\n\n## 以下词语已确认会触发审核，生成提示词时必须完全规避：\n"
            + ", ".join(blocked_words)
            if blocked_words else ""
        )

        raw: dict[str, Any] = {}
        video_prompt = ""
        used_fallback = False
        error = ""
        try:
            parsed = await llm_service.chat_json(
                system_prompt=system_prompt + blocked_note,
                user_prompt=user_prompt,
            )
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if isinstance(parsed, dict):
                raw = parsed
                video_prompt = str(raw.get("prompt", "") or "").strip()
        except Exception as exc:
            error = str(exc)
            video_prompt = ""

        if not video_prompt:
            video_prompt = self.fallback_prompt
            used_fallback = True

        dialogue_section = (
            "【台词与配音】\n"
            f"台词原文：{data.dialogue_text}\n"
            f"角色音色设定：\n{data.voice_profiles}\n"
            f"配音/表演要求：\n{data.dialogue_performance}\n"
            "执行要求：有台词时必须同步口型和配音；只有台词中的 speaker 可以开口，其他人物必须闭嘴做无声反应；"
            "无台词时不得生成画外人声或错误口型。"
        )

        submitted_prompt = "\n\n".join([
            video_prompt,
            (
                "【镜头基础信息】\n"
                f"镜头编号：{data.shot_code}\n"
                f"视频时长：{data.duration}秒\n"
                f"分镜描述：{data.shot_description}\n"
                f"连续性上下文：\n{data.continuity_context}"
            ),
            dialogue_section,
            f"【镜头资产契约】\n{data.asset_contract or '无'}",
            data.direct_reference_section,
        ])

        return ShotPromptOutput(
            target_model=data.target_model,
            prompt=video_prompt,
            submitted_prompt=submitted_prompt,
            raw_response=raw if isinstance(raw, dict) else {},
            used_fallback=used_fallback,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            error=error,
        )
