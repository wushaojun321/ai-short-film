"""Image generation Celery tasks: asset images, shot storyboard images."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.image.gen_asset", queue="image")
def gen_asset_image_task(self, asset_id: str):
    """Generate preview image for an asset using Seedream."""
    return run_async(_gen_asset_image_async(self.request.id, asset_id))


async def _gen_asset_image_async(celery_id: str, asset_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.asset import Asset, AssetStatus, AssetVersion
    from app.models.project import Project
    from app.models.task_record import TaskRecord
    from app.services import image_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope
    from datetime import datetime

    try:
        asset = await Asset.get(PydanticObjectId(asset_id))
        if not asset:
            raise ValueError("Asset not found")

        # Mark as generating immediately so frontend can show loading
        await asset.set({"status": AssetStatus.generating, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 10})

        # Load series_prompt for style consistency
        project = await Project.get(asset.project_id)
        series_prompt = (project.series_prompt or "") if project else ""

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.asset_prompt_gen,
            {
                "series_prompt": series_prompt,
                "asset_name": asset.name,
                "asset_type": asset.asset_type,
                "asset_description": asset.prompt,
            },
        )

        # Merge series_prompt into generation prompt for visual consistency
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if user_prompt else system_prompt
        if series_prompt and series_prompt not in full_prompt:
            full_prompt = f"{series_prompt}\n\n{full_prompt}"

        if record:
            await record.set({"progress": 30})

        image_url = await image_service.generate_image(
            prompt=full_prompt or asset.prompt,
            size="2048x2048",
        )

        # Record version
        version_str = f"v{len(asset.versions) + 1}"
        new_version = AssetVersion(
            version=version_str,
            url=image_url,
            prompt=full_prompt or asset.prompt,
            created_at=datetime.utcnow(),
        )

        versions = asset.versions + [new_version]
        await asset.set({
            "preview_url": image_url,
            "versions": versions,
            "status": AssetStatus.pending,  # needs user confirmation
            "generation_task_id": celery_id,
        })

        await finish_task_record(celery_id, result={"image_url": image_url})
        return {"image_url": image_url}

    except Exception as e:
        # Reset status on failure
        try:
            asset = await Asset.get(PydanticObjectId(asset_id))
            if asset:
                await asset.set({"status": AssetStatus.need_regen})
        except Exception:
            pass
        await finish_task_record(celery_id, error=str(e))
        raise


@celery_app.task(bind=True, name="app.tasks.image.gen_shot_image", queue="image")
def gen_shot_image_task(self, shot_id: str):
    """Generate storyboard image for a shot."""
    return run_async(_gen_shot_image_async(self.request.id, shot_id))


async def _gen_shot_image_async(celery_id: str, shot_id: str):
    from app.database import init_db
    await init_db()

    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.project import Project
    from app.models.task_record import TaskRecord
    from app.services import image_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        # Mark as generating immediately
        await shot.set({"state": ShotState.generating, "generation_task_id": celery_id})

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 10})

        # Load series_prompt
        project = await Project.get(shot.project_id)
        series_prompt = (project.series_prompt or "") if project else ""

        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_image_gen,
            {
                "series_prompt": series_prompt,
                "shot_code": shot.shot_code,
                "shot_description": shot.description,
                "shot_prompt": shot.prompt,
            },
        )

        full_prompt = user_prompt or shot.prompt
        if series_prompt and series_prompt not in full_prompt:
            full_prompt = f"{series_prompt}\n\n{full_prompt}"

        if record:
            await record.set({"progress": 30})

        image_url = await image_service.generate_image(
            prompt=full_prompt,
            size="2048x3640",  # ~9:16 vertical, ≥3.6M pixels
        )

        await shot.set({
            "image_url": image_url,
            "state": ShotState.asset_ready,
            "generation_task_id": celery_id,
        })

        await finish_task_record(celery_id, result={"image_url": image_url})
        return {"image_url": image_url}

    except Exception as e:
        try:
            shot = await Shot.get(PydanticObjectId(shot_id))
            if shot:
                await shot.set({"state": ShotState.planned})
        except Exception:
            pass
        await finish_task_record(celery_id, error=str(e))
        raise
