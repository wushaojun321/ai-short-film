from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.utils.script_indexer import (
    SCRIPT_INDEX_VERSION,
    build_index_digest,
    create_script_index,
    explicit_episode_ranges,
)


DIRECT_INDEX_THRESHOLD = 50000


@dataclass
class ScriptContextPack:
    script_len: int
    blocks: list
    explicit_ranges: list
    target_count: int
    script_index: str
    suggested_ranges: list


class ScriptContextPackBuilder:
    """Build the only context package sent to the global blueprint planner."""

    async def build(self, project) -> ScriptContextPack:
        script_text = project.script_text or ""
        blocks = await create_script_index(project.id, script_text)
        if not blocks:
            raise ValueError("Script index is empty")

        await project.set({
            "script_index_version": SCRIPT_INDEX_VERSION,
            "script_indexed_at": datetime.utcnow(),
        })

        explicit_ranges = explicit_episode_ranges(blocks)
        target_count = project.target_episode_count or len(explicit_ranges) or 1
        script_len = len(script_text)
        digest_limit = (
            min(max(script_len * 3, 22000), 140000)
            if script_len <= DIRECT_INDEX_THRESHOLD
            else 90000
        )
        script_index = build_index_digest(blocks, max_chars=digest_limit)

        return ScriptContextPack(
            script_len=script_len,
            blocks=blocks,
            explicit_ranges=explicit_ranges,
            target_count=target_count,
            script_index=script_index,
            suggested_ranges=explicit_ranges if explicit_ranges else [],
        )
