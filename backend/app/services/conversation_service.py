"""Multi-turn conversation service for artifact editing via LLM."""
from __future__ import annotations
from datetime import datetime
from beanie import PydanticObjectId
from app.models.conversation import Conversation, Message, ConversationRole, ConversationTarget
from app.services import llm_service
from app.services.prompt_service import render
from app.models.prompt_config import PromptConfigScope


async def get_or_create_conversation(
    target_type: ConversationTarget,
    target_id: PydanticObjectId,
    project_id: PydanticObjectId,
    title: str = "新对话",
) -> Conversation:
    """Get active conversation for target, or create new one."""
    existing = await Conversation.find_one(
        Conversation.target_type == target_type,
        Conversation.target_id == target_id,
        Conversation.is_active == True,
    )
    if existing:
        return existing

    conv = Conversation(
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
        title=title,
    )
    await conv.insert()
    return conv


async def list_conversations(target_id: PydanticObjectId) -> list[Conversation]:
    return await Conversation.find(
        Conversation.target_id == target_id,
    ).sort("-created_at").to_list()


async def get_conversation(conv_id: PydanticObjectId) -> Conversation | None:
    return await Conversation.get(conv_id)


async def _build_artifact_snapshot(
    target_type: ConversationTarget,
    target_id: PydanticObjectId,
    lightweight: bool = False,
) -> dict:
    """Fetch current artifact state as a dict snapshot."""
    if target_type == ConversationTarget.shot_script:
        from app.models.shot import Shot
        obj = await Shot.get(target_id)
        if obj:
            return {
                "shot_code": obj.shot_code,
                "description": obj.description,
                "prompt": obj.prompt,
                "state": obj.state,
                "duration": obj.duration,
                "transition_in": obj.transition_in,
                "transition_out": obj.transition_out,
                "transition_type": obj.transition_type,
                "start_state": obj.start_state,
                "end_state": obj.end_state,
                "screen_direction": obj.screen_direction,
                "continuity_notes": obj.continuity_notes,
                "use_prev_last_frame": obj.use_prev_last_frame,
            }
    elif target_type == ConversationTarget.shot_image:
        from app.models.shot import Shot
        obj = await Shot.get(target_id)
        if obj:
            return {"shot_code": obj.shot_code, "image_url": obj.image_url, "prompt": obj.prompt}
    elif target_type == ConversationTarget.shot_video:
        from app.models.shot import Shot
        obj = await Shot.get(target_id)
        if obj:
            return {"shot_code": obj.shot_code, "video_url": obj.video_url, "prompt": obj.prompt}
    elif target_type == ConversationTarget.asset:
        from app.models.asset import Asset
        obj = await Asset.get(target_id)
        if obj:
            return {"name": obj.name, "asset_type": obj.asset_type, "prompt": obj.prompt, "preview_url": obj.preview_url}
    elif target_type == ConversationTarget.episode:
        from app.models.episode import Episode
        from app.models.shot import Shot
        obj = await Episode.get(target_id)
        if obj:
            shots = await Shot.find(Shot.episode_id == obj.id).sort("+order").to_list()
            def dialogue_summary(line) -> str:
                speaker_text = f"{line.speaker}：{line.text}" if line.speaker else line.text
                performance = "，".join(
                    part for part in [
                        f"情绪={line.emotion}" if line.emotion else "",
                        f"语气={line.delivery}" if line.delivery else "",
                        f"动作={line.action}" if line.action else "",
                        f"表情={line.expression}" if line.expression else "",
                    ] if part
                )
                return f"{speaker_text}（{performance}）" if performance else speaker_text

            shot_list = [
                f"{s.shot_code}（{s.duration}s）: {s.description[:80]}"
                + (f" 台词：{'；'.join(dialogue_summary(d) for d in s.dialogues)}" if s.dialogues else "")
                for s in shots
            ]
            return {
                "id": str(obj.id),
                "title": obj.title,
                "summary": obj.summary,
                "current_step": obj.current_step,
                "shots": shot_list,
            }
    elif target_type == ConversationTarget.project:
        from app.models.project import Project
        from app.models.episode import Episode
        obj = await Project.get(target_id)
        if obj:
            episodes = await Episode.find(Episode.project_id == obj.id).sort("+number").to_list()
            episode_list = [
                {
                    "number": e.number,
                    "title": e.title,
                    "summary": e.summary,
                    "word_count": e.word_count,
                    "estimated_duration": e.estimated_duration,
                    # 首次对话注入完整剧本片段；后续轮次省略以节省 token
                    **({"script_excerpt": e.script_excerpt} if not lightweight else {}),
                }
                for e in episodes
            ]
            result: dict = {
                "title": obj.title,
                "genre": obj.genre,
                "series_prompt": obj.series_prompt,
                "episodes": episode_list,
            }
            # 首次对话注入完整原始剧本；后续轮次省略
            if not lightweight and obj.script_text:
                result["script_text"] = obj.script_text
            return result
    return {}


