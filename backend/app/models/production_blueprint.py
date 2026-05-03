from datetime import datetime
from enum import Enum
from typing import Any

from beanie import Document, PydanticObjectId
from pydantic import Field


class ProductionBlueprintStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    needs_review = "needs_review"


class ProductionBlueprint(Document):
    project_id: PydanticObjectId
    script_index_version: str = ""
    series: dict[str, Any] = Field(default_factory=dict)
    episodes: list[dict[str, Any]] = Field(default_factory=list)
    character_bible: list[dict[str, Any]] = Field(default_factory=list)
    scene_bible: list[dict[str, Any]] = Field(default_factory=list)
    prop_bible: list[dict[str, Any]] = Field(default_factory=list)
    character_variants: list[dict[str, Any]] = Field(default_factory=list)
    scene_variants: list[dict[str, Any]] = Field(default_factory=list)
    prop_variants: list[dict[str, Any]] = Field(default_factory=list)
    asset_inventory: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    continuity_report: dict[str, Any] = Field(default_factory=dict)
    status: ProductionBlueprintStatus = ProductionBlueprintStatus.draft
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "production_blueprints"
        indexes = [
            "project_id",
            [("project_id", 1), ("version", -1)],
        ]
