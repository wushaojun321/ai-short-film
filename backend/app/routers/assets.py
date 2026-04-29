from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from app.models.project import Project
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services import asset_service
from app.deps import get_current_user

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"], dependencies=[Depends(get_current_user)])


async def _get_project(project_id: PydanticObjectId) -> Project:
    project = await Project.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("")
async def list_assets(project_id: PydanticObjectId):
    await _get_project(project_id)
    return await asset_service.list_assets(project_id)


@router.post("", status_code=201)
async def create_asset(project_id: PydanticObjectId, data: AssetCreate):
    project = await _get_project(project_id)
    return await asset_service.create_asset(project, data)


@router.get("/{asset_id}")
async def get_asset(project_id: PydanticObjectId, asset_id: PydanticObjectId):
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


@router.patch("/{asset_id}")
async def update_asset(
    project_id: PydanticObjectId, asset_id: PydanticObjectId, data: AssetUpdate
):
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return await asset_service.update_asset(asset, data)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(project_id: PydanticObjectId, asset_id: PydanticObjectId):
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    from app.models.asset import AssetStatus
    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        raise HTTPException(409, "资产正在生成中，无法删除，请等待生成完成后再操作")
    await asset_service.delete_asset(asset)


@router.post("/{asset_id}/confirm")
async def confirm_asset(project_id: PydanticObjectId, asset_id: PydanticObjectId):
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return await asset_service.confirm_asset(asset)


@router.post("/{asset_id}/regen")
async def request_regen(project_id: PydanticObjectId, asset_id: PydanticObjectId):
    """Mark asset for regeneration and immediately enqueue Celery image task."""
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")

    from app.models.asset import AssetStatus
    from app.models.task_record import TaskRecord, TaskStatus
    from app.tasks.image_tasks import gen_asset_image_task
    from datetime import datetime

    await asset.set({"status": AssetStatus.queued})
    task = gen_asset_image_task.delay(str(asset_id))

    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_asset_image",
        project_id=project_id,
        target_id=asset_id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"status": AssetStatus.queued, "task_id": task.id, "record_id": str(record.id)}
