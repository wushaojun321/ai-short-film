from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class EpisodeStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed   = "completed"


class EpisodeStep(str, Enum):
    storyboard_script  = "storyboard_script"
    storyboard_images  = "storyboard_images"
    image_review       = "image_review"
    storyboard_videos  = "storyboard_videos"
    video_review       = "video_review"
    dubbing            = "dubbing"
    merge              = "merge"
    done               = "done"


STEP_ORDER = [
    EpisodeStep.storyboard_script,
    EpisodeStep.storyboard_images,
    EpisodeStep.image_review,
    EpisodeStep.storyboard_videos,
    EpisodeStep.video_review,
    EpisodeStep.dubbing,
    EpisodeStep.merge,
    EpisodeStep.done,
]


class Episode(Document):
    project_id: PydanticObjectId
    number: int
    title: str
    summary: str = ""
    script_excerpt: str = ""
    word_count: int = 0
    estimated_duration: int = 0
    status: EpisodeStatus = EpisodeStatus.not_started
    current_step: EpisodeStep = EpisodeStep.storyboard_script
    continuity_notes: str = ""
    final_video_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "episodes"
        indexes = [
            "project_id",
            [("project_id", 1), ("number", 1)],
        ]
