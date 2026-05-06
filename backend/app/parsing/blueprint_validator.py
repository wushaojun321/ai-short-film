from __future__ import annotations

from dataclasses import dataclass, field

from app.parsing.range_utils import extract_minimum_ranges_from_episode_plan
from app.tasks.llm_tasks import _as_dict, _as_list


@dataclass
class BlueprintValidationResult:
    plan: dict
    planned_ranges: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BlueprintSchemaValidator:
    """Validate the LLM blueprint enough for deterministic builders to run."""

    def validate(self, plan: dict, blocks: list, minimum_count: int) -> BlueprintValidationResult:
        if not isinstance(plan, dict):
            plan = {}

        warnings: list[str] = []
        series = _as_dict(plan.get("series"))
        if not series:
            warnings.append("蓝图缺少 series 行，已使用项目默认风格兜底")

        episodes = _as_list(plan.get("episodes"))
        if not episodes:
            warnings.append("蓝图缺少 episode 行，将使用后端原文边界兜底")

        planned_ranges = extract_minimum_ranges_from_episode_plan(episodes, blocks, minimum_count) if episodes else []
        if episodes and not planned_ranges:
            warnings.append("episode block 范围不足最低集数或不可用，将使用原文边界兜底")

        registry = _as_dict(plan.get("asset_registry"))
        if not registry:
            warnings.append("蓝图缺少 asset_registry，将使用分集需求或原文索引兜底")

        plan.setdefault("continuity_report", {"issues": [], "warnings": [], "status": "needs_review"})
        continuity_report = _as_dict(plan.get("continuity_report"))
        report_warnings = continuity_report.get("warnings")
        if isinstance(report_warnings, list):
            report_warnings.extend(warnings)
        else:
            continuity_report["warnings"] = warnings
        continuity_report.setdefault("issues", [])
        continuity_report.setdefault("status", "needs_review")
        plan["continuity_report"] = continuity_report

        return BlueprintValidationResult(plan=plan, planned_ranges=planned_ranges, warnings=warnings)
