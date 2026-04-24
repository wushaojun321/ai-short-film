"""
项目初始化阶段工具：供步骤3（分集+资产确认）Agent 调用。

这些工具直接操作 DB，不触发生图任务。
用于用户在确认分集/资产前通过多轮对话进行调整。
"""
from __future__ import annotations
from datetime import datetime

# ── OpenAI function schemas ────────────────────────────────────────────────────

CREATE_ASSET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_asset",
        "description": (
            "新增一个资产（人物/场景/道具）到项目中。"
            "资产记录立即创建，图片将在用户确认后的步骤4统一生成。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目的 MongoDB ID"},
                "name": {"type": "string", "description": "资产名称，如「李白」、「御书房」"},
                "asset_type": {
                    "type": "string",
                    "enum": ["character", "scene", "prop"],
                    "description": "资产类型：character（人物）/ scene（场景）/ prop（道具）",
                },
                "prompt": {
                    "type": "string",
                    "description": "Seedream 图像生成提示词，按规范详细描述外貌/场景/道具",
                },
            },
            "required": ["project_id", "name", "asset_type", "prompt"],
        },
    },
}

DELETE_ASSET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_asset",
        "description": "删除一个资产。仅在用户明确要求删除某资产时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "资产的 MongoDB ID"},
            },
            "required": ["asset_id"],
        },
    },
}

UPDATE_ASSET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_asset",
        "description": (
            "修改资产的名称或图像生成提示词（不触发重新生成）。"
            "仅修改指定字段，未传的字段保持不变。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "资产的 MongoDB ID"},
                "name": {"type": "string", "description": "新的资产名称（可选）"},
                "prompt": {"type": "string", "description": "新的 Seedream 图像提示词（可选）"},
            },
            "required": ["asset_id"],
        },
    },
}

UPDATE_EPISODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_episode",
        "description": "修改某一集的标题或简介。",
        "parameters": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "string", "description": "分集的 MongoDB ID"},
                "title": {"type": "string", "description": "新的集标题（可选）"},
                "summary": {"type": "string", "description": "新的剧情简介（可选）"},
            },
            "required": ["episode_id"],
        },
    },
}

# 该 target_type 可用的所有 tool schemas
PROJECT_INIT_TOOLS = [
    CREATE_ASSET_SCHEMA,
    DELETE_ASSET_SCHEMA,
    UPDATE_ASSET_SCHEMA,
    UPDATE_EPISODE_SCHEMA,
]


# ── Tool implementations ───────────────────────────────────────────────────────

async def create_asset(project_id: str, name: str, asset_type: str, prompt: str) -> dict:
    """Create a new asset record (no image generation)."""
    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetType, AssetStatus
    from app.models.project import Project

    project = await Project.get(PydanticObjectId(project_id))
    if not project:
        return {"error": f"Project {project_id} not found"}

    try:
        at = AssetType(asset_type)
    except ValueError:
        return {"error": f"Invalid asset_type: {asset_type}，必须是 character/scene/prop"}

    asset = Asset(
        project_id=project.id,
        name=name,
        asset_type=at,
        prompt=prompt,
        status=AssetStatus.pending,
    )
    await asset.insert()
    return {
        "asset_id": str(asset.id),
        "name": asset.name,
        "asset_type": asset_type,
        "message": f"资产「{name}」已创建，图片将在确认后统一生成。",
    }


async def delete_asset(asset_id: str) -> dict:
    """Delete an asset record."""
    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetStatus

    asset = await Asset.get(PydanticObjectId(asset_id))
    if not asset:
        return {"error": f"Asset {asset_id} not found"}
    if asset.status in (AssetStatus.queued, AssetStatus.generating):
        return {"error": f"资产「{asset.name}」正在生成中，无法删除"}

    name = asset.name
    await asset.delete()
    return {"asset_id": asset_id, "message": f"资产「{name}」已删除。"}


async def update_asset(asset_id: str, name: str | None = None, prompt: str | None = None) -> dict:
    """Update asset name and/or prompt without triggering image generation."""
    from beanie import PydanticObjectId
    from app.models.asset import Asset

    asset = await Asset.get(PydanticObjectId(asset_id))
    if not asset:
        return {"error": f"Asset {asset_id} not found"}

    updates: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        updates["name"] = name
    if prompt is not None:
        updates["prompt"] = prompt

    if len(updates) > 1:  # more than just updated_at
        await asset.set(updates)

    return {
        "asset_id": asset_id,
        "name": updates.get("name", asset.name),
        "message": f"资产「{asset.name}」已更新。",
    }


async def update_episode(episode_id: str, title: str | None = None, summary: str | None = None) -> dict:
    """Update episode title and/or summary."""
    from beanie import PydanticObjectId
    from app.models.episode import Episode

    episode = await Episode.get(PydanticObjectId(episode_id))
    if not episode:
        return {"error": f"Episode {episode_id} not found"}

    updates: dict = {}
    if title is not None:
        updates["title"] = title
    if summary is not None:
        updates["summary"] = summary

    if updates:
        await episode.set(updates)

    return {
        "episode_id": episode_id,
        "number": episode.number,
        "title": updates.get("title", episode.title),
        "message": f"第 {episode.number} 集已更新。",
    }
