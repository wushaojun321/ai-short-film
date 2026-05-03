"""Unit tests for continuity planning helpers."""
from app.tasks.llm_tasks import _extract_shot_list, _infer_transition_type
from app.tasks.video_tasks import _needs_side_reference


def test_infer_transition_type_from_explicit_value():
    assert _infer_transition_type("", "", {}, {"transition_type": "crossfade"}) == "crossfade"


def test_infer_transition_type_from_text():
    assert _infer_transition_type("承接上一镜台词尾音", "", {}, {}) == "audio_bridge"
    assert _infer_transition_type("动作连续", "以手中玉佩匹配切", {}, {}) == "match_cut"
    assert _infer_transition_type("三日后黑场转入", "", {}, {}) == "black_gap"


def test_extract_segments_shape_for_repair_output():
    result = {
        "segments": [
            {
                "segment_code": "SEG01",
                "shots": [
                    {"shot_code": "SEG01-S01", "description": "建立镜"},
                    {"shot_code": "SEG01-S02", "description": "反应镜"},
                ],
            }
        ],
        "issues": [{"shot_code": "SEG01-S02", "message": "已修复承接"}],
    }
    flattened = _extract_shot_list(result)
    assert len(flattened) == 2
    assert flattened[0][0]["segment_code"] == "SEG01"
    assert flattened[1][1]["shot_code"] == "SEG01-S02"


def test_side_reference_detection():
    assert _needs_side_reference("近景侧脸，角色缓慢回头")
    assert not _needs_side_reference("正面中景，两人对峙")
