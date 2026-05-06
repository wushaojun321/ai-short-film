from __future__ import annotations

import math
from typing import Awaitable, Callable

from app.models.episode import Episode, EpisodeStatus
from app.tasks.llm_tasks import (
    _as_list,
    _episode_asset_requirements,
    _episode_title_from_range,
    _group_ranges,
)
from app.utils.script_indexer import build_excerpt, fallback_even_ranges

LogFn = Callable[[list[str], int], Awaitable[None]]


class EpisodeMaterialBuilder:
    """Create Episode documents by backfilling source text from ScriptBlock ranges."""

    def __init__(self, project, blocks: list, log: LogFn):
        self.project = project
        self.blocks = blocks
        self.log = log

    async def build(
        self,
        *,
        plan: dict,
        planned_ranges: list,
        explicit_ranges: list,
        minimum_count: int,
        continuity_notes: str,
    ) -> tuple[list[dict], list]:
        episodes_data = _as_list(plan.get("episodes"))
        source_ranges = await self._select_source_ranges(
            explicit_ranges=explicit_ranges,
            planned_ranges=planned_ranges,
            minimum_count=minimum_count,
        )

        created_eps = 0
        final_episodes: list[dict] = []
        for idx, source_range in enumerate(source_ranges, start=1):
            ep_data = (
                episodes_data[idx - 1]
                if idx - 1 < len(episodes_data) and isinstance(episodes_data[idx - 1], dict)
                else {}
            )
            excerpt, block_ids, start_line, end_line, dialogue_count = build_excerpt(self.blocks, source_range)
            word_count = len(excerpt)
            llm_duration = int(ep_data.get("estimated_duration", 0) or 0)
            duration = self._calc_duration(word_count, llm_duration, self.project.min_episode_duration or 30)
            title = ep_data.get("title") or _episode_title_from_range(self.blocks, source_range, f"第{idx}集")
            summary = ep_data.get("summary") or excerpt[:80]

            ep = Episode(
                project_id=self.project.id,
                number=idx,
                title=title,
                summary=summary,
                script_excerpt=excerpt,
                word_count=word_count,
                estimated_duration=duration,
                continuity_notes=continuity_notes,
                source_block_ids=block_ids,
                source_start_line=start_line,
                source_end_line=end_line,
                dialogue_count=dialogue_count,
                source_integrity="original" if excerpt else "summary_fallback",
                status=EpisodeStatus.not_started,
            )
            await ep.insert()
            created_eps += 1
            final_episodes.append({
                "number": ep.number,
                "title": ep.title,
                "summary": ep.summary,
                "script_excerpt": ep.script_excerpt,
                "word_count": ep.word_count,
                "estimated_duration": ep.estimated_duration,
                "source_start_line": start_line,
                "source_end_line": end_line,
                "source_integrity": ep.source_integrity,
                "source_block_ranges": [{"start_block": source_range.start_block, "end_block": source_range.end_block}],
                "dialogue_count": dialogue_count,
                "beats": ep_data.get("beats", []) if isinstance(ep_data.get("beats", []), list) else [],
                "emotion_curve": ep_data.get("emotion_curve", ""),
                "ending_hook": ep_data.get("ending_hook", ""),
                "asset_requirements": _episode_asset_requirements(ep_data),
            })

        await self.log([f"[episodes] 已按原文创建 {created_eps} 集"], 75)
        return final_episodes, source_ranges

    async def _select_source_ranges(self, *, explicit_ranges: list, planned_ranges: list, minimum_count: int) -> list:
        minimum = max(minimum_count, 1)
        if explicit_ranges and len(explicit_ranges) >= minimum:
            await self.log(["[episodes] 使用剧本显式第X集边界，已按目标最低集数规则保留原文分集"], 55)
            return explicit_ranges
        if planned_ranges:
            await self.log(["[episodes] 使用综合规划返回的 block 范围，已满足目标最低集数"], 55)
            return planned_ranges

        grouped = _group_ranges(explicit_ranges, minimum)
        source_ranges = grouped or fallback_even_ranges(self.blocks, minimum)
        if explicit_ranges:
            await self.log(["[episodes] 原文显式分集少于目标最低集数，已按全文重新兜底切分"], 55)
        else:
            await self.log(["[warn] 分集范围不足最低集数，已使用后端原文块兜底切分"], 55)
        return source_ranges

    @staticmethod
    def _calc_duration(word_count: int, llm_duration: int, min_duration: int) -> int:
        formula = word_count / 3.5 * 1.4 if word_count > 0 else min_duration
        lo, hi = formula * 0.5, formula * 1.5
        chosen = llm_duration if (lo <= llm_duration <= hi and llm_duration > 0) else formula
        result_sec = max(chosen, min_duration or 30)
        return int(math.ceil(result_sec / 5) * 5)
