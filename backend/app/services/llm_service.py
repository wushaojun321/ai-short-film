"""OpenRouter LLM service with instructor for structured output."""
from __future__ import annotations
import json
import os
import httpx
from openai import AsyncOpenAI
from app.config import settings

_EXTRA_HEADERS = {
    "HTTP-Referer": "https://ai-short-film.local",
    "X-Title": "AI Short Film",
}


def get_client() -> AsyncOpenAI:
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    http_client = httpx.AsyncClient(proxy=httpx.Proxy(url=proxy_url)) if proxy_url else None
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        http_client=http_client,
    )


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    """Simple chat completion, returns raw text."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.openrouter_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        extra_headers=_EXTRA_HEADERS,
    )
    return resp.choices[0].message.content or ""


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 32000,
) -> dict:
    """Chat completion expecting JSON response. Returns parsed dict."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.openrouter_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        extra_headers=_EXTRA_HEADERS,
    )
    choice = resp.choices[0]
    content = choice.message.content or "{}"
    if choice.finish_reason == "length":
        raise ValueError(
            "LLM JSON response was truncated before completion. "
            "Increase max_tokens or reduce requested output size."
        )
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        try:
            return await _repair_json(content=content, max_tokens=max_tokens)
        except Exception:
            pass
        preview_start = max(exc.pos - 120, 0)
        preview_end = min(exc.pos + 120, len(content))
        preview = content[preview_start:preview_end].replace("\n", "\\n")
        raise ValueError(
            f"LLM returned invalid JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno} (char {exc.pos}). Around error: {preview}"
        ) from exc


async def _repair_json(content: str, max_tokens: int = 4096) -> dict:
    """Ask the model to repair malformed JSON once."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 JSON 修复器。用户会给你一段格式损坏的 JSON。"
                    "只输出修复后的合法 JSON 对象，不要解释。"
                    "保留原有字段和信息，修复未转义换行、引号、逗号、括号等语法问题。"
                    "如果内容末尾被截断，请尽量补全最小合法结构。"
                ),
            },
            {"role": "user", "content": content},
        ],
        temperature=0,
        max_tokens=max(max_tokens, 4096),
        response_format={"type": "json_object"},
        extra_headers=_EXTRA_HEADERS,
    )
    repaired = resp.choices[0].message.content or "{}"
    return json.loads(repaired)


async def chat_with_history(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    """Multi-turn chat with pre-built messages list."""
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.openrouter_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_headers=_EXTRA_HEADERS,
    )
    return resp.choices[0].message.content or ""


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> tuple[str | None, list | None]:
    """
    Single LLM call with tool definitions.
    Returns (text_reply, tool_calls):
      - If LLM returns tool_calls: (None, tool_calls_list)
      - If LLM returns text:       (text, None)
    """
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.openrouter_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=temperature,
        max_tokens=max_tokens,
        extra_headers=_EXTRA_HEADERS,
    )
    choice = resp.choices[0]
    msg = choice.message

    if choice.finish_reason == "tool_calls" and msg.tool_calls:
        return None, msg.tool_calls

    return msg.content or "", None
