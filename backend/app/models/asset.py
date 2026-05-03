from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    character = "character"
    scene     = "scene"
    prop      = "prop"
    template  = "template"


class AssetStatus(str, Enum):
    pending    = "pending"
    queued     = "queued"     # task enqueued, waiting for worker
    generating = "generating"  # worker picked up, actively generating
    approved   = "approved"
    need_regen = "need_regen"
    missing    = "missing"


class AssetVersion(BaseModel):
    version: str
    url: str
    prompt: str
    note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Asset(Document):
    project_id: PydanticObjectId
    name: str
    asset_type: AssetType
    status: AssetStatus = AssetStatus.pending
    prompt: str = ""
    voice_profile: str = ""
    character_name: str = ""
    asset_package: str = ""
    face_identity: str = ""
    scene_scope: str = ""
    appearance_stage: str = ""
    view_requirements: str = ""
    preview_url: Optional[str] = None
    versions: list[AssetVersion] = []
    generation_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "assets"
        indexes = [
            "project_id",
            [("project_id", 1), ("asset_type", 1)],
        ]
