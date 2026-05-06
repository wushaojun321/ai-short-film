from beanie import PydanticObjectId

from app.parsing.blueprint_validator import BlueprintSchemaValidator
from app.parsing.parse_report_builder import ParseReportBuilder
from app.parsing.range_utils import extract_minimum_ranges_from_episode_plan
from app.tasks.llm_tasks import _jsonl_plan_from_text
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


def test_jsonl_plan_accepts_asset_first_episode_later_order():
    raw = "\n".join([
        '{"type":"series","series_prompt":"写实电影质感","main_storyline":"主线","continuity_notes":"连续性"}',
        '{"type":"character","name":"秦川","package":"秦川","role":"指挥官","importance":"lead","episodes":"1-2","face":"方脸短发","distinctive_traits":["高鼻梁"],"avoid_similar_to":["林晚照"],"voice":"低沉"}',
        '{"type":"character_variant","character":"秦川","name":"秦川-战场","level":"must_build","episodes":"1-2","scene":"战场","state":"军装","reason":"主线","look_lock":"短发、无胡须、深色军装","prompt_seed":"写实电影质感人物"}',
        '{"type":"scene","name":"城门","package":"城门","importance":"core","episodes":"1-2"}',
        '{"type":"scene_variant","scene":"城门","name":"城门-战损","level":"must_build","episodes":"1-2","state":"战损","reason":"反复出现","prompt_seed":"写实影视场景"}',
        '{"type":"prop","name":"密令","package":"密令","importance":"key","episodes":"1-2","owner":"秦川"}',
        '{"type":"prop_variant","prop":"密令","name":"密令-染血","level":"must_build","episodes":"2","state":"染血","owner":"秦川","reason":"推动剧情","prompt_seed":"写实道具摄影"}',
        '{"type":"episode","number":1,"title":"第一集","summary":"城门开战","start_block":0,"end_block":3,"estimated_duration":120,"beats":["开战"],"hook":"密令出现"}',
    ])

    plan, stats = _jsonl_plan_from_text(raw)

    assert stats["parsed"] == 8
    assert plan["episodes"][0]["title"] == "第一集"
    assert plan["asset_registry"]["characters"][0]["variants"][0]["look_lock"] == "短发、无胡须、深色军装"
    assert plan["asset_registry"]["scenes"][0]["variants"][0]["name"] == "城门-战损"
    assert plan["asset_registry"]["props"][0]["variants"][0]["name"] == "密令-染血"


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
