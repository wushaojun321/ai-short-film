from typing import Optional
from pydantic import BaseModel
from app.models.shot import ShotState


class ShotCreate(BaseModel):
    shot_code: str
    order: int
    duration: int = 5
    description: str = ""
    prompt: str = ""


class ShotUpdate(BaseModel):
    shot_code: Optional[str] = None
    order: Optional[int] = None
    duration: Optional[int] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    state: Optional[ShotState] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    review_comment: Optional[str] = None


class ShotReviewRequest(BaseModel):
    approved: bool
    comment: str = ""


class BatchReviewRequest(BaseModel):
    reviews: list[dict]  # [{"shot_id": str, "approved": bool, "comment": ""}]
