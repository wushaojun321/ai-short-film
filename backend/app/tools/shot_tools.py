"""Shot atomic tools: generate shot video, update prompt, bind assets."""
from __future__ import annotations
from datetime import datetime


# ── OpenAI function schemas ────────────────────────────────────────────────────

GENERATE_SHOT_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_shot_image",
        "description": (
            "为分镜生成或重新生成剧照图片（9:16竖屏）。"
            "任务异步执行，立即返回 task_record_id。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "string", "description": "分镜的 MongoDB ID"},
                "prompt_override": {
                    "type": "string",
                    "description": "可选，覆盖分镜原有生成提示词",
                },
            },
            "required": ["shot_id"],
        },
    },
}

GENERATE_SHOT_VIDEO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_shot_video",
        "description": (
            "为分镜生成或重新生成视频片段。可直接根据分镜脚本、提示词和绑定资产生成，"
            "不需要先生成分镜剧照；若已有剧照，系统会自动作为可选参考。"
            "任务异步执行，立即返回 task_record_id。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "string", "description": "分镜的 MongoDB ID"},
            },
            "required": ["shot_id"],
        },
    },
}

UPDATE_SHOT_PROMPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_shot_prompt",
        "description": "修改分镜的生成提示词（不触发重新生成）。",
        "parameters": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "string", "description": "分镜的 MongoDB ID"},
                "new_prompt": {"type": "string", "description": "新的生成提示词"},
            },
            "required": ["shot_id", "new_prompt"],
        },
    },
}

BIND_ASSETS_TO_SHOT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bind_assets_to_shot",
        "description": "为分镜绑定资产（角色/场景/道具），影响后续视频生成时的参考图列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "string", "description": "分镜的 MongoDB ID"},
                "asset_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要绑定的资产 MongoDB ID 列表",
                },
            },
            "required": ["shot_id", "asset_ids"],
        },
    },
}

# 旧版分镜剧照 Agent 入口已从制作流程移除，保留实现仅用于兼容历史任务/接口。
SHOT_IMAGE_TOOLS: list[dict] = []
SHOT_VIDEO_TOOLS = [GENERATE_SHOT_VIDEO_SCHEMA, UPDATE_SHOT_PROMPT_SCHEMA, BIND_ASSETS_TO_SHOT_SCHEMA]


# ── Tool implementations ───────────────────────────────────────────────────────

async def generate_shot_image(shot_id: str, prompt_override: str | None = None) -> dict:
    """Dispatch gen_shot_image_task, set shot.state = generating, return task_record_id."""
    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord, TaskStatus
    from app.services.project_task_cleanup import get_active_parse_record
    from app.tasks.image_tasks import gen_shot_image_task

    shot = await Shot.get(PydanticObjectId(shot_id))
    if not shot:
        return {"error": f"Shot {shot_id} not found"}
    if await get_active_parse_record(shot.project_id):
        return {"error": "项目正在解析剧本，请等待解析完成后再生成分镜图片。"}

    if prompt_override:
        await shot.set({"prompt": prompt_override})

    celery_task = gen_shot_image_task.delay(shot_id)

    record = TaskRecord(
        celery_task_id=celery_task.id,
        task_type="gen_shot_image",
        project_id=shot.project_id,
        episode_id=shot.episode_id,
        target_id=shot.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()

    await shot.set({
        "state": ShotState.generating,
        "generation_task_id": celery_task.id,
    })

    return {
        "task_record_id": str(record.id),
        "shot_id": shot_id,
        "shot_code": shot.shot_code,
        "status": "started",
        "message": f"分镜「{shot.shot_code}」图片生成任务已启动。",
    }


async def generate_shot_video(shot_id: str) -> dict:
    """Dispatch gen_shot_video_task, set shot.state = rendering, return task_record_id."""
    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord, TaskStatus
    from app.services.project_task_cleanup import get_active_parse_record
    from app.tasks.video_tasks import gen_shot_video_task

    shot = await Shot.get(PydanticObjectId(shot_id))
    if not shot:
        return {"error": f"Shot {shot_id} not found"}
    if await get_active_parse_record(shot.project_id):
        return {"error": "项目正在解析剧本，请等待解析完成后再生成分镜视频。"}

    celery_task = gen_shot_video_task.delay(shot_id)

    record = TaskRecord(
        celery_task_id=celery_task.id,
        task_type="gen_shot_video",
        project_id=shot.project_id,
        episode_id=shot.episode_id,
        target_id=shot.id,
        status=TaskStatus.running,
        started_at=datetime.utcnow(),
    )
    await record.insert()

    await shot.set({
        "state": ShotState.rendering,
        "generation_task_id": celery_task.id,
    })

    return {
        "task_record_id": str(record.id),
        "shot_id": shot_id,
        "shot_code": shot.shot_code,
        "status": "started",
        "message": f"分镜「{shot.shot_code}」视频生成任务已启动，通常需要 3-10 分钟，前端轮询状态获取结果。",
    }


async def update_shot_prompt(shot_id: str, new_prompt: str) -> dict:
    """Update shot prompt without regenerating."""
    from beanie import PydanticObjectId
    from app.models.shot import Shot

    shot = await Shot.get(PydanticObjectId(shot_id))
    if not shot:
        return {"error": f"Shot {shot_id} not found"}

    await shot.set({"prompt": new_prompt, "updated_at": datetime.utcnow()})
    return {
        "shot_id": shot_id,
        "shot_code": shot.shot_code,
        "new_prompt": new_prompt,
        "message": f"分镜「{shot.shot_code}」提示词已更新。",
    }


async def bind_assets_to_shot(shot_id: str, asset_ids: list[str]) -> dict:
    """Bind assets to a shot for reference image injection during video generation."""
    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotAssetBinding
    from app.models.asset import Asset, AssetType

    shot = await Shot.get(PydanticObjectId(shot_id))
    if not shot:
        return {"error": f"Shot {shot_id} not found"}

    bindings: list[ShotAssetBinding] = []
    bound_names: list[str] = []
    for aid in asset_ids:
        asset = await Asset.get(PydanticObjectId(aid))
        if asset:
            bindings.append(ShotAssetBinding(
                asset_id=asset.id,
                asset_name=asset.name,
                asset_type=asset.asset_type.value,
                role_in_shot={
                    AssetType.character: "main_actor",
                    AssetType.scene: "scene",
                    AssetType.prop: "prop",
                    AssetType.template: "template",
                }.get(asset.asset_type, ""),
                character_name=asset.character_name,
                asset_package=asset.asset_package or asset.character_name,
                appearance_stage=asset.appearance_stage,
                reference_purpose={
                    AssetType.character: "identity",
                    AssetType.scene: "scene_space",
                    AssetType.prop: "prop_detail",
                    AssetType.template: "reference",
                }.get(asset.asset_type, ""),
                required_views=["face", "full_body"] if asset.asset_type == AssetType.character else ["preview"],
                binding_source="manual",
            ))
            bound_names.append(asset.name)

    await shot.set({"required_assets": bindings, "updated_at": datetime.utcnow()})
    return {
        "shot_id": shot_id,
        "shot_code": shot.shot_code,
        "bound_assets": bound_names,
        "message": f"分镜「{shot.shot_code}」已绑定资产：{', '.join(bound_names)}",
    }
