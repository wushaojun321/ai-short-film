"""Deterministic script indexing.

The index keeps original text blocks addressable so LLM planning can reference
source ranges without rewriting or compressing episode scripts.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from beanie import PydanticObjectId

from app.models.script_block import ScriptBlock, ScriptBlockType


SCRIPT_INDEX_VERSION = "v1"

_EPISODE_RE = re.compile(r"^\s*第\s*([0-9一二三四五六七八九十百千万两〇零]+)\s*[集章节回幕部]")
_SCENE_RE = re.compile(r"^\s*(第\s*[0-9一二三四五六七八九十百千万两〇零]+\s*场|场景\s*[0-9一二三四五六七八九十百千万两〇零]*|[内外景].*[日夜晨昏]|.*[·\-—/].*[日夜晨昏])")
_DIALOGUE_RE = re.compile(r"^\s*([A-Za-z0-9_\-\u4e00-\u9fff（）()·]{1,18})\s*[：:]\s*(.+?)\s*$")
_NON_SPEAKER_PREFIXES = {
    "概述", "核心主旨", "主要人物", "人物小传", "故事梗概", "剧情简介", "分集大纲",
    "场景", "时间", "地点", "主题", "风格", "资产", "道具", "性别", "年龄",
    "身份", "性格", "背景", "第一部分", "第二部分",
    "第三部分", "第四部分", "第五部分",
}

_CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


@dataclass(frozen=True)
class SourceRange:
    start_block: int
    end_block: int


def parse_episode_number(raw: str) -> int | None:
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    total = 0
    section = 0
    number = 0
    units = {"十": 10, "百": 100, "千": 1000}
    for ch in raw:
        if ch in _CN_NUM:
            number = _CN_NUM[ch]
        elif ch in units:
            unit = units[ch]
            section += (number or 1) * unit
            number = 0
        elif ch == "万":
            total += (section + number) * 10000
            section = 0
            number = 0
        else:
            return None
    return total + section + number or None


def _classify_line(text: str) -> tuple[ScriptBlockType, str, int | None]:
    episode_match = _EPISODE_RE.match(text)
    if episode_match:
        return ScriptBlockType.episode_header, "", parse_episode_number(episode_match.group(1))

    dialogue_match = _DIALOGUE_RE.match(text)
    if dialogue_match:
        speaker = dialogue_match.group(1).strip()
        body = dialogue_match.group(2).strip()
        if speaker not in _NON_SPEAKER_PREFIXES and len(body) > 0:
            return ScriptBlockType.dialogue, speaker, None

    if len(text) <= 48 and (_SCENE_RE.match(text) or text.endswith(("内", "外", "夜", "日", "晨", "昏"))):
        return ScriptBlockType.scene_header, "", None

    if text.startswith(("【", "（", "(", "[")) or text.endswith(("。", "！", "？")):
        return ScriptBlockType.action, "", None

    return ScriptBlockType.paragraph, "", None


def build_script_blocks(project_id: PydanticObjectId, script_text: str) -> list[ScriptBlock]:
    blocks: list[ScriptBlock] = []
    char_pos = 0
    current_episode: int | None = None

    for line_no, raw_line in enumerate(script_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        line_start = char_pos
        char_pos += len(raw_line) + 1
        text = raw_line.strip()
        if not text:
            continue

        block_type, speaker, episode_hint = _classify_line(text)
        if block_type == ScriptBlockType.episode_header and episode_hint:
            current_episode = episode_hint

        blocks.append(ScriptBlock.model_construct(
            project_id=project_id,
            block_index=len(blocks),
            block_type=block_type,
            text=text,
            start_line=line_no,
            end_line=line_no,
            char_start=line_start,
            char_end=line_start + len(raw_line),
            speaker=speaker,
            episode_hint=current_episode,
        ))

    return blocks


def explicit_episode_ranges(blocks: list[ScriptBlock]) -> list[SourceRange]:
    headers = [b for b in blocks if b.block_type == ScriptBlockType.episode_header and b.episode_hint]
    if len(headers) < 2:
        return []

    ranges: list[SourceRange] = []
    for idx, header in enumerate(headers):
        next_start = headers[idx + 1].block_index if idx + 1 < len(headers) else len(blocks)
        if next_start > header.block_index:
            ranges.append(SourceRange(header.block_index, next_start - 1))
    return ranges


def fallback_even_ranges(blocks: list[ScriptBlock], target_episodes: int) -> list[SourceRange]:
    if not blocks:
        return []
    target = max(target_episodes, 1)
    size = math.ceil(len(blocks) / target)
    ranges: list[SourceRange] = []
    for start in range(0, len(blocks), size):
        ranges.append(SourceRange(start, min(start + size, len(blocks)) - 1))
    return ranges[:target]


def normalize_ranges(raw_ranges: list[dict], blocks: list[ScriptBlock], target_episodes: int) -> list[SourceRange]:
    ranges: list[SourceRange] = []
    last_end = -1
    max_idx = len(blocks) - 1
    for item in raw_ranges:
        try:
            start = int(item.get("start_block", item.get("start_block_index", 0)))
            end = int(item.get("end_block", item.get("end_block_index", start)))
        except (TypeError, ValueError):
            continue
        start = max(0, min(start, max_idx))
        end = max(start, min(end, max_idx))
        if start <= last_end:
            start = last_end + 1
        if start > max_idx:
            break
        end = max(start, end)
        ranges.append(SourceRange(start, end))
        last_end = end

    if not ranges:
        return fallback_even_ranges(blocks, target_episodes)

    if ranges[0].start_block > 0:
        ranges[0] = SourceRange(0, ranges[0].end_block)
    if ranges[-1].end_block < max_idx and len(ranges) >= target_episodes:
        ranges[-1] = SourceRange(ranges[-1].start_block, max_idx)

    return ranges[:target_episodes]


def build_excerpt(blocks: list[ScriptBlock], source_range: SourceRange) -> tuple[str, list[PydanticObjectId], int, int, int]:
    selected = [b for b in blocks if source_range.start_block <= b.block_index <= source_range.end_block]
    text = "\n".join(b.text for b in selected).strip()
    ids = [b.id for b in selected if b.id]
    start_line = selected[0].start_line if selected else 0
    end_line = selected[-1].end_line if selected else 0
    dialogue_count = sum(1 for b in selected if b.block_type == ScriptBlockType.dialogue)
    return text, ids, start_line, end_line, dialogue_count


def build_index_digest(blocks: list[ScriptBlock], max_chars: int = 18000) -> str:
    lines: list[str] = []
    total = 0
    for block in blocks:
        speaker = f" {block.speaker}：" if block.speaker else " "
        ep = f" ep={block.episode_hint}" if block.episode_hint else ""
        line = f"#{block.block_index} [{block.block_type.value}{ep} L{block.start_line}]{speaker}{block.text}"
        if total + len(line) > max_chars:
            lines.append(f"... 已截断索引摘要，剩余 {len(blocks) - block.block_index} 个原文块仍可按 block_index 引用 ...")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


async def create_script_index(project_id: PydanticObjectId, script_text: str) -> list[ScriptBlock]:
    await ScriptBlock.find(ScriptBlock.project_id == project_id).delete()
    blocks = build_script_blocks(project_id, script_text)
    if blocks:
        docs = [ScriptBlock(**block.model_dump(exclude={"id"})) for block in blocks]
        await ScriptBlock.insert_many(docs)
    return await ScriptBlock.find(ScriptBlock.project_id == project_id).sort("+block_index").to_list()
