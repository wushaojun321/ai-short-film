"""Deterministic asset image prompt builder.

The asset prompt shown in UI should be the same text submitted to Seedream.
Keep this builder concise and deterministic so generation does not depend on a
second LLM rewrite step.
"""
from __future__ import annotations

import re
from typing import Iterable

from app.models.asset import Asset


ASSET_NEGATIVE_PROMPT = (
    "不要动漫、插画、游戏CG、3D建模、卡通、塑料皮肤、过度磨皮、通用脸、同脸换装、"
    "多视角拼图、三宫格、分屏、模糊、变形、多余肢体、不自然比例"
)


CHARACTER_VIEW_SPECS = {
    "face": {
        "label": "面部特写",
        "instruction": "本次只生成一张面部特写：胸口以上正面近景，五官、骨相、皮肤纹理、胡须/无胡须状态、发型发际线和眼神清晰，服装领口与肩部沿用本阶段造型，不拼接其他视角。若请求包含参考图1，它是同一角色面部基准，必须保留脸型、骨相、五官比例、年龄感和肤色。",
    },
    "full_body": {
        "label": "全身正面",
        "instruction": "本次只生成一张全身正面：从头到脚完整入画，发型、胡须/无胡须状态、服装、妆发、配饰、道具和身形比例清楚，脸部保持同一人物基准。请求参考图1为本阶段面部基准，必须沿用参考图1的同一张脸、发型发际线和胡须/无胡须状态。",
    },
    "side": {
        "label": "侧面视角",
        "instruction": "本次只生成一张侧面或三分之二侧面：脸型轮廓、鼻梁、下颌线、发型、胡须/无胡须状态和服装侧面结构清楚，脸部身份和本阶段造型保持一致。请求参考图1为本阶段面部基准，参考图2为本阶段全身造型；侧面图必须沿用参考图1的脸和参考图2的服装、配饰、伤势、随身道具。",
    },
}


_STYLE_WORDS_TO_DROP = (
    "超现实",
    "梦境",
    "梦幻",
    "二次元",
    "动漫",
    "卡通",
    "插画",
    "游戏CG",
    "CG",
    "3D建模",
    "立绘",
    "设定图",
)


def _asset_type_value(asset: Asset) -> str:
    return asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)


def _single_line(text: str | None, limit: int = 180, *, blocked_words: Iterable[str] = ()) -> str:
    value = (text or "").strip()
    for word in (*_STYLE_WORDS_TO_DROP, *blocked_words):
        word = str(word or "").strip()
        if word:
            value = value.replace(word, "")
    value = re.sub(r"\s+", " ", value)
    value = (
        value.replace("禁止", "")
        .replace("严禁", "")
        .replace("不得", "")
        .replace("不要", "")
        .replace("避免", "")
    )
    value = re.sub(r"(?<=[、，,；;])风(?=[、，,。；;]|$)", "", value)
    value = re.sub(r"[、，,；;]{2,}", "，", value)
    value = re.sub(r"[、，,；;]+(?=[。；;]|$)", "", value)
    value = value.strip(" ，、；;,.。")
    if len(value) > limit:
        return f"{value[:limit].rstrip()}..."
    return value


def _non_empty_parts(*parts: str | None) -> list[str]:
    return [part.strip() for part in parts if part and part.strip()]


def _same_package(asset: Asset, other: Asset) -> bool:
    current = (asset.asset_package or asset.character_name or asset.name or "").strip()
    other_name = (other.asset_package or other.character_name or other.name or "").strip()
    return bool(current and other_name and current == other_name)


def _character_difference_note(asset: Asset, all_assets: list[Asset], blocked_words: Iterable[str]) -> str:
    notes: list[str] = []
    seen: set[str] = set()
    for other in all_assets:
        if str(other.id) == str(asset.id):
            continue
        if _asset_type_value(other) != "character" or _same_package(asset, other):
            continue
        package = _single_line(other.asset_package or other.character_name or other.name, 28, blocked_words=blocked_words)
        if not package or package in seen:
            continue
        seen.add(package)
        identity = _single_line(other.face_identity or other.prompt, 70, blocked_words=blocked_words)
        notes.append(f"{package}（{identity or '独立面部基准'}）")
        if len(notes) >= 4:
            break
    if not notes:
        return "避免通用脸，当前角色要有独立可识别的脸型、五官比例和气质。"
    return f"与其他角色保持可辨差异：{'；'.join(notes)}。"


