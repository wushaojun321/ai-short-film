from typing import Optional
from pydantic import BaseModel, Field
from app.models.asset import AssetType, AssetStatus


class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType
    prompt: str = ""
    voice_profile: str = ""
    character_name: str = ""
    asset_package: str = ""
    face_identity: str = ""
    distinctive_traits: list[str] = Field(default_factory=list)
    avoid_similar_to: list[str] = Field(default_factory=list)
    look_lock: str = ""
    scene_scope: str = ""
    appearance_stage: str = ""
    view_requirements: str = ""
    submitted_prompt: str = ""
    submitted_prompts: dict[str, str] = Field(default_factory=dict)
    view_urls: dict[str, str] = Field(default_factory=dict)
    status: AssetStatus = AssetStatus.pending
    provider_preview_url: Optional[str] = None
    provider_view_urls: dict[str, str] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    voice_profile: Optional[str] = None
    character_name: Optional[str] = None
    asset_package: Optional[str] = None
    face_identity: Optional[str] = None
    distinctive_traits: Optional[list[str]] = None
    avoid_similar_to: Optional[list[str]] = None
    look_lock: Optional[str] = None
    scene_scope: Optional[str] = None
    appearance_stage: Optional[str] = None
    view_requirements: Optional[str] = None
    submitted_prompt: Optional[str] = None
    submitted_prompts: Optional[dict[str, str]] = None
    status: Optional[AssetStatus] = None
    preview_url: Optional[str] = None
    view_urls: Optional[dict[str, str]] = None
    provider_preview_url: Optional[str] = None
    provider_view_urls: Optional[dict[str, str]] = None


class AssetConfirmRequest(BaseModel):
    status: AssetStatus  # "approved" | "need_regen"
