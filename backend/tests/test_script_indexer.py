import pytest
from beanie import PydanticObjectId

from app.models.script_block import ScriptBlockType
from app.utils.script_indexer import (
    build_excerpt,
    build_script_blocks,
    explicit_episode_ranges,
    fallback_even_ranges,
    normalize_ranges,
    parse_episode_number,
)


def test_parse_episode_number_supports_chinese_and_digits():
    assert parse_episode_number("1") == 1
    assert parse_episode_number("一") == 1
    assert parse_episode_number("十") == 10
    assert parse_episode_number("二十一") == 21


def test_script_indexer_recognizes_episode_dialogue_and_paragraph():
    project_id = PydanticObjectId()
    text = "\n".join([
        "第1集：冷卫入府",
        "长公主府 夜",
        "李云湘：你是谁派来的？",
        "谢风凌低头不语。",
        "性格：冷静克制",
    ])

    blocks = build_script_blocks(project_id, text)

    assert [b.block_type for b in blocks] == [
        ScriptBlockType.episode_header,
        ScriptBlockType.scene_header,
        ScriptBlockType.dialogue,
        ScriptBlockType.action,
        ScriptBlockType.paragraph,
    ]
    assert blocks[2].speaker == "李云湘"
    assert blocks[2].episode_hint == 1


def test_explicit_ranges_and_excerpt_preserve_original_dialogue():
    project_id = PydanticObjectId()
    text = "\n".join([
        "第1集：冷卫入府",
        "李云湘：你是谁派来的？",
        "谢风凌：奉旨护卫。",
        "第2集：赈粮交锋",
        "李睿：赈粮账册呢？",
    ])
    blocks = build_script_blocks(project_id, text)

    ranges = explicit_episode_ranges(blocks)
    assert len(ranges) == 2

    excerpt, _, start_line, end_line, dialogue_count = build_excerpt(blocks, ranges[0])
    assert "李云湘：你是谁派来的？" in excerpt
    assert "谢风凌：奉旨护卫。" in excerpt
    assert start_line == 1
    assert end_line == 3
    assert dialogue_count == 2


def test_normalize_ranges_falls_back_without_valid_llm_ranges():
    project_id = PydanticObjectId()
    blocks = build_script_blocks(project_id, "第一行\n第二行\n第三行\n第四行")

    ranges = normalize_ranges([], blocks, 2)
    fallback = fallback_even_ranges(blocks, 2)

    assert ranges == fallback
    assert ranges[0].start_block == 0
    assert ranges[-1].end_block == len(blocks) - 1
