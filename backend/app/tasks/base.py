"""Base task utilities: async runner, DB init, TaskRecord management."""
from __future__ import annotations
import asyncio
from datetime import datetime
from app.celery_app import celery_app


def run_async(coro):
    """Run an async coroutine in a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def ensure_db():
    """Initialize Beanie if not already initialized."""
    from beanie import Document
    from app.database import init_db
    # Check if already initialized by seeing if the registry exists
    try:
        from beanie.odm.utils.init import IS_INITIALIZED
        if not IS_INITIALIZED:
            await init_db()
    except ImportError:
        await init_db()


async def create_task_record(
    celery_task_id: str,
    task_type: str,
    project_id=None,
    episode_id=None,
    target_id=None,
) -> str:
    """Create a TaskRecord and return its mongo id as string."""
    from app.models.task_record import TaskRecord, TaskStatus
    from datetime import datetime
    record = TaskRecord(
        celery_task_id=celery_task_id,
        task_type=task_type,
        project_id=project_id,
        episode_id=episode_id,
        target_id=target_id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()
    return str(record.id)


async def finish_task_record(celery_task_id: str, result: dict | None = None, error: str | None = None):
    from app.models.task_record import TaskRecord, TaskStatus
    record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_task_id)
    if record:
        status = TaskStatus.failed if error else TaskStatus.success
        await record.set({
            "status": status,
            "result": result,
            "error": error,
            "progress": 100 if not error else record.progress,
            "finished_at": datetime.utcnow(),
        })
