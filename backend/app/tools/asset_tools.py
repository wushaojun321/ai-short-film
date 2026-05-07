"""Asset atomic tools: generate / regen asset image, update prompt."""
from __future__ import annotations
from datetime import datetime


# ── OpenAI function schemas ────────────────────────────────────────────────────

GENERATE_ASSET_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_asset_image",
        "description": (
            "为角色/场景/道具资产生成或重新生成参考图片。"
            "任务异步执行，立即返回 task_record_id，前端轮询资产状态获取结果。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "资产的 MongoDB ID"},
                "prompt_override": {
                    "type": "string",
                    "description": "可选，覆盖资产原有生成提示词，留空则沿用原提示词",
                },
            },
            "required": ["asset_id"],
        },
    },
}

UPDATE_ASSET_PROMPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_asset_prompt",
        "description": "修改资产的生成提示词（不触发重新生成）。",
        "parameters": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "资产的 MongoDB ID"},
                "new_prompt": {"type": "string", "description": "新的生成提示词"},
            },
            "required": ["asset_id", "new_prompt"],
        },
    },
}

# 该 target_type 可用的所有 tool schemas
ASSET_TOOLS = [GENERATE_ASSET_IMAGE_SCHEMA, UPDATE_ASSET_PROMPT_SCHEMA]


# ── Tool implementations ───────────────────────────────────────────────────────

async def generate_asset_image(asset_id: str, prompt_override: str | None = None) -> dict:
    """
    Dispatch gen_asset_image_task asynchronously.
    Sets asset.status = generating immediately, returns task_record_id.
    """
    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetStatus
    from app.models.task_record import TaskRecord, TaskStatus
    from app.services.project_task_cleanup import get_active_parse_record
    from app.tasks.image_tasks import gen_asset_image_task

    asset = await Asset.get(PydanticObjectId(asset_id))
    if not asset:
        return {"error": f"Asset {asset_id} not found"}
    if await get_active_parse_record(asset.project_id):
        return {"error": "项目正在解析剧本，请等待解析完成后再生成资产图片。"}

    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        return {
            "asset_id": asset_id,
            "asset_name": asset.name,
            "status": "skipped",
            "task_id": asset.generation_task_id,
            "message": f"资产「{asset.name}」已有图片生成任务在进行中，已跳过重复提交。",
        }

    if prompt_override:
        await asset.set({"prompt": prompt_override})

    # Dispatch Celery task
    celery_task = gen_asset_image_task.delay(asset_id)

    # Create task record
    record = TaskRecord(
        celery_task_id=celery_task.id,
        task_type="gen_asset_image",
        project_id=asset.project_id,
        target_id=asset.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()

    # Mark queued immediately; worker will change to generating when it starts
    await asset.set({
        "status": AssetStatus.queued,
        "generation_task_id": celery_task.id,
    })

    return {
        "task_record_id": str(record.id),
        "asset_id": asset_id,
        "asset_name": asset.name,
        "status": "started",
        "message": f"资产「{asset.name}」图片生成任务已启动，前端轮询状态获取结果。",
    }


async def update_asset_prompt(asset_id: str, new_prompt: str) -> dict:
    """Update asset prompt without regenerating."""
    from beanie import PydanticObjectId
    from app.models.asset import Asset

    asset = await Asset.get(PydanticObjectId(asset_id))
    if not asset:
        return {"error": f"Asset {asset_id} not found"}

    await asset.set({"prompt": new_prompt, "updated_at": datetime.utcnow()})
    return {
        "asset_id": asset_id,
        "asset_name": asset.name,
        "new_prompt": new_prompt,
        "message": f"资产「{asset.name}」提示词已更新。如需重新生成图片，请调用 generate_asset_image。",
    }
