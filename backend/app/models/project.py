from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class ProjectInitStatus(str, Enum):
    not_started        = "not_started"
    script_uploaded    = "script_uploaded"
    episodes_confirmed = "episodes_confirmed"
    assets_confirmed   = "assets_confirmed"
    initialized        = "initialized"


class Project(Document):
    owner_id: Optional[PydanticObjectId] = None  # 创建者用户 ID
    title: str
    genre: str = ""
    format: str = "VERTICAL_9_16"
    target_episode_count: int = 0
    min_episode_duration: int = 120
    init_status: ProjectInitStatus = ProjectInitStatus.not_started
    script_file_url: Optional[str] = None
    script_text: Optional[str] = None
    series_prompt: Optional[str] = None
    parse_notes: Optional[str] = None
    script_index_version: str = ""
    script_indexed_at: Optional[datetime] = None
    progress: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "projects"
        indexes = ["title", "owner_id"]
