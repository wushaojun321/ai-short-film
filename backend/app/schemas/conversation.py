from typing import Optional
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    target_type: str      # ConversationTarget value
    target_id: str        # MongoDB object id
    project_id: str       # MongoDB object id
    title: Optional[str] = "新对话"


class MessageCreate(BaseModel):
    content: str
