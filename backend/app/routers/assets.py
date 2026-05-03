from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from app.models.project import Project
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services import asset_service
from app.deps import get_current_user, get_owned_project

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_assets(project: Project = Depends(get_owned_project)):
    return await asset_service.list_assets(project.id)


@router.post("", status_code=201)
async def create_asset(data: AssetCreate, project: Project = Depends(get_owned_project)):
    return await asset_service.create_asset(project, data)


@router.get("/{asset_id}")
async def get_asset(asset_id: PydanticObjectId, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")
    return asset


@router.patch("/{asset_id}")
async def update_asset(asset_id: PydanticObjectId, data: AssetUpdate, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")
    return await asset_service.update_asset(asset, data)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(asset_id: PydanticObjectId, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")
    from app.models.asset import AssetStatus
    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        raise HTTPException(409, "资产正在生成中，无法删除，请等待生成完成后再操作")
    await asset_service.delete_asset(asset)


@router.post("/{asset_id}/confirm")
async def confirm_asset(asset_id: PydanticObjectId, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")
    return await asset_service.confirm_asset(asset)


@router.post("/{asset_id}/versions/{version}/restore")
async def restore_asset_version(asset_id: PydanticObjectId, version: str, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")
    try:
        return await asset_service.restore_asset_version(asset, version)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{asset_id}/regen")
async def request_regen(asset_id: PydanticObjectId, project: Project = Depends(get_owned_project)):
    asset = await asset_service.get_asset(asset_id)
    if not asset or asset.project_id != project.id:
        raise HTTPException(404, "Asset not found")

    from app.models.asset import AssetStatus
    from app.models.task_record import TaskRecord, TaskStatus
    from app.tasks.image_tasks import gen_asset_image_task
    from datetime import datetime

    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        return {
            "status": asset.status,
            "task_id": asset.generation_task_id,
            "record_id": None,
            "skipped": True,
            "reason": "already queued or generating",
        }

    await asset.set({"status": AssetStatus.queued})
    task = gen_asset_image_task.delay(str(asset_id))

    record = TaskRecord(
        celery_task_id=task.id,
        task_type="gen_asset_image",
        project_id=project.id,
        target_id=asset_id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return {"status": AssetStatus.queued, "task_id": task.id, "record_id": str(record.id)}
