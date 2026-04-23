from typing import Optional
from pydantic import BaseModel
from app.models.project import ProjectInitStatus


class ProjectCreate(BaseModel):
    title: str
    genre: str = ""
    format: str = "VERTICAL_9_16"
    target_episode_count: int = 0
    min_episode_duration: int = 120


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    format: Optional[str] = None
    target_episode_count: Optional[int] = None
    min_episode_duration: Optional[int] = None
    series_prompt: Optional[str] = None
    parse_notes: Optional[str] = None
    progress: Optional[int] = None
    init_status: Optional[ProjectInitStatus] = None


class ParseScriptRequest(BaseModel):
    target_episodes: int = 8
    min_duration: int = 120
    parse_notes: str = ""


class ConfirmEpisodesRequest(BaseModel):
    episodes: list[dict]  # [{id, title, summary, word_count, estimated_duration}]
