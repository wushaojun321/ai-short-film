from typing import Optional
from pydantic import BaseModel
from app.models.asset import AssetType, AssetStatus


class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType
    prompt: str = ""
    status: AssetStatus = AssetStatus.pending


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    status: Optional[AssetStatus] = None
    preview_url: Optional[str] = None


class AssetConfirmRequest(BaseModel):
    status: AssetStatus  # "approved" | "need_regen"
