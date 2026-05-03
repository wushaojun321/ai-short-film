from beanie import PydanticObjectId
from app.models.asset import Asset, AssetStatus
from app.models.project import Project
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services.asset_prompt_builder import build_asset_submitted_prompts
from datetime import datetime


PROMPT_SOURCE_FIELDS = {
    "name",
    "prompt",
    "character_name",
    "asset_package",
    "face_identity",
    "scene_scope",
    "appearance_stage",
    "view_requirements",
}


def _asset_has_image(asset: Asset) -> bool:
    return bool(asset.preview_url or any((asset.view_urls or {}).values()))


def _asset_is_running(asset: Asset) -> bool:
    return asset.status in (AssetStatus.queued, AssetStatus.generating)


async def _refresh_submitted_prompts(
    asset: Asset,
    all_assets: list[Asset] | None = None,
    *,
    force: bool = False,
) -> Asset:
    if _asset_is_running(asset):
        return asset
    if not force and _asset_has_image(asset) and asset.submitted_prompt:
        return asset

    all_assets = all_assets or await Asset.find(Asset.project_id == asset.project_id).to_list()
    submitted_prompt, submitted_prompts = build_asset_submitted_prompts(asset, all_assets)
    updates: dict = {}
    if asset.submitted_prompt != submitted_prompt:
        updates["submitted_prompt"] = submitted_prompt
        asset.submitted_prompt = submitted_prompt
    if (asset.submitted_prompts or {}) != submitted_prompts:
        updates["submitted_prompts"] = submitted_prompts
        asset.submitted_prompts = submitted_prompts
    if updates:
        updates["updated_at"] = datetime.utcnow()
        await asset.set(updates)
    return asset


async def _refresh_list_submitted_prompts(assets: list[Asset]) -> list[Asset]:
    if not assets:
        return assets
    for asset in assets:
        if _asset_is_running(asset):
            continue
        if not asset.submitted_prompt or not _asset_has_image(asset):
            await _refresh_submitted_prompts(asset, assets)
    return assets


async def create_asset(project: Project, data: AssetCreate) -> Asset:
    asset = Asset(project_id=project.id, **data.model_dump())
    await asset.insert()
    all_assets = await Asset.find(Asset.project_id == project.id).to_list()
    await _refresh_submitted_prompts(asset, all_assets, force=True)
    return asset


async def get_asset(asset_id: PydanticObjectId) -> Asset | None:
    return await Asset.get(asset_id)


async def list_assets(project_id: PydanticObjectId) -> list[Asset]:
    assets = await Asset.find(Asset.project_id == project_id).to_list()
    return await _refresh_list_submitted_prompts(assets)


async def refresh_asset_submitted_prompts(asset: Asset, *, force: bool = True) -> Asset:
    all_assets = await Asset.find(Asset.project_id == asset.project_id).to_list()
    return await _refresh_submitted_prompts(asset, all_assets, force=force)


async def update_asset(asset: Asset, data: AssetUpdate) -> Asset:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await asset.set(update_data)
        fresh = await Asset.get(asset.id)
        if fresh:
            asset = fresh
        if PROMPT_SOURCE_FIELDS.intersection(update_data):
            all_assets = await Asset.find(Asset.project_id == asset.project_id).to_list()
            await _refresh_submitted_prompts(asset, all_assets, force=True)
    return asset


async def confirm_asset(asset: Asset) -> Asset:
    await asset.set({"status": AssetStatus.approved})
    return asset


async def restore_asset_version(asset: Asset, version: str) -> Asset:
    selected = next((item for item in asset.versions if item.version == version), None)
    if not selected:
        raise ValueError("Asset version not found")

    updates: dict = {
        "status": AssetStatus.pending,
    }
    if not asset.prompt and selected.prompt:
        updates["prompt"] = selected.prompt
    if selected.view_type:
        view_urls = dict(asset.view_urls or {})
        view_urls[selected.view_type] = selected.url
        updates["view_urls"] = view_urls
        provider_view_urls = dict(asset.provider_view_urls or {})
        if selected.provider_url:
            provider_view_urls[selected.view_type] = selected.provider_url
            updates["provider_view_urls"] = provider_view_urls
        submitted_prompts = dict(asset.submitted_prompts or {})
        if selected.prompt:
            submitted_prompts[selected.view_type] = selected.prompt
            updates["submitted_prompts"] = submitted_prompts
            view_labels = {"face": "面部特写", "full_body": "全身正面", "side": "侧面视角"}
            updates["submitted_prompt"] = "\n\n---\n\n".join(
                f"{view_labels.get(key, key)}：\n{prompt}"
                for key, prompt in submitted_prompts.items()
                if prompt
            )
        if selected.view_type == "face" or not asset.preview_url:
            updates["preview_url"] = selected.url
            if selected.provider_url:
                updates["provider_preview_url"] = selected.provider_url
    else:
        updates["preview_url"] = selected.url
        if selected.provider_url:
            updates["provider_preview_url"] = selected.provider_url
        if selected.prompt:
            updates["submitted_prompt"] = selected.prompt
            updates["submitted_prompts"] = {}

    await asset.set(updates)
    return asset


async def mark_regen(asset: Asset) -> Asset:
    await asset.set({"status": AssetStatus.need_regen})
    return asset


async def delete_asset(asset: Asset) -> None:
    await asset.delete()
