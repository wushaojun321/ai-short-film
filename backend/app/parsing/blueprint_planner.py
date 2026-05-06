from __future__ import annotations

import asyncio
import json
import time
from typing import Awaitable, Callable

from app.models.prompt_config import PromptConfigScope
from app.services import llm_service
from app.services.prompt_service import render
from app.tasks.llm_tasks import _jsonl_plan_from_text, _ranges_to_jsonable

LogFn = Callable[[list[str], int], Awaitable[None]]


class ProductionBlueprintPlanner:
    """The single LLM planner for script parsing.

    It reads the compact script context once and emits a JSONL production
    blueprint. It does not create episodes, assets or prompts directly.
    """

    def __init__(self, project, context_pack, log: LogFn):
        self.project = project
        self.context_pack = context_pack
        self.log = log

    async def plan(self) -> tuple[dict, dict]:
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.script_production_plan,
            {
                "script_index": self.context_pack.script_index,
                "target_episodes": self.context_pack.minimum_count,
                "min_duration": self.project.min_episode_duration,
                "parse_notes": self.project.parse_notes or "",
                "suggested_ranges": json.dumps(
                    _ranges_to_jsonable(self.context_pack.suggested_ranges),
                    ensure_ascii=False,
                ),
            },
        )

        raw = await self._chat_text_step(
            system_prompt,
            user_prompt,
            max_tokens=12000,
            timeout_seconds=240,
            label="script_production_plan",
            progress=45,
        )
        production_result, plan_stats = _jsonl_plan_from_text(raw)
        await self.log([
            (
                "[plan] JSONL 蓝图解析完成："
                f"{plan_stats['parsed']}/{plan_stats['lines']} 行可用，跳过 {plan_stats['skipped']} 行"
            )
        ], 48)
        if plan_stats["parsed"] <= 0:
            raise ValueError("LLM JSONL response contained no valid planning lines")
        if not isinstance(production_result, dict):
            return {}, plan_stats
        return production_result, plan_stats

    async def _chat_text_step(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        timeout_seconds: int,
        label: str,
        progress: int,
    ) -> str:
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                llm_service.chat_completion(
                    system_prompt,
                    user_prompt,
                    temperature=0.2,
                    max_tokens=max_tokens,
                    scope=label,
                    audit={"project_id": str(self.project.id)},
                ),
                timeout=timeout_seconds,
            )
        except Exception:
            elapsed = time.perf_counter() - started
            await self.log([
                f"[timing] {label} 失败：{elapsed:.1f}s，输入约 {len(system_prompt) + len(user_prompt)} 字，输出上限 {max_tokens}"
            ], progress)
            raise

        elapsed = time.perf_counter() - started
        await self.log([
            f"[timing] {label} 完成：{elapsed:.1f}s，输入约 {len(system_prompt) + len(user_prompt)} 字，输出上限 {max_tokens}"
        ], progress)
        return result
