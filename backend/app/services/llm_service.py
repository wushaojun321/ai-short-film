"""OpenRouter LLM service with instructor for structured output."""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Any

import httpx
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

_EXTRA_HEADERS = {
    "HTTP-Referer": "https://ai-short-film.local",
    "X-Title": "AI Short Film",
}


def _message_chars(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif content is not None:
            total += len(str(content))
        else:
            total += len(json.dumps(message, ensure_ascii=False, default=str))
    return total


def _usage_value(usage: Any, field: str) -> int | None:
    if not usage:
        return None
    value = getattr(usage, field, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(field)
    return int(value) if value is not None else None


def _object_id_or_none(value: Any):
    if not value:
        return None
    try:
        from beanie import PydanticObjectId
        return PydanticObjectId(str(value))
    except Exception:
        return None


async def _write_call_record(
    *,
    call_type: str,
    scope: str,
    model: str,
    messages: list[dict],
    output_text: str = "",
    max_tokens: int,
    temperature: float,
    duration_ms: int,
    success: bool,
    finish_reason: str = "",
    error: str = "",
    usage: Any = None,
    audit: dict | None = None,
) -> None:
    """Persist lightweight LLM call telemetry without affecting generation."""
    audit = audit or {}
    input_chars = _message_chars(messages)
    output_chars = len(output_text or "")
    logger.info(
        "[LLM CALL] scope=%s type=%s model=%s success=%s input_chars=%d output_chars=%d duration_ms=%d finish=%s",
        scope or "",
        call_type,
        model,
        success,
        input_chars,
        output_chars,
        duration_ms,
        finish_reason or "",
    )
    try:
        from app.models.llm_call_record import LLMCallRecord

        record = LLMCallRecord(
            call_type=call_type,
            scope=scope or "",
            model=model,
            input_chars=input_chars,
            output_chars=output_chars,
            prompt_tokens=_usage_value(usage, "prompt_tokens"),
            completion_tokens=_usage_value(usage, "completion_tokens"),
            total_tokens=_usage_value(usage, "total_tokens"),
            max_tokens=max_tokens,
            temperature=temperature,
            duration_ms=duration_ms,
            success=success,
            finish_reason=finish_reason or "",
            error=error[:500],
            project_id=_object_id_or_none(audit.get("project_id")),
            episode_id=_object_id_or_none(audit.get("episode_id")),
            shot_id=_object_id_or_none(audit.get("shot_id")),
            target_id=_object_id_or_none(audit.get("target_id")),
            meta={k: v for k, v in audit.items() if k not in {"project_id", "episode_id", "shot_id", "target_id"}},
        )
        await record.insert()
    except Exception as exc:
        logger.debug("LLM audit write skipped: %s", exc)


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
    scope: str = "",
    audit: dict | None = None,
) -> str:
    """Simple chat completion, returns raw text."""
    client = get_client()
    actual_model = model or settings.openrouter_model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    started = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=_EXTRA_HEADERS,
        )
    except Exception as exc:
        await _write_call_record(
            call_type="chat_completion",
            scope=scope,
            model=actual_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error=str(exc),
            audit=audit,
        )
        raise
    content = resp.choices[0].message.content or ""
    await _write_call_record(
        call_type="chat_completion",
        scope=scope,
        model=actual_model,
        messages=messages,
        output_text=content,
        max_tokens=max_tokens,
        temperature=temperature,
        duration_ms=int((time.perf_counter() - started) * 1000),
        success=True,
        finish_reason=resp.choices[0].finish_reason or "",
        usage=getattr(resp, "usage", None),
        audit=audit,
    )
    return content


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 32000,
    scope: str = "",
    audit: dict | None = None,
) -> dict:
    """Chat completion expecting JSON response. Returns parsed dict."""
    client = get_client()
    actual_model = model or settings.openrouter_model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    started = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_headers=_EXTRA_HEADERS,
        )
    except Exception as exc:
        await _write_call_record(
            call_type="chat_json",
            scope=scope,
            model=actual_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error=str(exc),
            audit=audit,
        )
        raise
    choice = resp.choices[0]
    content = choice.message.content or "{}"
    await _write_call_record(
        call_type="chat_json",
        scope=scope,
        model=actual_model,
        messages=messages,
        output_text=content,
        max_tokens=max_tokens,
        temperature=temperature,
        duration_ms=int((time.perf_counter() - started) * 1000),
        success=choice.finish_reason != "length",
        finish_reason=choice.finish_reason or "",
        error=(
            "LLM JSON response was truncated before completion."
            if choice.finish_reason == "length" else ""
        ),
        usage=getattr(resp, "usage", None),
        audit=audit,
    )
    if choice.finish_reason == "length":
        raise ValueError(
            "LLM JSON response was truncated before completion. "
            "Increase max_tokens or reduce requested output size."
        )
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        try:
            return await _repair_json(content=content, max_tokens=max_tokens, scope=scope, audit=audit)
        except Exception:
            pass
        preview_start = max(exc.pos - 120, 0)
        preview_end = min(exc.pos + 120, len(content))
        preview = content[preview_start:preview_end].replace("\n", "\\n")
        raise ValueError(
            f"LLM returned invalid JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno} (char {exc.pos}). Around error: {preview}"
        ) from exc


