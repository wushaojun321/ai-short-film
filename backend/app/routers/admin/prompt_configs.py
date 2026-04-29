from fastapi import APIRouter, HTTPException
from app.models.prompt_config import PromptConfigScope
from app.services.prompt_service import _PROMPTS

router = APIRouter(prefix="/admin/prompt-configs", tags=["admin"])


@router.get("")
async def list_configs():
    """List all prompt configs (read from code constants)."""
    return {k: {"scope": k, "system_prompt": v["system_prompt"], "user_prompt_template": v.get("user_prompt_template", "")} for k, v in _PROMPTS.items()}


@router.get("/{scope}")
async def get_config(scope: PromptConfigScope):
    key = str(scope.value)
    if key not in _PROMPTS:
        raise HTTPException(404, f"No config for scope: {scope}")
    v = _PROMPTS[key]
    return {"scope": key, "system_prompt": v["system_prompt"], "user_prompt_template": v.get("user_prompt_template", "")}
