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
    max_tokens: int = 16000,
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
    max_tokens: int = 16000,
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
    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # LLM output was truncated — salvage complete objects from a partial JSON array
        import re
        # Find all complete {...} objects inside the truncated content
        salvaged = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', content, re.DOTALL)
        if salvaged:
            complete = []
            for s in salvaged:
                try:
                    complete.append(json.loads(s))
                except json.JSONDecodeError:
                    pass
            if complete:
                return complete  # type: ignore[return-value]
        raise


async def chat_with_history(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 16000,
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
    max_tokens: int = 16000,
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

