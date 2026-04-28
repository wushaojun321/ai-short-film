"""Prompt configuration management service."""
from datetime import datetime
from app.models.prompt_config import PromptConfig, PromptConfigScope


async def get_active(scope: PromptConfigScope) -> PromptConfig:
    config = await PromptConfig.find_one(
        PromptConfig.scope == scope,
        PromptConfig.is_active == True,
    )
    if not config:
        raise ValueError(f"No active prompt config for scope: {scope}")
    return config


async def render(scope: PromptConfigScope, variables: dict) -> tuple[str, str, dict]:
    """Return (system_prompt, rendered_user_prompt, config_snapshot)."""
    config = await get_active(scope)
    try:
        system_prompt = config.system_prompt.format(**variables)
    except KeyError:
        system_prompt = config.system_prompt
    try:
        user_prompt = config.user_prompt_template.format(**variables)
    except KeyError:
        user_prompt = config.user_prompt_template
    snapshot = {
        "scope": config.scope,
        "version": config.version,
        "system_prompt": config.system_prompt,
        "user_prompt_template": config.user_prompt_template,
    }
    return system_prompt, user_prompt, snapshot


async def upsert(
    scope: PromptConfigScope,
    system_prompt: str,
    user_prompt_template: str = "",
    name: str = "",
    description: str = "",
    variables: list[str] | None = None,
) -> PromptConfig:
    """Update or create a prompt config (version-controlled)."""
    existing = await PromptConfig.find_one(
        PromptConfig.scope == scope,
        PromptConfig.is_active == True,
    )
    if existing:
        # Deactivate old
        existing.is_active = False
        existing.updated_at = datetime.utcnow()
        await existing.save()
        new_version = existing.version + 1
    else:
        new_version = 1

    config = PromptConfig(
        scope=scope,
        name=name or str(scope.value),
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        description=description,
        variables=variables or [],
        version=new_version,
        is_active=True,
    )
    await config.insert()
    return config


async def get_history(scope: PromptConfigScope) -> list[PromptConfig]:
    return await PromptConfig.find(PromptConfig.scope == scope).sort("-version").to_list()


async def rollback(scope: PromptConfigScope, version: int) -> PromptConfig:
    target = await PromptConfig.find_one(
        PromptConfig.scope == scope,
        PromptConfig.version == version,
    )
    if not target:
        raise ValueError(f"Version {version} not found for scope {scope}")

    # Deactivate current active
    current = await PromptConfig.find_one(
        PromptConfig.scope == scope,
        PromptConfig.is_active == True,
    )
    if current:
        current.is_active = False
        current.updated_at = datetime.utcnow()
        await current.save()

    target.is_active = True
    target.updated_at = datetime.utcnow()
    await target.save()
    return target
