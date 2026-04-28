from datetime import datetime
from enum import Enum
from beanie import Document
from pydantic import Field


class PromptConfigScope(str, Enum):
    script_parse         = "script_parse"
    episode_split        = "episode_split"
    continuity_extract   = "continuity_extract"
    shot_script_gen      = "shot_script_gen"
    shot_script_edit     = "shot_script_edit"
    asset_prompt_gen     = "asset_prompt_gen"
    asset_prompt_edit    = "asset_prompt_edit"
    shot_image_gen       = "shot_image_gen"
    shot_image_edit      = "shot_image_edit"
    shot_video_gen       = "shot_video_gen"
    shot_video_edit      = "shot_video_edit"
    dubbing_gen          = "dubbing_gen"
    series_overview_edit = "series_overview_edit"
    script_map           = "script_map"


class PromptConfig(Document):
    scope: PromptConfigScope
    name: str
    system_prompt: str
    user_prompt_template: str = ""
    description: str = ""
    version: int = 1
    is_active: bool = True
    variables: list[str] = []
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "prompt_configs"
        indexes = [
            [("scope", 1), ("is_active", 1)],
        ]
