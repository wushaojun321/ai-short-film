from fastapi import APIRouter, HTTPException
from app.models.prompt_config import PromptConfigScope
from app.schemas.prompt_config import PromptConfigUpdate
import app.services.prompt_service as prompt_service

router = APIRouter(prefix="/admin/prompt-configs", tags=["admin"])


@router.get("")
async def list_configs():
    """List active prompt configs for all scopes."""
    results = {}
    for scope in PromptConfigScope:
        try:
            cfg = await prompt_service.get_active(scope)
            results[scope.value] = cfg
        except ValueError:
            pass
    return results


@router.get("/{scope}")
async def get_config(scope: PromptConfigScope):
    try:
        return await prompt_service.get_active(scope)
    except ValueError:
        raise HTTPException(404, f"No active config for scope: {scope}")


@router.put("/{scope}")
async def update_config(scope: PromptConfigScope, data: PromptConfigUpdate):
    return await prompt_service.upsert(
        scope=scope,
        system_prompt=data.system_prompt,
        user_prompt_template=data.user_prompt_template or "",
        description=data.description or "",
        variables=data.variables or [],
    )


@router.get("/{scope}/history")
async def get_history(scope: PromptConfigScope):
    return await prompt_service.get_history(scope)


@router.post("/{scope}/rollback/{version}")
async def rollback(scope: PromptConfigScope, version: int):
    try:
        return await prompt_service.rollback(scope, version)
    except ValueError as e:
        raise HTTPException(404, str(e))
