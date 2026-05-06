from __future__ import annotations

from beanie import PydanticObjectId

from app.models.asset import Asset
from app.models.episode import Episode
from app.models.production_blueprint import ProductionBlueprint
from app.models.project import Project
from app.models.shot import Shot
from app.models.task_record import TaskRecord
from app.parsing.asset_registry_builder import AssetRegistryBuilder
from app.parsing.blueprint_planner import ProductionBlueprintPlanner
from app.parsing.blueprint_validator import BlueprintSchemaValidator
from app.parsing.context_pack import ScriptContextPackBuilder
from app.parsing.continuity_seed_builder import ContinuitySeedBuilder
from app.parsing.episode_builder import EpisodeMaterialBuilder
from app.parsing.parse_report_builder import ParseReportBuilder
from app.tasks.base import finish_task_record
from app.tasks.llm_tasks import _as_dict


class ParseOrchestrator:
    """Orchestrate script parsing while keeping module responsibilities separate."""

    def __init__(self, celery_id: str, project_id: str):
        self.celery_id = celery_id
        self.project_id = project_id
        self.record = None

    async def run(self) -> dict:
        try:
            project = await Project.get(PydanticObjectId(self.project_id))
            if not project or not project.script_text:
                raise ValueError("Project or script not found")

            self.record = await TaskRecord.find_one(TaskRecord.celery_task_id == self.celery_id)
            await self.log([
                f"[init] 项目加载完成：{project.title}",
                f"[init] 剧本长度：{len(project.script_text or '')} 字，目标最低集数：{project.target_episode_count}",
            ], 10)

            await self._clear_existing_outputs(project)

            context_pack = await ScriptContextPackBuilder().build(project)
            await self.log([
                f"[index] 原文索引完成：{len(context_pack.blocks)} 个块，显式分集边界 {len(context_pack.explicit_ranges)} 个",
            ], 25)

            plan = await self._build_blueprint_plan(project, context_pack)
            validation = BlueprintSchemaValidator().validate(
                plan,
                context_pack.blocks,
                context_pack.minimum_count,
            )
            for warning in validation.warnings:
                await self.log([f"[blueprint][warn] {warning}"], 50)

            series = self._normalize_series(project, validation.plan)
            await project.set({"series_prompt": series["series_prompt"]})
            await self.log(["[plan] 综合制作规划完成，开始按原文块回填分集"], 50)

            final_episodes, _ = await EpisodeMaterialBuilder(project, context_pack.blocks, self.log).build(
                plan=validation.plan,
                planned_ranges=validation.planned_ranges,
                explicit_ranges=context_pack.explicit_ranges,
                minimum_count=context_pack.minimum_count,
                continuity_notes=series.get("continuity_notes", ""),
            )

            blueprint_episodes = self._blueprint_episodes(final_episodes)
            await self.log(["[blueprint] 分集蓝图已生成，开始后端归并资产注册表"], 78)

            continuity_report = ContinuitySeedBuilder().build(validation.plan)
            blueprint, assets_data = await AssetRegistryBuilder(project, context_pack.blocks, self.log).build_blueprint_and_assets(
                plan=validation.plan,
                blueprint_episodes=blueprint_episodes,
                series=series,
                continuity_report=continuity_report,
            )

            await self.log(["✓ 剧本解析完成，请在步骤3确认分集与资产后继续"], 100)
            result = ParseReportBuilder().build(
                episodes=final_episodes,
                assets=assets_data,
                series=series,
                blueprint_id=str(blueprint.id),
                continuity_report=continuity_report,
            )
            await finish_task_record(self.celery_id, result=result)
            return result
        except Exception as exc:
            if self.record:
                await self.record.set({"logs": (self.record.logs or []) + [f"[error] {exc}"]})
            await finish_task_record(self.celery_id, error=str(exc))
            raise

    async def log(self, msgs: list[str], progress: int):
        if self.record:
            current = self.record.logs or []
            await self.record.set({"logs": current + msgs, "progress": progress})

    async def _clear_existing_outputs(self, project: Project):
        await Shot.find(Shot.project_id == project.id).delete()
        await Episode.find(Episode.project_id == project.id).delete()
        await Asset.find(Asset.project_id == project.id).delete()
        await ProductionBlueprint.find(ProductionBlueprint.project_id == project.id).delete()

    async def _build_blueprint_plan(self, project: Project, context_pack) -> dict:
        try:
            plan, _ = await ProductionBlueprintPlanner(project, context_pack, self.log).plan()
            return plan
        except Exception as exc:
            await self.log([f"[warn] 综合制作规划失败，使用后端原文边界兜底：{exc}"], 45)
            return {}

    @staticmethod
    def _normalize_series(project: Project, plan: dict) -> dict:
        series = _as_dict(plan.get("series"))
        if not series:
            series = {
                "series_prompt": plan.get("series_prompt") or "",
                "main_storyline": plan.get("main_storyline") or "",
                "continuity_notes": plan.get("continuity_notes") or "",
            }
        series_prompt = series.get("series_prompt") or project.series_prompt or (
            "写实电影质感，真实摄影基础，真实影视布光，真实材质，电影级调色，克制真实氛围"
        )
        series["series_prompt"] = series_prompt
        series["continuity_notes"] = series.get("continuity_notes") or plan.get("continuity_notes", "")
        return series

    @staticmethod
    def _blueprint_episodes(final_episodes: list[dict]) -> list[dict]:
        return [
            {
                "number": ep["number"],
                "title": ep["title"],
                "summary": ep["summary"],
                "word_count": ep["word_count"],
                "estimated_duration": ep["estimated_duration"],
                "source_start_line": ep["source_start_line"],
                "source_end_line": ep["source_end_line"],
                "source_integrity": ep["source_integrity"],
                "source_block_ranges": ep["source_block_ranges"],
                "dialogue_count": ep["dialogue_count"],
                "beats": ep.get("beats", []),
                "emotion_curve": ep.get("emotion_curve", ""),
                "ending_hook": ep.get("ending_hook", ""),
                "asset_requirements": ep.get("asset_requirements", {}),
            }
            for ep in final_episodes
        ]
