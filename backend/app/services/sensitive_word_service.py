"""Global sensitive word blocklist service.

Words are stored in MongoDB `sensitive_words` collection (no Beanie model needed).
They are learned automatically when Seedream/Seedance returns InputTextSensitiveContentDetected.
"""
from __future__ import annotations
from datetime import datetime


def _get_collection():
    """Get motor collection after beanie/db is initialised.

    Reuse the motor client that beanie already has via any registered Document's
    pymongo collection → extract the database → access sensitive_words.
    """
    from app.models.task_record import TaskRecord  # any beanie Document
    pymongo_col = TaskRecord.get_pymongo_collection()
    # pymongo_col.database is a motor AsyncIOMotorDatabase
    return pymongo_col.database["sensitive_words"]


async def _ensure_index() -> None:
    col = _get_collection()
    await col.create_index("word", unique=True, background=True)


async def get_all_words() -> list[str]:
    """Return all known sensitive words."""
    col = _get_collection()
    docs = await col.find({}, {"word": 1, "_id": 0}).to_list(None)
    return [d["word"] for d in docs]


async def add_words(words: list[str], source: str = "unknown", prompt_snippet: str = "") -> None:
    """Upsert a list of words into the blocklist."""
    if not words:
        return
    col = _get_collection()
    await _ensure_index()
    now = datetime.utcnow()
    snippet = prompt_snippet[:150]
    for word in words:
        w = word.strip()
        if not w:
            continue
        await col.update_one(
            {"word": w},
            {
                "$setOnInsert": {
                    "word": w,
                    "source": source,
                    "prompt_snippet": snippet,
                    "created_at": now,
                }
            },
            upsert=True,
        )


async def extract_and_save(prompt: str, source: str) -> list[str]:
    """Ask LLM to infer which words in *prompt* likely triggered content moderation,
    persist them to the blocklist, and return the extracted word list.
    """
    from app.services import llm_service

    system = (
        "你是中国内容审核专家。"
        "请从下方 AI 图像/视频生成提示词中，找出可能触发中国内容平台审核的词语或短语。"
        "常见触发类型：金融专业术语（K线、大阳线、涨停、比特币等）、"
        "真实人名（名人/企业家）、公司/品牌名、特定虚构IP名称、政治敏感词。"
        "只列出你认为有风险的词，不要列出普通描述词。"
        '输出 JSON：{"words": ["词1", "词2", ...]}'
    )
    user = f"提示词：\n{prompt[:800]}"

    words: list[str] = []
    try:
        raw = await llm_service.chat_json(system_prompt=system, user_prompt=user)
        if isinstance(raw, str):
            import json
            raw = json.loads(raw)
        words = [str(w).strip() for w in raw.get("words", []) if str(w).strip()]
    except Exception:
        pass  # extraction failure is non-fatal

    if words:
        await add_words(words, source=source, prompt_snippet=prompt[:150])

    return words
