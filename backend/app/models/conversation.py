from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class ConversationRole(str, Enum):
    user      = "user"
    assistant = "assistant"
    system    = "system"


class ConversationTarget(str, Enum):
    project        = "project"
    episode        = "episode"
    shot_script    = "shot_script"
    shot_image     = "shot_image"
    shot_video     = "shot_video"
    asset          = "asset"


class Message(BaseModel):
    role: ConversationRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None
    artifact_snapshot: Optional[dict] = None


class Conversation(Document):
    target_type: ConversationTarget
    target_id: PydanticObjectId
    project_id: PydanticObjectId
    title: str = "新对话"
    messages: list[Message] = []
    prompt_config_snapshot: Optional[dict] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "conversations"
        indexes = [
            "target_id",
            "project_id",
            [("target_type", 1), ("target_id", 1)],
        ]
