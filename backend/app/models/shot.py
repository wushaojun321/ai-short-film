from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class ShotState(str, Enum):
    planned        = "planned"
    asset_required = "asset_required"
    generating     = "generating"   # image generating
    asset_ready    = "asset_ready"
    rendering      = "rendering"    # video generating
    rendered       = "rendered"
    review_failed  = "review_failed"
    approved       = "approved"


class ShotAssetBinding(BaseModel):
    asset_id: PydanticObjectId
    asset_name: str
    asset_type: str = ""
    role_in_shot: str = ""          # main_actor / speaker / listener / background / scene / prop
    character_name: str = ""
    asset_package: str = ""
    appearance_stage: str = ""
    reference_purpose: str = ""     # identity / costume / scene_space / prop_detail / continuity
    required_views: list[str] = Field(default_factory=list)  # face / full_body / side / preview
    screen_position: str = ""
    action_requirement: str = ""
    expression_requirement: str = ""
    continuity_requirement: str = ""
    voice_required: bool = False
    speaking: bool = False
    muted: bool = False
    binding_source: str = "llm"     # llm / auto / manual
    confidence: float = 1.0


class ShotDialogueLine(BaseModel):
    speaker: str = ""
    text: str = ""
    emotion: str = ""
    delivery: str = ""
    action: str = ""
    expression: str = ""


class ShotVersion(BaseModel):
    version: str
    video_url: str
    last_frame_url: Optional[str] = None
    prompt: str = ""
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Shot(Document):
    project_id: PydanticObjectId
    episode_id: PydanticObjectId
    shot_code: str                         # "S01", "S02" ...
    order: int
    duration: int = 5
    segment_code: str = ""
    segment_name: str = ""
    segment_function: str = ""
    shot_function: str = ""
    transition_in: str = ""
    transition_out: str = ""
    transition_type: str = "hard_cut"
    start_state: str = ""
    end_state: str = ""
    screen_direction: str = ""
    continuity_notes: str = ""
    use_prev_last_frame: bool = False
    depends_on_last_frame_shot_id: Optional[PydanticObjectId] = None
    continuity_dirty: bool = False
    continuity_dirty_reason: str = ""
    description: str = ""
    dialogues: list[ShotDialogueLine] = []  # 一个镜头可有多句对白
    prompt: str = ""
    submitted_prompt: str = ""
    submitted_prompt_input_hash: str = ""
    submitted_prompt_cached_at: Optional[datetime] = None
    required_assets: list[ShotAssetBinding] = []
    state: ShotState = ShotState.planned
    version: str = "v1"
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    versions: list[ShotVersion] = Field(default_factory=list)
    review_comment: str = ""
    generation_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "shots"
        indexes = [
            "episode_id",
            [("episode_id", 1), ("order", 1)],
        ]
