"""Tests for deterministic asset prompt generation."""
from beanie import PydanticObjectId

from app.models.asset import Asset, AssetType
from app.services.asset_prompt_builder import build_asset_submitted_prompts


def test_character_prompt_uses_identity_difference_and_look_locks():
    asset = Asset.model_construct(
        id=PydanticObjectId("000000000000000000000001"),
        project_id=PydanticObjectId("000000000000000000000000"),
        name="秦川-指挥官常规状态",
        asset_type=AssetType.character,
        prompt="深灰作战服，黑色战术背心，左肩无线电",
        character_name="秦川",
        asset_package="秦川",
        face_identity="方脸，低眉骨，薄唇，左眉尾旧疤",
        distinctive_traits=["方脸低眉骨", "左眉尾旧疤", "薄唇"],
        avoid_similar_to=["避免像温和书生脸"],
        look_lock="短寸发，无胡须，深灰作战服，黑色战术背心，左肩无线电",
    )

    submitted_prompt, submitted_prompts = build_asset_submitted_prompts(asset, [asset])

    assert set(submitted_prompts) == {"face", "full_body", "side"}
    assert "三视图一致性锁定" in submitted_prompt
    assert "短寸发" in submitted_prompt
    assert "深灰作战服" in submitted_prompt
    assert "左眉尾旧疤" in submitted_prompt
    assert "当前角色固定差异点" in submitted_prompt
