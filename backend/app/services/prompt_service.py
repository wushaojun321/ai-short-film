"""Prompt service — reads directly from code constants (llm_prompts.py).

Prompts are defined in app/prompts/llm_prompts.py and take effect immediately
on deploy, no database sync needed.
"""
from app.models.prompt_config import PromptConfigScope
from app.prompts import DEFAULT_PROMPTS

# Build a scope → prompt dict at import time
_PROMPTS: dict[str, dict] = {
    str(p["scope"].value): p for p in DEFAULT_PROMPTS
}


def _get(scope: PromptConfigScope) -> dict:
    key = str(scope.value)
    if key not in _PROMPTS:
        raise ValueError(f"No prompt config for scope: {scope}")
    return _PROMPTS[key]


async def render(scope: PromptConfigScope, variables: dict) -> tuple[str, str, dict]:
    """Return (system_prompt, rendered_user_prompt, config_snapshot)."""
    config = _get(scope)
    sys_tpl = config["system_prompt"]
    usr_tpl = config.get("user_prompt_template", "")
    try:
        system_prompt = sys_tpl.format(**variables)
    except KeyError:
        system_prompt = sys_tpl
    try:
        user_prompt = usr_tpl.format(**variables)
    except KeyError:
        user_prompt = usr_tpl
    snapshot = {
        "scope": str(scope.value),
        "version": 1,
        "system_prompt": sys_tpl,
        "user_prompt_template": usr_tpl,
    }
    return system_prompt, user_prompt, snapshot
