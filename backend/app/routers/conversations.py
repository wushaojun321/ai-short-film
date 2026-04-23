"""Conversation endpoints for multi-turn artifact editing."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from app.models.conversation import Conversation, ConversationTarget
from app.schemas.conversation import ConversationCreate, MessageCreate
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=201)
async def create_conversation(data: ConversationCreate):
    """Create or retrieve active conversation for an artifact."""
    conv = await conversation_service.get_or_create_conversation(
        target_type=ConversationTarget(data.target_type),
        target_id=PydanticObjectId(data.target_id),
        project_id=PydanticObjectId(data.project_id),
        title=data.title or "新对话",
    )
    return conv


@router.get("/by-target/{target_id}")
async def list_by_target(target_id: PydanticObjectId):
    return await conversation_service.list_conversations(target_id)


@router.get("/{conv_id}")
async def get_conversation(conv_id: PydanticObjectId):
    conv = await conversation_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("/{conv_id}/messages")
async def send_message(conv_id: PydanticObjectId, data: MessageCreate):
    """Send a user message and get LLM reply."""
    conv = await conversation_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    reply, updated = await conversation_service.send_message(conv, data.content)
    return {"reply": reply, "conversation": updated}


@router.post("/{conv_id}/apply-edit")
async def apply_edit(conv_id: PydanticObjectId):
    """Apply the last assistant message as edits to the artifact."""
    conv = await conversation_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if not conv.messages:
        raise HTTPException(400, "No messages in conversation")

    # Get last assistant message
    last_assistant = next(
        (m for m in reversed(conv.messages) if m.role == "assistant"), None
    )
    if not last_assistant:
        raise HTTPException(400, "No assistant message to apply")

    changes = await conversation_service.apply_edit_from_reply(conv, last_assistant.content)
    return {"applied_changes": changes}


@router.delete("/{conv_id}", status_code=204)
async def close_conversation(conv_id: PydanticObjectId):
    """Mark conversation as inactive."""
    conv = await conversation_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await conv.set({"is_active": False})
