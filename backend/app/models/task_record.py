from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class TaskStatus(str, Enum):
    pending   = "pending"
    running   = "running"
    success   = "success"
    failed    = "failed"
    cancelled = "cancelled"


class TaskRecord(Document):
    celery_task_id: str
    task_type: str
    project_id: Optional[PydanticObjectId] = None
    episode_id: Optional[PydanticObjectId] = None
    target_id: Optional[PydanticObjectId] = None
    status: TaskStatus = TaskStatus.pending
    progress: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "task_records"
        indexes = [
            "celery_task_id",
            "target_id",
            [("project_id", 1), ("status", 1)],
        ]
