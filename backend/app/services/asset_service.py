from beanie import PydanticObjectId
from app.models.asset import Asset, AssetStatus
from app.models.project import Project
from app.schemas.asset import AssetCreate, AssetUpdate


async def create_asset(project: Project, data: AssetCreate) -> Asset:
    asset = Asset(project_id=project.id, **data.model_dump())
    await asset.insert()
    return asset


async def get_asset(asset_id: PydanticObjectId) -> Asset | None:
    return await Asset.get(asset_id)


async def list_assets(project_id: PydanticObjectId) -> list[Asset]:
    return await Asset.find(Asset.project_id == project_id).to_list()


async def update_asset(asset: Asset, data: AssetUpdate) -> Asset:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await asset.set(update_data)
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
    else:
        updates["preview_url"] = selected.url
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
