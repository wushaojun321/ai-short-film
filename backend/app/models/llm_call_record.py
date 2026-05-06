from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field


class LLMCallRecord(Document):
    provider: str = "openrouter"
    call_type: str = ""
    scope: str = ""
    model: str = ""
    input_chars: int = 0
    output_chars: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    max_tokens: int = 0
    temperature: float = 0.0
    duration_ms: int = 0
    success: bool = True
    finish_reason: str = ""
    error: str = ""
    project_id: Optional[PydanticObjectId] = None
    episode_id: Optional[PydanticObjectId] = None
    shot_id: Optional[PydanticObjectId] = None
    target_id: Optional[PydanticObjectId] = None
    meta: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "llm_call_records"
        indexes = [
            "scope",
            "created_at",
            [("project_id", 1), ("created_at", -1)],
            [("episode_id", 1), ("created_at", -1)],
            [("shot_id", 1), ("created_at", -1)],
        ]
