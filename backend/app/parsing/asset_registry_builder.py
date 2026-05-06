from __future__ import annotations

from typing import Awaitable, Callable

from app.models.asset import Asset, AssetStatus, AssetType
from app.models.production_blueprint import ProductionBlueprint, ProductionBlueprintStatus
from app.tasks.llm_tasks import (
    _as_str_list,
    _asset_inventory_from_blueprint,
    _assets_from_production_plan,
    _registry_from_plan,
)
from app.utils.script_indexer import SCRIPT_INDEX_VERSION

LogFn = Callable[[list[str], int], Awaitable[None]]


class AssetRegistryBuilder:
    """Derive normalized asset docs from the production blueprint."""

    def __init__(self, project, blocks: list, log: LogFn):
        self.project = project
        self.blocks = blocks
        self.log = log

    async def build_blueprint_and_assets(
        self,
        *,
        plan: dict,
        blueprint_episodes: list[dict],
        series: dict,
        continuity_report: dict,
    ) -> tuple[ProductionBlueprint, dict]:
        asset_registry = _registry_from_plan(plan)
        character_bible, character_variants, scene_bible, prop_bible = _assets_from_production_plan(
            asset_registry,
            blueprint_episodes,
            self.blocks,
        )
        assets_data = _asset_inventory_from_blueprint(character_variants, scene_bible, prop_bible)

        await self.log([
            (
                "[blueprint] 资产注册表归并完成："
                f"{len(character_bible)} 个角色包、{len(character_variants)} 个人物阶段、"
                f"{len(scene_bible)} 个场景阶段、{len(prop_bible)} 个道具阶段"
            )
        ], 90)

        blueprint = ProductionBlueprint(
            project_id=self.project.id,
            script_index_version=SCRIPT_INDEX_VERSION,
            series=series,
            episodes=blueprint_episodes,
            character_bible=character_bible,
            scene_bible=scene_bible,
            prop_bible=prop_bible,
            character_variants=character_variants,
            scene_variants=scene_bible,
            prop_variants=prop_bible,
            asset_inventory=assets_data,
            continuity_report=continuity_report,
            status=(
                ProductionBlueprintStatus.validated
                if continuity_report.get("status") == "validated"
                else ProductionBlueprintStatus.needs_review
            ),
        )
        await blueprint.insert()
        await self.log(["[blueprint] 制作蓝图已写入，开始派生资产卡片"], 92)

        await self.create_asset_records(assets_data)
        return blueprint, assets_data

    async def create_asset_records(self, assets_data: dict) -> dict[str, int]:
        if not isinstance(assets_data, dict):
            assets_data = {}
        type_map = {
            "characters": AssetType.character,
            "scenes": AssetType.scene,
            "props": AssetType.prop,
        }
        asset_counts: dict[str, int] = {}
        for key, asset_type in type_map.items():
            count = 0
            for item in assets_data.get(key, []):
                if not isinstance(item, dict):
                    continue
                existing_asset = await Asset.find_one(
                    Asset.project_id == self.project.id,
                    Asset.name == item.get("name", ""),
                )
                if existing_asset:
                    continue

                asset_prompt = item.get("prompt") or item.get("description", "")
                asset = Asset(
                    project_id=self.project.id,
                    name=item.get("name", ""),
                    asset_type=asset_type,
                    prompt=asset_prompt,
                    voice_profile=item.get("voice_profile", "") if asset_type == AssetType.character else "",
                    character_name=item.get("character_name", "") if asset_type == AssetType.character else "",
                    asset_package=(
                        item.get("asset_package") or item.get("character_name") or item.get("name", "")
                    ) if asset_type == AssetType.character else "",
                    face_identity=item.get("face_identity", "") if asset_type == AssetType.character else "",
                    distinctive_traits=_as_str_list(item.get("distinctive_traits")) if asset_type == AssetType.character else [],
                    avoid_similar_to=_as_str_list(item.get("avoid_similar_to")) if asset_type == AssetType.character else [],
                    look_lock=item.get("look_lock", "") if asset_type == AssetType.character else "",
                    scene_scope=item.get("scene_scope", "") if asset_type == AssetType.character else "",
                    appearance_stage=item.get("appearance_stage", "") if asset_type == AssetType.character else "",
                    view_requirements=item.get("view_requirements", "面部特写、全身形象、侧面视角") if asset_type == AssetType.character else "",
                    status=AssetStatus.pending,
                )
                await asset.insert()
                count += 1
            if count:
                asset_counts[key] = count

        asset_summary = "、".join(f"{v} 个{k}" for k, v in asset_counts.items()) if asset_counts else "无新资产"
        await self.log([f"[assets] 资产记录已创建：{asset_summary}（图片待步骤4生成）"], 95)
        return asset_counts
