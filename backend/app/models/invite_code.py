from datetime import datetime
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class InviteCode(Document):
    code: str
    used: bool = False
    used_by: Optional[PydanticObjectId] = None
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "invite_codes"
        indexes = ["code"]
