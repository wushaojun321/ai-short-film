"""Conversation CRUD + agent chat endpoint."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from pydantic import BaseModel
from app.models.conversation import Conversation, ConversationTarget, ConversationRole, Message
from app.deps import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"], dependencies=[Depends(get_current_user)])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    target_type: ConversationTarget
    target_id: str
    project_id: str
    title: str = "新对话"


class ChatRequest(BaseModel):
    content: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls_made: list[dict]
    conversation_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("")
async def create_conversation(body: CreateConversationRequest):
    """Create a new conversation bound to a target (asset / shot / episode)."""
    conv = Conversation(
        target_type=body.target_type,
        target_id=PydanticObjectId(body.target_id),
        project_id=PydanticObjectId(body.project_id),
        title=body.title,
    )
    await conv.insert()
    return conv


@router.get("")
async def list_conversations(target_id: str | None = None, project_id: str | None = None):
    """List conversations, optionally filtered by target_id or project_id."""
    conditions = []
    if target_id:
        conditions.append(Conversation.target_id == PydanticObjectId(target_id))
    if project_id:
        conditions.append(Conversation.project_id == PydanticObjectId(project_id))
    query = Conversation.find(*conditions) if conditions else Conversation.find()
    return await query.sort("-updated_at").to_list()


@router.get("/{conv_id}")
async def get_conversation(conv_id: PydanticObjectId):
    """Get a conversation by ID (includes all messages)."""
    conv = await Conversation.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: PydanticObjectId):
    conv = await Conversation.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await conv.delete()
    return {"deleted": True}


@router.post("/{conv_id}/chat")
async def chat(conv_id: PydanticObjectId, body: ChatRequest) -> ChatResponse:
    """
    Send a user message to the agent and get a reply.

    Flow:
    1. Load conversation + history
    2. Build system prompt (base + series_prompt + target snapshot)
    3. Get applicable tools for this target_type
    4. Run agent loop (tool-calling)
    5. Persist all new messages, return reply
    """
    conv = await Conversation.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    from app.agent.context import build_system_prompt
    from app.agent.runner import run_agent
    from app.tools.registry import get_tools_for_target

    # Build system prompt with current target state
    system_prompt = await build_system_prompt(
        target_type=conv.target_type,
        target_id=str(conv.target_id),
        project_id=str(conv.project_id),
    )

    # Convert stored messages to LLM-compatible dicts (skip system messages)
    history = [
        {"role": m.role, "content": m.content}
        for m in conv.messages
        if m.role in (ConversationRole.user, ConversationRole.assistant)
    ]

    tools = get_tools_for_target(conv.target_type)

    # Run agent
    reply, new_messages, tool_calls_made = await run_agent(
        system_prompt=system_prompt,
        history=history,
        user_message=body.content,
        tools=tools,
    )

    # Persist new user + assistant messages (skip tool messages — internal detail)
    now = datetime.utcnow()
    persistent_messages: list[Message] = []
    for m in new_messages:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            persistent_messages.append(Message(
                role=ConversationRole(role),
                content=content,
                created_at=now,
            ))

    if persistent_messages:
        await conv.set({
            "messages": conv.messages + persistent_messages,
            "updated_at": now,
        })

    return ChatResponse(
        reply=reply,
        tool_calls_made=tool_calls_made,
        conversation_id=str(conv.id),
    )
