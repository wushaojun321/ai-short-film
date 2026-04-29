"""Seed default prompt configs on startup."""
import hashlib
from datetime import datetime
from app.models.prompt_config import PromptConfig
from app.prompts import DEFAULT_PROMPTS


def _content_hash(item: dict) -> str:
    """Hash system_prompt + user_prompt_template to detect changes."""
    content = item.get("system_prompt", "") + item.get("user_prompt_template", "")
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def seed_prompt_configs():
    """Insert or update prompt configs on startup.

    - If a config doesn't exist: insert it.
    - If it exists but content has changed (hash mismatch): update in-place
      and bump version. This ensures code-side prompt changes are automatically
      synced to the database on next deploy, without manual intervention.
    """
    for item in DEFAULT_PROMPTS:
        new_hash = _content_hash(item)
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
        else:
            existing_hash = _content_hash({
                "system_prompt": existing.system_prompt,
                "user_prompt_template": existing.user_prompt_template,
            })
            if existing_hash != new_hash:
                await existing.set({
                    "system_prompt": item["system_prompt"],
                    "user_prompt_template": item.get("user_prompt_template", ""),
                    "description": item.get("description", existing.description),
                    "variables": item.get("variables", existing.variables),
                    "version": existing.version + 1,
                    "updated_at": datetime.utcnow(),
                })
