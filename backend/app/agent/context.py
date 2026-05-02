"""
Assemble system prompt for the agent based on target type and current state.
System prompt = base instructions + series_prompt + target state snapshot.
"""
from __future__ import annotations

from app.prompts import BASE_INSTRUCTIONS


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
                f"asset_id：{target_id}\n"
                f"名称：{asset.name}\n"
                f"当前提示词：{asset.prompt}\n"
                f"固定音色：{asset.voice_profile or '无'}\n"
                f"角色本名：{asset.character_name or '无'}\n"
                f"适用场景：{asset.scene_scope or '无'}\n"
                f"造型阶段：{asset.appearance_stage or '无'}\n"
                f"视角要求：{asset.view_requirements or '无'}\n"
                f"当前状态：{asset.status}\n"
                f"已有版本数：{len(asset.versions)}"
            )

        if target_type in ("shot_image", "shot_video"):
            from app.models.shot import Shot
            shot = await Shot.get(PydanticObjectId(target_id))
            if not shot:
                return ""
            assets_str = ", ".join(b.asset_name for b in shot.required_assets) or "无"
            video_note = (
                "\n视频生成说明：分镜视频可直接根据分镜脚本、当前提示词和绑定资产生成，不需要先生成分镜剧照。"
                if target_type == "shot_video" else ""
            )
            return (
                f"类型：分镜（{target_type}）\n"
                f"shot_id：{target_id}\n"
                f"镜头编号：{shot.shot_code}\n"
                f"场景描述：{shot.description}\n"
                f"当前提示词：{shot.prompt}\n"
                f"绑定资产：{assets_str}\n"
                f"当前状态：{shot.state}\n"
                f"有无视频：{'是' if shot.video_url else '否'}"
                f"{video_note}"
            )

        if target_type == "episode":
            from app.models.episode import Episode
            ep = await Episode.get(PydanticObjectId(target_id))
            if not ep:
                return ""
            return (
                f"类型：分集\n"
                f"episode_id：{target_id}\n"
                f"第 {ep.number} 集：{ep.title}\n"
                f"简介：{ep.summary}\n"
                f"当前步骤：{ep.current_step}"
            )

        if target_type == "project":
            from app.models.project import Project
            from app.models.episode import Episode
            from app.models.asset import Asset
            project = await Project.get(PydanticObjectId(target_id))
            if not project:
                return ""

            # 加载所有分集
            episodes = await Episode.find(
                Episode.project_id == project.id
            ).sort("number").to_list()
            eps_lines = []
            for ep in episodes:
                eps_lines.append(f"  - 第{ep.number}集（id:{ep.id}）：{ep.title} | {ep.summary[:50]}…" if len(ep.summary) > 50 else f"  - 第{ep.number}集（id:{ep.id}）：{ep.title} | {ep.summary}")

            # 加载所有资产，按类型分组
            assets = await Asset.find(Asset.project_id == project.id).to_list()
            type_map = {"character": "人物", "scene": "场景", "prop": "道具"}
            asset_lines = []
            for asset_type_key, label in type_map.items():
                typed = [a for a in assets if a.asset_type == asset_type_key]
                if typed:
                    asset_lines.append(f"  【{label}】")
                    for a in typed:
                        prompt_text = f"{a.prompt[:80]}…" if len(a.prompt) > 80 else a.prompt
                        voice_text = f" | voice: {a.voice_profile}" if getattr(a, "voice_profile", "") else ""
                        meta_parts = [
                            f"角色:{a.character_name}" if getattr(a, "character_name", "") else "",
                            f"场景:{a.scene_scope}" if getattr(a, "scene_scope", "") else "",
                            f"阶段:{a.appearance_stage}" if getattr(a, "appearance_stage", "") else "",
                        ]
                        meta_text = " | " + "，".join(part for part in meta_parts if part) if any(meta_parts) else ""
                        asset_lines.append(f"    - {a.name}（id:{a.id}）| prompt: {prompt_text}{meta_text}{voice_text}")

            eps_text = "\n".join(eps_lines) if eps_lines else "  （暂无分集）"
            assets_text = "\n".join(asset_lines) if asset_lines else "  （暂无资产）"

            return (
                f"类型：项目（初始化阶段）\n"
                f"project_id：{target_id}\n"
                f"项目名称：{project.title}\n"
                f"当前状态：{project.init_status}\n\n"
                f"【当前分集列表（共{len(episodes)}集）】\n{eps_text}\n\n"
                f"【当前资产列表（共{len(assets)}个）】\n{assets_text}"
            )
    except Exception:
        pass

    return ""
