"""
Agent runner: OpenAI tool-calling loop.

All tools are fire-and-forget (they dispatch Celery tasks and return immediately),
so the loop almost always completes in 1-2 rounds:
  round 1: LLM decides which tools to call
  round 2: LLM sees tool results, generates final text reply
"""
from __future__ import annotations
import asyncio
import json
from app.services.llm_service import chat_with_tools
from app.tools.registry import dispatch_tool


async def run_agent(
    system_prompt: str,
    history: list[dict],          # prior conversation messages (role/content dicts)
    user_message: str,            # current user input
    tools: list[dict],            # OpenAI function schemas for this target
    max_rounds: int = 5,
    history_limit: int = 20,
    audit: dict | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """
    Execute agent loop.

    Returns:
        reply        — final text reply to show the user
        new_messages — list of new messages produced this turn
                       (user + any tool messages + assistant reply)
        tool_calls_made — summary of tools that were dispatched
    """
    # Build full message list: system + history + new user message
    msgs: list[dict] = [{"role": "system", "content": system_prompt}]
    msgs.extend(history[-history_limit:] if history_limit > 0 else [])
    user_msg = {"role": "user", "content": user_message}
    msgs.append(user_msg)

    new_messages: list[dict] = [user_msg]
    tool_calls_made: list[dict] = []

    for _round in range(max_rounds):
        text_reply, tool_calls = await chat_with_tools(
            messages=msgs,
            tools=tools,
            scope="agent_tool_call",
            audit=audit,
        )

        if tool_calls:
            # Append assistant message with tool_calls (OpenAI SDK objects → dict)
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            msgs.append(assistant_msg)
            new_messages.append(assistant_msg)

            # Execute all tool calls in parallel (all are fire-and-forget so fast)
            results = await asyncio.gather(
                *[
                    dispatch_tool(tc.function.name, json.loads(tc.function.arguments))
                    for tc in tool_calls
                ],
                return_exceptions=True,
            )

            for tc, result in zip(tool_calls, results):
                if isinstance(result, Exception):
                    result = {"error": str(result)}

                tool_calls_made.append({
                    "tool": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    "result": result,
                })

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
                msgs.append(tool_msg)
                new_messages.append(tool_msg)

        else:
            # LLM returned a text reply — we're done
            reply = text_reply or ""
            reply_msg = {"role": "assistant", "content": reply}
            new_messages.append(reply_msg)
            return reply, new_messages, tool_calls_made

    # Fallback if max_rounds hit (shouldn't happen with fire-and-forget tools)
    fallback = "已完成处理，请查看前端最新状态。"
    new_messages.append({"role": "assistant", "content": fallback})
    return fallback, new_messages, tool_calls_made