def _character_stage_lock(asset: Asset, base: str, blocked_words: Iterable[str]) -> str:
    face = _single_line(asset.face_identity, 150, blocked_words=blocked_words)
    stage = _single_line(asset.appearance_stage, 80, blocked_words=blocked_words)
    scene = _single_line(asset.scene_scope, 80, blocked_words=blocked_words)
    styling = _single_line(base, 220, blocked_words=blocked_words)
    lock_parts = _non_empty_parts(
        f"面部基准={face}" if face else "",
        f"阶段={stage}" if stage else "",
        f"场景={scene}" if scene else "",
        f"造型={styling}" if styling else "",
    )
    lock_text = "；".join(lock_parts) or "沿用当前阶段的同一张脸、同一发型、同一服装和同一随身道具。"
    return (
        f"三视图一致性锁定：{lock_text}。"
        "面部特征、年龄感、脸型骨相、五官比例、眉眼鼻唇、皮肤质感、发型发际线、胡须/无胡须状态、"
        "服装款式颜色材质、领口袖口腰带、配饰、伤势、随身道具在面部特写、全身正面、侧面视角三张图中必须完全一致；"
        "只允许相机角度和景别变化，不允许换发型、增减胡须、换衣服、换配饰、换道具、改变伤势或换成另一位演员。"
    )


def build_asset_positive_prompt(
    asset: Asset,
    all_assets: list[Asset] | None = None,
    *,
    blocked_words: Iterable[str] = (),
) -> str:
    """Build the concise positive prompt used as the base submitted prompt."""
    all_assets = all_assets or []
    asset_type = _asset_type_value(asset)
    name = _single_line(asset.name, 60, blocked_words=blocked_words)
    base = _single_line(asset.prompt, 260, blocked_words=blocked_words)

    if asset_type == "character":
        package = _single_line(asset.asset_package or asset.character_name or asset.name, 50, blocked_words=blocked_words)
        face = _single_line(
            asset.face_identity or "稳定中国真人面孔，五官比例自然，骨相清楚，皮肤纹理真实，同一人物资产包内保持一致",
            170,
            blocked_words=blocked_words,
        )
        scene = _single_line(asset.scene_scope or "按剧本主要场景", 90, blocked_words=blocked_words)
        stage = _single_line(asset.appearance_stage or "当前剧情阶段", 90, blocked_words=blocked_words)
        stage_lock = _character_stage_lock(asset, base, blocked_words)
        difference = _character_difference_note(asset, all_assets, blocked_words)
        parts = [
            f"竖屏9:16，写实电影人物定妆参考照，{name}。",
            f"角色资产包：{package}；同组所有造型沿用同一面部基准：{face}。",
            f"当前阶段：{stage}；适用场景：{scene}。",
            f"造型重点：{base}。" if base else "",
            stage_lock,
            "真实演员摄影，影视布光，真实皮肤纹理、自然毛孔和真实织物材质，克制电影色调。",
            difference,
        ]
        return "\n".join(_non_empty_parts(*parts))

    if asset_type == "scene":
        parts = [
            f"竖屏9:16，写实影视场景参考照，{name}。",
            f"场景重点：{base}。" if base else "",
            "真实空间透视，真实建筑和环境材质，影视布光，电影色调，主体清晰，适合作为短剧镜头参考。",
        ]
        return "\n".join(_non_empty_parts(*parts))

    if asset_type == "prop":
        parts = [
            f"竖屏9:16，写实道具摄影参考照，{name}。",
            f"道具重点：{base}。" if base else "",
            "真实材质、颜色、磨损和使用痕迹清楚，棚拍式影视布光，主体完整清晰，背景简洁。",
        ]
        return "\n".join(_non_empty_parts(*parts))

    parts = [
        f"竖屏9:16，写实电影参考图，{name}。",
        f"重点：{base}。" if base else "",
        "真实摄影基础，影视布光，真实材质，电影色调，主体清晰。",
    ]
    return "\n".join(_non_empty_parts(*parts))


def _with_negative(prompt: str, *, blocked_words: Iterable[str] = ()) -> str:
    blocked = [_single_line(word, 20) for word in blocked_words if str(word or "").strip()]
    blocked_note = f"，规避已触发审核的词汇" if blocked else ""
    return f"{prompt.strip()}\n\n反向约束：{ASSET_NEGATIVE_PROMPT}{blocked_note}。"


def build_asset_submitted_prompts(
    asset: Asset,
    all_assets: list[Asset] | None = None,
    *,
    blocked_words: Iterable[str] = (),
) -> tuple[str, dict[str, str]]:
    """Return combined submitted prompt and per-view prompts for character assets."""
    positive = build_asset_positive_prompt(asset, all_assets, blocked_words=blocked_words)
    if _asset_type_value(asset) != "character":
        return _with_negative(positive, blocked_words=blocked_words), {}

    submitted_prompts: dict[str, str] = {}
    for view_key, spec in CHARACTER_VIEW_SPECS.items():
        submitted_prompts[view_key] = _with_negative(
            f"{positive}\n{spec['instruction']}",
            blocked_words=blocked_words,
        )
    combined = "\n\n---\n\n".join(
        f"{CHARACTER_VIEW_SPECS[key]['label']}：\n{prompt}"
        for key, prompt in submitted_prompts.items()
        if prompt
    )
    return combined, submitted_prompts
