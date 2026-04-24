"""
Tool registry: maps target_type → (available tool schemas, dispatcher).
"""
from __future__ import annotations
from app.models.conversation import ConversationTarget
from app.tools.asset_tools import (
    ASSET_TOOLS,
    generate_asset_image,
    update_asset_prompt,
)
from app.tools.shot_tools import (
    SHOT_IMAGE_TOOLS,
    SHOT_VIDEO_TOOLS,
    generate_shot_image,
    generate_shot_video,
    update_shot_prompt,
    bind_assets_to_shot,
)

# ── Per-target tool schema lists ───────────────────────────────────────────────

TARGET_TOOLS: dict[str, list[dict]] = {
    ConversationTarget.asset:       ASSET_TOOLS,
    ConversationTarget.shot_image:  SHOT_IMAGE_TOOLS,
    ConversationTarget.shot_video:  SHOT_VIDEO_TOOLS,
    # episode / project targets get all tools
    ConversationTarget.episode:     ASSET_TOOLS + SHOT_IMAGE_TOOLS + SHOT_VIDEO_TOOLS,
    ConversationTarget.project:     ASSET_TOOLS + SHOT_IMAGE_TOOLS + SHOT_VIDEO_TOOLS,
    ConversationTarget.shot_script: [],  # LLM-only, no generation tools needed
}

# ── Dispatcher: name → async function ─────────────────────────────────────────

_DISPATCH: dict[str, callable] = {
    "generate_asset_image":  generate_asset_image,
    "update_asset_prompt":   update_asset_prompt,
    "generate_shot_image":   generate_shot_image,
    "generate_shot_video":   generate_shot_video,
    "update_shot_prompt":    update_shot_prompt,
    "bind_assets_to_shot":   bind_assets_to_shot,
}


async def dispatch_tool(name: str, arguments: dict) -> dict:
    """Execute a tool by name with given arguments. Returns result dict."""
    fn = _DISPATCH.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    return await fn(**arguments)


def get_tools_for_target(target_type: str) -> list[dict]:
    return TARGET_TOOLS.get(target_type, [])
