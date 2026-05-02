from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field


class ScriptBlockType(str, Enum):
    episode_header = "episode_header"
    scene_header = "scene_header"
    dialogue = "dialogue"
    action = "action"
    paragraph = "paragraph"


class ScriptBlock(Document):
    project_id: PydanticObjectId
    block_index: int
    block_type: ScriptBlockType
    text: str
    start_line: int
    end_line: int
    char_start: int
    char_end: int
    speaker: str = ""
    episode_hint: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "script_blocks"
        indexes = [
            "project_id",
            [("project_id", 1), ("block_index", 1)],
            [("project_id", 1), ("episode_hint", 1)],
        ]