async def _repair_json(content: str, max_tokens: int = 4096, scope: str = "", audit: dict | None = None) -> dict:
    """Ask the model to repair malformed JSON once."""
    client = get_client()
    messages = [
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
    ]
    started = time.perf_counter()
    repair_max_tokens = max(max_tokens, 4096)
    try:
        resp = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=messages,
            temperature=0,
            max_tokens=repair_max_tokens,
            response_format={"type": "json_object"},
            extra_headers=_EXTRA_HEADERS,
        )
    except Exception as exc:
        await _write_call_record(
            call_type="json_repair",
            scope=f"{scope}:json_repair" if scope else "json_repair",
            model=settings.openrouter_model,
            messages=messages,
            max_tokens=repair_max_tokens,
            temperature=0,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error=str(exc),
            audit=audit,
        )
        raise
    repaired = resp.choices[0].message.content or "{}"
    await _write_call_record(
        call_type="json_repair",
        scope=f"{scope}:json_repair" if scope else "json_repair",
        model=settings.openrouter_model,
        messages=messages,
        output_text=repaired,
        max_tokens=repair_max_tokens,
        temperature=0,
        duration_ms=int((time.perf_counter() - started) * 1000),
        success=True,
        finish_reason=resp.choices[0].finish_reason or "",
        usage=getattr(resp, "usage", None),
        audit=audit,
    )
    return json.loads(repaired)


async def chat_with_history(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
    scope: str = "",
    audit: dict | None = None,
) -> str:
    """Multi-turn chat with pre-built messages list."""
    client = get_client()
    actual_model = model or settings.openrouter_model
    started = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=_EXTRA_HEADERS,
        )
    except Exception as exc:
        await _write_call_record(
            call_type="chat_with_history",
            scope=scope,
            model=actual_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error=str(exc),
            audit=audit,
        )
        raise
    content = resp.choices[0].message.content or ""
    await _write_call_record(
        call_type="chat_with_history",
        scope=scope,
        model=actual_model,
        messages=messages,
        output_text=content,
        max_tokens=max_tokens,
        temperature=temperature,
        duration_ms=int((time.perf_counter() - started) * 1000),
        success=True,
        finish_reason=resp.choices[0].finish_reason or "",
        usage=getattr(resp, "usage", None),
        audit=audit,
    )
    return content


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
    scope: str = "",
    audit: dict | None = None,
) -> tuple[str | None, list | None]:
    """
    Single LLM call with tool definitions.
    Returns (text_reply, tool_calls):
      - If LLM returns tool_calls: (None, tool_calls_list)
      - If LLM returns text:       (text, None)
    """
    client = get_client()
    actual_model = model or settings.openrouter_model
    started = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=_EXTRA_HEADERS,
        )
    except Exception as exc:
        await _write_call_record(
            call_type="chat_with_tools",
            scope=scope,
            model=actual_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error=str(exc),
            audit=audit,
        )
        raise
    choice = resp.choices[0]
    msg = choice.message
    text = msg.content or ""
    await _write_call_record(
        call_type="chat_with_tools",
        scope=scope,
        model=actual_model,
        messages=messages,
        output_text=text,
        max_tokens=max_tokens,
        temperature=temperature,
        duration_ms=int((time.perf_counter() - started) * 1000),
        success=True,
        finish_reason=choice.finish_reason or "",
        usage=getattr(resp, "usage", None),
        audit=audit,
    )

    if choice.finish_reason == "tool_calls" and msg.tool_calls:
        return None, msg.tool_calls

    return text, None
