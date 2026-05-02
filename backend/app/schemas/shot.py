from typing import Optional
from pydantic import BaseModel
from app.models.shot import ShotState


class ShotCreate(BaseModel):
    shot_code: str
    order: int
    duration: int = 5
    segment_code: str = ""
    segment_name: str = ""
    segment_function: str = ""
    shot_function: str = ""
    transition_in: str = ""
    transition_out: str = ""
    start_state: str = ""
    end_state: str = ""
    screen_direction: str = ""
    continuity_notes: str = ""
    use_prev_last_frame: bool = False
    description: str = ""
    prompt: str = ""


class ShotUpdate(BaseModel):
    shot_code: Optional[str] = None
    order: Optional[int] = None
    duration: Optional[int] = None
    segment_code: Optional[str] = None
    segment_name: Optional[str] = None
    segment_function: Optional[str] = None
    shot_function: Optional[str] = None
    transition_in: Optional[str] = None
    transition_out: Optional[str] = None
    start_state: Optional[str] = None
    end_state: Optional[str] = None
    screen_direction: Optional[str] = None
    continuity_notes: Optional[str] = None
    use_prev_last_frame: Optional[bool] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    submitted_prompt: Optional[str] = None
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
