from datetime import datetime
from beanie import Document
from pydantic import Field


class User(Document):
    username: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = ["username"]
