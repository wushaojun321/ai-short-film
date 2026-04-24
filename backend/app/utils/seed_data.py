"""Seed default prompt configs on startup."""
from app.models.prompt_config import PromptConfig
from app.prompts import DEFAULT_PROMPTS


async def seed_prompt_configs():
    """Insert default prompt configs if they don't exist."""
    for item in DEFAULT_PROMPTS:
        existing = await PromptConfig.find_one(
            PromptConfig.scope == item["scope"],
            PromptConfig.is_active == True,
        )
        if not existing:
            config = PromptConfig(
                scope=item["scope"],
                name=item["name"],
                system_prompt=item["system_prompt"],
                user_prompt_template=item.get("user_prompt_template", ""),
                description=item.get("description", ""),
                variables=item.get("variables", []),
                version=1,
                is_active=True,
            )
            await config.insert()
