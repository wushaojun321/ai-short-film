from beanie import init_beanie
from app.config import settings
from app.models import (
    Project, Episode, Shot, Asset,
    ScriptBlock, ProductionBlueprint,
    Conversation, PromptConfig, TaskRecord,
    User, InviteCode,
)


async def init_db():
    await init_beanie(
        connection_string=settings.mongodb_url,
        document_models=[
            Project,
            Episode,
            ScriptBlock,
            ProductionBlueprint,
            Shot,
            Asset,
            Conversation,
            PromptConfig,
            TaskRecord,
            User,
            InviteCode,
        ],
    )
