"""Video generation Celery tasks using Seedance."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video", queue="video")
def gen_shot_video_task(self, shot_id: str):
    """Generate video for a shot using its image as first frame."""
    return run_async(_gen_shot_video_async(self.request.id, shot_id))


async def _gen_shot_video_async(celery_id: str, shot_id: str):
    from app.database import init_db
    await init_db()

    import asyncio
    from beanie import PydanticObjectId
    from app.models.shot import Shot, ShotState
    from app.models.asset import Asset
    from app.models.task_record import TaskRecord
    from app.services import video_service
    from app.services.prompt_service import render
    from app.models.prompt_config import PromptConfigScope

    try:
        shot = await Shot.get(PydanticObjectId(shot_id))
        if not shot:
            raise ValueError("Shot not found")

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)
        if record:
            await record.set({"progress": 5})

        # Build video prompt
        system_prompt, user_prompt, _ = await render(
            PromptConfigScope.shot_video_gen,
            {
                "shot_code": shot.shot_code,
                "shot_description": shot.description,
                "shot_prompt": shot.prompt,
            },
        )
        video_prompt = user_prompt or shot.prompt

        # Gather reference asset images
        reference_images: list[str] = []
        for binding in shot.required_assets:
            asset = await Asset.find_one(
                Asset.project_id == shot.project_id,
                Asset.name == binding.asset_name,
            )
            if asset and asset.preview_url:
                reference_images.append(asset.preview_url)

        if record:
            await record.set({"progress": 10})

        # Run sync Seedance generation in thread (blocks for up to 10 min)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: video_service.generate_video_sync(
                prompt=video_prompt,
                first_frame_url=shot.image_url,
                reference_images=reference_images if reference_images else None,
                ratio="9:16",
                duration=shot.duration or 5,
                resolution="720p",
                return_last_frame=True,
            ),
        )

        if record:
            await record.set({"progress": 80})

        # Re-upload video to COS
        video_url = await video_service.upload_video_to_cos(result["video_url"])
        last_frame_url = result.get("last_frame_url")

        updates: dict = {
            "video_url": video_url,
            "state": ShotState.rendered,
            "generation_task_id": celery_id,
        }
        if last_frame_url:
            updates["last_frame_url"] = last_frame_url

        await shot.set(updates)

        await finish_task_record(celery_id, result={"video_url": video_url, "last_frame_url": last_frame_url})
        return {"video_url": video_url}

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
