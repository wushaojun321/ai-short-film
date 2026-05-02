"""
统一提示词管理入口。

所有提示词集中在此目录：
  llm_prompts.py    —— LLM scope 提示词（当前运行时直接从代码常量读取）
  agent_prompts.py  —— Agent 基础提示词（硬编码，不入库）

调用方式：
  from app.prompts import DEFAULT_PROMPTS      # → prompt_service.py
  from app.prompts import BASE_INSTRUCTIONS    # → agent/context.py
  from app.prompts import SHOT_SCRIPT_GEN      # 按名称引用单条（可选）
"""

from app.prompts.llm_prompts import (
    DEFAULT_PROMPTS,
    SCRIPT_PARSE,
    SERIES_PLAN,
    EPISODE_SPLIT,
    ASSET_EXTRACT,
    CONTINUITY_EXTRACT,
    ASSET_PROMPT_GEN,
    SHOT_SCRIPT_GEN,
    SHOT_IMAGE_GEN,
    SHOT_VIDEO_GEN,
    SHOT_SCRIPT_EDIT,
    ASSET_PROMPT_EDIT,
    SHOT_IMAGE_EDIT,
    SHOT_VIDEO_EDIT,
    DUBBING_GEN,
    SERIES_OVERVIEW_EDIT,
)
from app.prompts.agent_prompts import BASE_INSTRUCTIONS

__all__ = [
    "DEFAULT_PROMPTS",
    "BASE_INSTRUCTIONS",
    # 单条 prompt 常量
    "SCRIPT_PARSE",
    "SERIES_PLAN",
    "EPISODE_SPLIT",
    "ASSET_EXTRACT",
    "CONTINUITY_EXTRACT",
    "ASSET_PROMPT_GEN",
    "SHOT_SCRIPT_GEN",
    "SHOT_IMAGE_GEN",
    "SHOT_VIDEO_GEN",
    "SHOT_SCRIPT_EDIT",
    "ASSET_PROMPT_EDIT",
    "SHOT_IMAGE_EDIT",
    "SHOT_VIDEO_EDIT",
    "DUBBING_GEN",
    "SERIES_OVERVIEW_EDIT",
]
