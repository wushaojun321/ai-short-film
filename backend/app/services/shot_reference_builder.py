"""Build structured shot reference context for video prompt generation."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.asset import Asset, AssetType
from app.models.shot import Shot
from app.services.storage_service import presign_if_cos


class ShotReferenceBuildResult(BaseModel):
    character_prompts: str = "无"
    scene_prompt: str = "无"
    prop_prompts: str = "无"
    asset_contract: str = "无"
    voice_profiles: str = "无可用角色音色设定；按角色身份保持自然、稳定、写实的中文声线。"
    voice_profile_map: dict[str, str] = Field(default_factory=dict)
    reference_image_block: str = "无"
    direct_reference_section: str = "【直接参考图片】\n无可用参考图片"
    reference_images: list[str] = Field(default_factory=list)
    previous_last_frame_label: str = "无"
    visible_character_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def should_use_prev_last_frame(shot: Shot, prev_shot: Shot | None) -> bool:
    if not prev_shot or not getattr(prev_shot, "last_frame_url", None):
        return False
    if getattr(shot, "use_prev_last_frame", False):
        return True
    return bool(shot.segment_code and prev_shot.segment_code == shot.segment_code)


def fallback_voice_profile(name: str, prompt: str = "") -> str:
    base = prompt or name
    if any(word in base for word in ("女性", "女子", "公主", "长公主", "皇后", "侍女")):
        return f"{name}固定音色：成年女性声线，吐字清晰，情绪随剧情变化但年龄感和音色质感保持一致，不要变成少女撒娇音，不要尖叫失真。"
    if any(word in base for word in ("少年", "年轻")):
        return f"{name}固定音色：年轻男性声线，清晰自然，语速稳定，情绪表达克制，不要变成女性音色或夸张动漫腔。"
    return f"{name}固定音色：成年男性声线，音色稳定，吐字清晰，语速中等，情绪克制，不要变成女性音色，不要忽高忽低。"


def _needs_side_reference(shot_description: str, transition_text: str = "") -> bool:
    text = f"{shot_description} {transition_text}"
    return any(word in text for word in ("侧面", "侧脸", "侧身", "三分之二侧", "回头", "转身", "背身"))


def _append_reference_image(
    *,
    reference_images: list[str],
    reference_image_parts: list[str],
    reference_lookup: dict[str, str],
    url: str | None,
    label: str,
    asset_type_label: str,
    max_images: int = 9,
) -> str | None:
    if not url:
        return None
    presigned_url = presign_if_cos(url)
    if presigned_url in reference_lookup:
        return reference_lookup[presigned_url]
    if len(reference_images) >= max_images:
        return None
    image_index = len(reference_images) + 1
    image_label = f"[图{image_index}]"
    reference_images.append(presigned_url)
    reference_lookup[presigned_url] = image_label
    reference_image_parts.append(f"{image_label} {label}（{asset_type_label}）")
    return image_label


def _provider_view_url(asset: Asset, view_type: str) -> str:
    return (asset.provider_view_urls or {}).get(view_type) or ""


def _provider_preview_url(asset: Asset) -> str:
    return asset.provider_preview_url or ""


class ShotReferenceBuilder:
    """Build reference images, asset contract, voice profiles and preflight warnings."""

    async def build(self, shot: Shot) -> ShotReferenceBuildResult:
        from beanie import PydanticObjectId

        warnings: list[str] = []
        character_parts: list[str] = []
        scene_parts: list[str] = []
        prop_parts: list[str] = []
        asset_contract_parts: list[str] = []
        voice_profile_parts: list[str] = []
        voice_profile_map: dict[str, str] = {}
        visible_character_names: list[str] = []
        reference_image_parts: list[str] = []
        reference_images: list[str] = []
        reference_lookup: dict[str, str] = {}

        if shot.required_assets:
            asset_ids = [binding.asset_id for binding in shot.required_assets]
            assets = await Asset.find({"_id": {"$in": asset_ids}}).to_list()
            asset_map = {str(asset.id): asset for asset in assets}
        else:
            asset_map = {}
            warnings.append("镜头未绑定任何资产，视频提示词只能依赖文字描述。")

        project_assets = await Asset.find(Asset.project_id == shot.project_id).to_list()
        package_face_refs: dict[str, str] = {}
        for asset in project_assets:
            if asset.asset_type != AssetType.character:
                continue
            package_key = asset.asset_package or asset.character_name or asset.name
            face_url = _provider_view_url(asset, "face") or (asset.view_urls or {}).get("face")
            if package_key and face_url and package_key not in package_face_refs:
                package_face_refs[package_key] = face_url

        side_reference_needed = _needs_side_reference(
            shot.description,
            f"{shot.transition_in} {shot.transition_out} {shot.start_state} {shot.end_state}",
        )

        has_scene = False
        for binding in shot.required_assets:
            asset = asset_map.get(str(binding.asset_id))
            if not asset:
                warnings.append(f"资产绑定无法解析：{binding.asset_name}")
                continue

            asset_type_label = {
                AssetType.character: "人物",
                AssetType.scene: "场景",
                AssetType.prop: "道具",
                AssetType.template: "模板",
            }.get(asset.asset_type, "资产")
            required_views = binding.required_views or []
            binding_ref_labels: list[str] = []

            if asset.asset_type == AssetType.character:
                package_key = asset.asset_package or asset.character_name or asset.name
                provider_face_url = _provider_view_url(asset, "face")
                provider_full_body_url = _provider_view_url(asset, "full_body") or _provider_preview_url(asset)
                provider_side_url = _provider_view_url(asset, "side")
                identity_face_url = provider_face_url or (asset.view_urls or {}).get("face") or package_face_refs.get(package_key)
                current_look_url = provider_full_body_url or (asset.view_urls or {}).get("full_body") or asset.preview_url
                side_url = provider_side_url or (asset.view_urls or {}).get("side")

                if not identity_face_url:
                    warnings.append(f"人物资产缺少面部锚点：{asset.name}")
                if not current_look_url:
                    warnings.append(f"人物资产缺少当前造型参考图：{asset.name}")
                if not provider_face_url or not provider_full_body_url:
                    warnings.append(f"人物资产缺少方舟原始产物 URL，将回退 COS URL，可能触发 Seedance 人脸素材审核：{asset.name}")

                if not required_views or "face" in required_views:
                    face_ref = _append_reference_image(
                        reference_images=reference_images,
                        reference_image_parts=reference_image_parts,
                        reference_lookup=reference_lookup,
                        url=identity_face_url,
                        label=f"{asset.name}-身份面部锚点",
                        asset_type_label=asset_type_label,
                    )
                    if face_ref:
                        binding_ref_labels.append(face_ref)

                if not required_views or "full_body" in required_views or "body" in required_views:
                    look_ref = _append_reference_image(
                        reference_images=reference_images,
                        reference_image_parts=reference_image_parts,
                        reference_lookup=reference_lookup,
                        url=current_look_url,
                        label=f"{asset.name}-当前造型",
                        asset_type_label=asset_type_label,
                    )
                    if look_ref:
                        binding_ref_labels.append(look_ref)

                if ("side" in required_views or side_reference_needed) and side_url:
                    side_ref = _append_reference_image(
                        reference_images=reference_images,
                        reference_image_parts=reference_image_parts,
                        reference_lookup=reference_lookup,
                        url=side_url,
                        label=f"{asset.name}-侧面轮廓辅助",
                        asset_type_label=asset_type_label,
                    )
                    if side_ref:
                        binding_ref_labels.append(side_ref)

                character_name = binding.character_name or asset.character_name or asset.name
                if character_name not in visible_character_names:
                    visible_character_names.append(character_name)
                refs = "".join(binding_ref_labels) or "无图"
                voice_profile = asset.voice_profile or fallback_voice_profile(character_name, asset.prompt)
                for key in {asset.name, character_name, asset.character_name, asset.asset_package}:
                    if key:
                        voice_profile_map[key] = voice_profile
                voice_profile_parts.append(f"{character_name}：{voice_profile}")
                character_parts.append(
                    f"{refs}{asset.name}（人物；角色：{character_name}；资产包：{asset.asset_package or character_name}；"
                    f"阶段：{asset.appearance_stage or binding.appearance_stage or '未标注'}；"
                    f"镜头职责：{binding.role_in_shot or '画面人物'}；位置：{binding.screen_position or '按分镜'}；"
                    f"动作：{binding.action_requirement or '按分镜描述'}；"
                    f"表情：{binding.expression_requirement or '按分镜描述'}；"
                    f"一致性：{binding.continuity_requirement or '按参考图保持同一张脸和当前造型'}）"
                )
                asset_contract_parts.append(
                    f"- 人物 {character_name}：参考 {refs}；资产 {asset.name}；角色职责 {binding.role_in_shot or '画面人物'}；"
                    f"画面位置 {binding.screen_position or '按分镜'}；"
                    f"{'本镜开口说话' if binding.speaking else '本镜不得开口，保持无声反应' if binding.muted else '按 dialogues 判断是否开口'}；"
                    f"动作 {binding.action_requirement or '按分镜描述'}；"
                    f"表情 {binding.expression_requirement or '按分镜描述'}；"
                    f"连续性 {binding.continuity_requirement or '按参考图保持人脸、服装、伤势、道具状态一致'}"
                )

            elif asset.asset_type == AssetType.scene:
                has_scene = True
                ref = _append_reference_image(
                    reference_images=reference_images,
                    reference_image_parts=reference_image_parts,
                    reference_lookup=reference_lookup,
                    url=asset.preview_url,
                    label=asset.name,
                    asset_type_label=asset_type_label,
                )
                ref_text = ref or "无图"
                scene_parts.append(
                    f"{ref_text}{asset.name}（场景；用途：{binding.reference_purpose or 'scene_space'}；"
                    f"位置：{binding.screen_position or '画面空间'}；"
                    f"连续性：{binding.continuity_requirement or '保持空间结构、光线和时代质感'}）"
                )
                asset_contract_parts.append(
                    f"- 场景 {asset.name}：参考 {ref_text}；作为空间锚点；"
                    f"连续性 {binding.continuity_requirement or '保持空间结构、光线、材质和时代质感'}"
                )

            elif asset.asset_type == AssetType.prop:
                ref = _append_reference_image(
                    reference_images=reference_images,
                    reference_image_parts=reference_image_parts,
                    reference_lookup=reference_lookup,
                    url=asset.preview_url,
                    label=asset.name,
                    asset_type_label=asset_type_label,
                )
                ref_text = ref or "无图"
                prop_parts.append(
                    f"{ref_text}{asset.name}（道具；用途：{binding.reference_purpose or 'prop_detail'}；"
                    f"动作：{binding.action_requirement or '按分镜'}；"
                    f"连续性：{binding.continuity_requirement or '保持道具外观和持有关系'}）"
                )
                asset_contract_parts.append(
                    f"- 道具 {asset.name}：参考 {ref_text}；"
                    f"动作/位置 {binding.action_requirement or binding.screen_position or '按分镜'}；"
                    f"连续性 {binding.continuity_requirement or '保持外观、材质、尺寸和持有关系'}"
                )

        dependency_shot = None
        if getattr(shot, "depends_on_last_frame_shot_id", None):
            dependency_shot = await Shot.get(PydanticObjectId(str(shot.depends_on_last_frame_shot_id)))

        prev_shots = await Shot.find(
            Shot.episode_id == shot.episode_id,
            Shot.order < shot.order,
        ).sort("-order").limit(1).to_list()
        prev_shot = dependency_shot or (prev_shots[0] if prev_shots else None)
        previous_last_frame_label = "无"
        if should_use_prev_last_frame(shot, prev_shot):
            last_frame_ref = _append_reference_image(
                reference_images=reference_images,
                reference_image_parts=reference_image_parts,
                reference_lookup=reference_lookup,
                url=prev_shot.last_frame_url,
                label="上一镜尾帧（仅作连续性辅助）",
                asset_type_label="连续性",
            )
            previous_last_frame_label = f"{last_frame_ref} 上一镜尾帧（仅作连续性辅助）" if last_frame_ref else "上一镜尾帧不可用"

        if not has_scene:
            warnings.append("镜头未绑定场景资产，可能影响空间连续性。")

        dialogue_speakers = [d.speaker for d in shot.dialogues if d.speaker]
        for speaker in dialogue_speakers:
            if speaker not in voice_profile_map:
                warnings.append(f"台词说话人未绑定人物资产或音色：{speaker}")

        if reference_images and len(reference_images) >= 9 and len(reference_image_parts) >= 9:
            warnings.append("参考图已达到 Seedance 当前上限 9 张，后续资产参考可能被截断。")

        reference_image_block = "\n".join(reference_image_parts) if reference_image_parts else "无"
        direct_reference_section = (
            "【直接参考图片】\n"
            f"{reference_image_block}\n"
            "生成时必须按上方图号直接参考请求体中的 reference_image。角色资产和场景资产是身份与空间锚点，上一镜尾帧如存在，只用于动作、站位、光线和情绪承接。"
            if reference_image_parts
            else "【直接参考图片】\n无可用参考图片"
        )

        return ShotReferenceBuildResult(
            character_prompts="\n".join(character_parts) if character_parts else "无",
            scene_prompt="\n".join(scene_parts) if scene_parts else "无",
            prop_prompts="\n".join(prop_parts) if prop_parts else "无",
            asset_contract="\n".join(asset_contract_parts) if asset_contract_parts else "无",
            voice_profiles="\n".join(dict.fromkeys(voice_profile_parts)) if voice_profile_parts else "无可用角色音色设定；按角色身份保持自然、稳定、写实的中文声线。",
            voice_profile_map=voice_profile_map,
            reference_image_block=reference_image_block,
            direct_reference_section=direct_reference_section,
            reference_images=reference_images,
            previous_last_frame_label=previous_last_frame_label,
            visible_character_names=visible_character_names,
            warnings=warnings,
        )
