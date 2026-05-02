from typing import Optional
from pydantic import BaseModel
from app.models.asset import AssetType, AssetStatus


class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType
    prompt: str = ""
    voice_profile: str = ""
    character_name: str = ""
    scene_scope: str = ""
    appearance_stage: str = ""
    view_requirements: str = ""
    status: AssetStatus = AssetStatus.pending


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    voice_profile: Optional[str] = None
    character_name: Optional[str] = None
    scene_scope: Optional[str] = None
    appearance_stage: Optional[str] = None
    view_requirements: Optional[str] = None
    status: Optional[AssetStatus] = None
    preview_url: Optional[str] = None


class AssetConfirmRequest(BaseModel):
    status: AssetStatus  # "approved" | "need_regen"
