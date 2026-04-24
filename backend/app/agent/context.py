"""
Assemble system prompt for the agent based on target type and current state.
System prompt = base instructions + series_prompt + target state snapshot.
"""
from __future__ import annotations

BASE_INSTRUCTIONS = """你是 AI 短剧制作助手，负责帮助用户修改和重新生成短剧的资产图片、分镜图片及视频片段。

工作规则：
1. 所有生成操作（图片/视频）都是异步的，调用工具后会立即返回 task_record_id，不需要等待生成完成。
2. 生成任务启动后，告诉用户任务已启动，前端会自动刷新显示最新结果。
3. 如果用户要求修改后重新生成，先调用 update_*_prompt 更新提示词，再调用 generate_* 触发生成。
4. 一次只响应用户的一个明确意图，不要猜测用户的后续意图主动多步操作。
5. 用简洁的中文回复，不要过度解释。"""


async def build_system_prompt(
    target_type: str,
    target_id: str,
    project_id: str,
) -> str:
    """Assemble system prompt = base + series_prompt + target snapshot."""
    from beanie import PydanticObjectId
    from app.models.project import Project

    parts = [BASE_INSTRUCTIONS]

    # Inject series_prompt for style consistency
    try:
        project = await Project.get(PydanticObjectId(project_id))
        if project and project.series_prompt:
            parts.append(f"\n\n【全剧风格设定】\n{project.series_prompt}")
    except Exception:
        pass

    # Inject target-specific snapshot
    snapshot = await _build_snapshot(target_type, target_id)
    if snapshot:
        parts.append(f"\n\n【当前操作对象】\n{snapshot}")

    return "\n".join(parts)


async def _build_snapshot(target_type: str, target_id: str) -> str:
    """Return a text snapshot of the target object for LLM context."""
    from beanie import PydanticObjectId

    try:
        if target_type == "asset":
            from app.models.asset import Asset
            asset = await Asset.get(PydanticObjectId(target_id))
            if not asset:
                return ""
            return (
                f"类型：资产（{asset.asset_type}）\n"
                f"名称：{asset.name}\n"
                f"当前提示词：{asset.prompt}\n"
                f"当前状态：{asset.status}\n"
                f"已有版本数：{len(asset.versions)}"
            )

        if target_type in ("shot_image", "shot_video"):
            from app.models.shot import Shot
            shot = await Shot.get(PydanticObjectId(target_id))
            if not shot:
                return ""
            assets_str = ", ".join(b.asset_name for b in shot.required_assets) or "无"
            return (
                f"类型：分镜（{target_type}）\n"
                f"镜头编号：{shot.shot_code}\n"
                f"场景描述：{shot.description}\n"
                f"当前提示词：{shot.prompt}\n"
                f"绑定资产：{assets_str}\n"
                f"当前状态：{shot.state}\n"
                f"有无剧照：{'是' if shot.image_url else '否'}\n"
                f"有无视频：{'是' if shot.video_url else '否'}"
            )

        if target_type == "episode":
            from app.models.episode import Episode
            ep = await Episode.get(PydanticObjectId(target_id))
            if not ep:
                return ""
            return (
                f"类型：分集\n"
                f"第 {ep.number} 集：{ep.title}\n"
                f"简介：{ep.summary}\n"
                f"当前步骤：{ep.current_step}"
            )
    except Exception:
        pass

    return ""
