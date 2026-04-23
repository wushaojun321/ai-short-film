from typing import Optional
from pydantic import BaseModel
from app.models.episode import EpisodeStatus, EpisodeStep


class EpisodeCreate(BaseModel):
    number: int
    title: str
    summary: str = ""
    word_count: int = 0
    estimated_duration: int = 0
    continuity_notes: str = ""


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    word_count: Optional[int] = None
    estimated_duration: Optional[int] = None
    continuity_notes: Optional[str] = None
    status: Optional[EpisodeStatus] = None
    current_step: Optional[EpisodeStep] = None


class StepAdvanceRequest(BaseModel):
    step: EpisodeStep
