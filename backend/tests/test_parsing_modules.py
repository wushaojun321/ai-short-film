from beanie import PydanticObjectId

from app.parsing.blueprint_validator import BlueprintSchemaValidator
from app.parsing.parse_report_builder import ParseReportBuilder
from app.parsing.range_utils import extract_minimum_ranges_from_episode_plan
from app.utils.script_indexer import build_script_blocks


def test_blueprint_validator_accepts_episode_block_ranges():
    project_id = PydanticObjectId()
    blocks = build_script_blocks(project_id, "第1集\n秦川：收到。\n第2集\n林晚照：明白。")
    plan = {
        "series": {"series_prompt": "写实电影质感"},
        "episodes": [
            {"number": 1, "source_block_ranges": [{"start_block": 0, "end_block": 1}]},
            {"number": 2, "source_block_ranges": [{"start_block": 2, "end_block": 3}]},
        ],
        "asset_registry": {"characters": [], "scenes": [], "props": []},
    }

    result = BlueprintSchemaValidator().validate(plan, blocks, 2)

    assert len(result.planned_ranges) == 2
    assert not result.warnings


def test_range_extraction_keeps_more_than_minimum_episodes():
    project_id = PydanticObjectId()
    blocks = build_script_blocks(project_id, "第1集\nA\n第2集\nB\n第3集\nC")
    episodes = [
        {"number": 1, "source_block_ranges": [{"start_block": 0, "end_block": 1}]},
        {"number": 2, "source_block_ranges": [{"start_block": 2, "end_block": 3}]},
        {"number": 3, "source_block_ranges": [{"start_block": 4, "end_block": 5}]},
    ]

    ranges = extract_minimum_ranges_from_episode_plan(episodes, blocks, minimum_count=2)

    assert len(ranges) == 3
    assert ranges[-1].end_block == len(blocks) - 1


def test_range_extraction_rejects_less_than_minimum_episodes():
    project_id = PydanticObjectId()
    blocks = build_script_blocks(project_id, "第1集\nA\n第2集\nB")
    episodes = [
        {"number": 1, "source_block_ranges": [{"start_block": 0, "end_block": 1}]},
    ]

    ranges = extract_minimum_ranges_from_episode_plan(episodes, blocks, minimum_count=2)

    assert ranges == []


def test_blueprint_validator_warns_without_episodes():
    project_id = PydanticObjectId()
    blocks = build_script_blocks(project_id, "第一行\n第二行")

    result = BlueprintSchemaValidator().validate({}, blocks, 1)

    assert result.planned_ranges == []
    assert any("episode" in warning for warning in result.warnings)
    assert result.plan["continuity_report"]["status"] == "needs_review"


def test_parse_report_builder_summarizes_counts():
    report = ParseReportBuilder().build(
        episodes=[
            {"dialogue_count": 2, "source_integrity": "original"},
            {"dialogue_count": 3, "source_integrity": "original"},
        ],
        assets={"characters": [{"name": "秦川"}], "scenes": [], "props": [{"name": "密令"}]},
        series={"series_prompt": "写实电影质感"},
        blueprint_id="blueprint-id",
        continuity_report={"warnings": []},
    )

    assert report["parse_report"]["episode_count"] == 2
    assert report["parse_report"]["asset_count"] == 2
    assert report["parse_report"]["dialogue_count"] == 5
    assert report["parse_report"]["source_integrity"] == "original"