def _scope_for_target(target_type: ConversationTarget) -> PromptConfigScope:
    mapping = {
        ConversationTarget.shot_script: PromptConfigScope.shot_script_edit,
        ConversationTarget.shot_image: PromptConfigScope.shot_image_edit,
        ConversationTarget.shot_video: PromptConfigScope.shot_video_edit,
        ConversationTarget.asset: PromptConfigScope.asset_prompt_edit,
        ConversationTarget.episode: PromptConfigScope.shot_script_edit,
        ConversationTarget.project: PromptConfigScope.series_overview_edit,
    }
    return mapping.get(target_type, PromptConfigScope.shot_script_edit)


async def send_message(
    conversation: Conversation,
    user_content: str,
) -> tuple[str, Conversation]:
    """Append user message, call LLM with full context, append assistant reply.
    
    Returns (assistant_reply, updated_conversation).
    """
    # Build artifact snapshot — full on first turn, lightweight on subsequent turns
    is_first_turn = len(conversation.messages) == 0
    snapshot = await _build_artifact_snapshot(
        conversation.target_type, conversation.target_id,
        lightweight=not is_first_turn,
    )

    # Get system prompt from config
    scope = _scope_for_target(conversation.target_type)
    try:
        system_prompt, _, config_snapshot = await render(scope, {"artifact": str(snapshot)})
    except Exception:
        system_prompt = "你是一位专业的短剧制作顾问，帮助用户修改制作素材。"
        config_snapshot = {}

    # Build messages list: system + last 20 messages + new user message
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Inject artifact context as first user message (first turn only)
    # Subsequent turns: snapshot is already in conversation history
    if snapshot and is_first_turn:
        messages.append({
            "role": "user",
            "content": f"当前制品信息：\n{snapshot}",
        })
        messages.append({
            "role": "assistant",
            "content": "好的，我已了解当前制品状态，请告诉我您想如何修改。",
        })
    elif snapshot and not is_first_turn:
        # 后续轮次只注入轻量状态更新（分集列表变化等），不重复注入原始剧本
        messages.append({
            "role": "user",
            "content": f"（当前最新状态：{snapshot}）",
        })
        messages.append({
            "role": "assistant",
            "content": "收到，已获取最新状态。",
        })

    # Add last 20 conversation messages
    history = conversation.messages[-20:]
    for m in history:
        messages.append({"role": m.role, "content": m.content})

    # Add new user message
    messages.append({"role": "user", "content": user_content})

    # Call LLM
    reply = await llm_service.chat_with_history(messages)

    # Save both messages to conversation
    user_msg = Message(
        role=ConversationRole.user,
        content=user_content,
        artifact_snapshot=snapshot if not conversation.messages else None,
    )
    assistant_msg = Message(
        role=ConversationRole.assistant,
        content=reply,
    )

    new_messages = conversation.messages + [user_msg, assistant_msg]
    await conversation.set({
        "messages": new_messages,
        "prompt_config_snapshot": config_snapshot,
        "updated_at": datetime.utcnow(),
    })

    return reply, conversation


async def apply_edit_from_reply(
    conversation: Conversation,
    assistant_reply: str,
) -> dict:
    """Parse assistant reply and apply edits to the target artifact.
    
    Returns dict of applied changes.
    """
    import json
    # Try to extract JSON from reply
    changes = {}
    try:
        # Find JSON block in reply
        start = assistant_reply.find("{")
        end = assistant_reply.rfind("}") + 1
        if start >= 0 and end > start:
            changes = json.loads(assistant_reply[start:end])
    except Exception:
        # No parseable JSON — return raw text for user to review
        return {"raw_reply": assistant_reply}

    target_type = conversation.target_type
    target_id = conversation.target_id

    if target_type in (ConversationTarget.shot_script, ConversationTarget.shot_image, ConversationTarget.shot_video):
        from app.models.shot import Shot
        shot = await Shot.get(target_id)
        if shot and changes:
            allowed = {
                "description", "prompt", "duration", "shot_code",
                "transition_in", "transition_out", "transition_type",
                "start_state", "end_state", "screen_direction",
                "continuity_notes", "use_prev_last_frame",
            }
            update = {k: v for k, v in changes.items() if k in allowed}
            if update:
                await shot.set(update)

    elif target_type == ConversationTarget.asset:
        from app.models.asset import Asset
        asset = await Asset.get(target_id)
        if asset and changes:
            allowed = {"prompt", "name"}
            update = {k: v for k, v in changes.items() if k in allowed}
            if update:
                await asset.set(update)

    elif target_type == ConversationTarget.episode:
        from app.models.episode import Episode
        episode = await Episode.get(target_id)
        if episode and changes:
            allowed = {"title", "summary", "continuity_notes"}
            update = {k: v for k, v in changes.items() if k in allowed}
            if update:
                await episode.set(update)

    return changes
