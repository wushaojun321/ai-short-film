"""Task status router — Phase 1 stub. Full implementation in Phase 2."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from app.models.task_record import TaskRecord

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: PydanticObjectId):
    record = await TaskRecord.get(task_id)
    if not record:
        raise HTTPException(404, "Task not found")
    return record


@router.get("")
async def list_tasks(project_id: str | None = None, limit: int = 50):
    query = TaskRecord.find()
    if project_id:
        query = TaskRecord.find(TaskRecord.project_id == PydanticObjectId(project_id))
    return await query.sort("-created_at").limit(limit).to_list()
