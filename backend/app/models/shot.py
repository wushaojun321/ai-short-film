from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class ShotState(str, Enum):
    planned        = "planned"
    asset_required = "asset_required"
    generating     = "generating"   # image generating
    asset_ready    = "asset_ready"
    rendering      = "rendering"    # video generating
    rendered       = "rendered"
    review_failed  = "review_failed"
    approved       = "approved"


class ShotAssetBinding(BaseModel):
    asset_id: PydanticObjectId
    asset_name: str


class Shot(Document):
    project_id: PydanticObjectId
    episode_id: PydanticObjectId
    shot_code: str                         # "S01", "S02" ...
    order: int
    duration: int = 5
    description: str = ""
    dialogue: str = ""
    speaker: str = ""
    prompt: str = ""
    required_assets: list[ShotAssetBinding] = []
    state: ShotState = ShotState.planned
    version: str = "v1"
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    review_comment: str = ""
    generation_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "shots"
        indexes = [
            "episode_id",
            [("episode_id", 1), ("order", 1)],
        ]
