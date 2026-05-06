from __future__ import annotations

from app.utils.script_indexer import SourceRange


def extract_minimum_ranges_from_episode_plan(episodes_data: list[dict], blocks: list, minimum_count: int) -> list[SourceRange]:
    """Extract monotonic source ranges and accept any count >= minimum_count.

    The parse UI now treats the episode count as a lower bound. If the source
    script or LLM plan naturally yields more episodes, keep them instead of
    truncating to an exact target count.
    """
    if not blocks:
        return []

    raw_ranges: list[dict] = []
    for episode in episodes_data:
        ranges = episode.get("source_block_ranges") or episode.get("source_ranges") or []
        if isinstance(ranges, list) and ranges:
            starts, ends = [], []
            for item in ranges:
                if isinstance(item, dict):
                    starts.append(item.get("start_block", item.get("start_block_index")))
                    ends.append(item.get("end_block", item.get("end_block_index")))
            try:
                raw_ranges.append({
                    "start_block": min(int(value) for value in starts),
                    "end_block": max(int(value) for value in ends),
                })
            except (TypeError, ValueError):
                continue
        elif "start_block" in episode or "end_block" in episode:
            raw_ranges.append(episode)

    ranges = normalize_minimum_ranges(raw_ranges, blocks)
    minimum = max(minimum_count, 1)
    return ranges if len(ranges) >= minimum else []


def normalize_minimum_ranges(raw_ranges: list[dict], blocks: list) -> list[SourceRange]:
    if not raw_ranges or not blocks:
        return []

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
        ranges.append(SourceRange(start, end))
        last_end = end

    if not ranges:
        return []

    if ranges[0].start_block > 0:
        ranges[0] = SourceRange(0, ranges[0].end_block)
    if ranges[-1].end_block < max_idx:
        ranges[-1] = SourceRange(ranges[-1].start_block, max_idx)

    return ranges
