"""Episode-level tools: regenerate storyboard script with user feedback."""
from __future__ import annotations
from datetime import datetime


# ── OpenAI function schema ─────────────────────────────────────────────────────

GEN_SHOT_SCRIPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "gen_shot_script",
        "description": (
            "重新生成本集的分镜脚本。根据用户的修改意见，AI 将重新拆分本集剧本为逐镜分镜。"
            "任务异步执行，立即返回 task_record_id，前端轮询状态。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "string", "description": "集的 MongoDB ID"},
                "feedback": {
                    "type": "string",
                    "description": "用户的修改意见，会传入分镜生成提示词中",
                },
                "max_shot_duration": {
                    "type": "integer",
                    "description": "每个镜头最大时长（秒），默认 10",
                    "default": 10,
                },
            },
            "required": ["episode_id", "feedback"],
        },
    },
}

EPISODE_TOOLS = [GEN_SHOT_SCRIPT_SCHEMA]


# ── Tool implementation ────────────────────────────────────────────────────────

async def gen_shot_script(episode_id: str, feedback: str, max_shot_duration: int = 5) -> dict:
    """Dispatch gen_shot_script_task with feedback, return task_record_id."""
    from beanie import PydanticObjectId
    from app.models.episode import Episode
    from app.models.task_record import TaskRecord, TaskStatus
    from app.tasks.llm_tasks import gen_shot_script_task

    episode = await Episode.get(PydanticObjectId(episode_id))
    if not episode:
        return {"error": f"Episode {episode_id} not found"}

    celery_task = gen_shot_script_task.delay(episode_id, max_shot_duration, feedback)

    record = TaskRecord(
        celery_task_id=celery_task.id,
        task_type="gen_shot_script",
        project_id=episode.project_id,
        episode_id=episode.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()

    return {
        "task_record_id": str(record.id),
        "episode_id": episode_id,
        "status": "started",
        "message": f"《{episode.title}》分镜脚本正在重新生成，请稍候…",
    }
