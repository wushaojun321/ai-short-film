from __future__ import annotations

from app.tasks.llm_tasks import _as_dict, _as_list


class ContinuitySeedBuilder:
    """Normalize continuity output from the blueprint into a stable report."""

    def build(self, plan: dict) -> dict:
        report = _as_dict(plan.get("continuity_report"))
        if not report:
            report = {"issues": [], "warnings": [], "status": "needs_review"}
        report.setdefault("status", "needs_review")
        report.setdefault("issues", [])
        report.setdefault("warnings", [])

        ignored_assets = _as_list(plan.get("ignored_assets"))
        if ignored_assets:
            report["ignored_assets"] = ignored_assets
        return report
