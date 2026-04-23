from beanie import init_beanie
from app.config import settings
from app.models import (
    Project, Episode, Shot, Asset,
    Conversation, PromptConfig, TaskRecord,
)


async def init_db():
    await init_beanie(
        connection_string=settings.mongodb_url,
        document_models=[
            Project,
            Episode,
            Shot,
            Asset,
            Conversation,
            PromptConfig,
            TaskRecord,
        ],
    )
