"""Video merge Celery task: concatenate all approved shots into final episode."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


@celery_app.task(bind=True, name="app.tasks.merge.merge_episode", queue="merge")
def merge_episode_task(self, episode_id: str):
    """Download approved shot videos and merge into final episode video."""
    return run_async(_merge_episode_async(self.request.id, episode_id))


async def _merge_episode_async(celery_id: str, episode_id: str):
    from app.database import init_db
    await init_db()

    import asyncio
    import os
    import tempfile
    import subprocess
    from pathlib import Path
    from beanie import PydanticObjectId
    from app.models.episode import Episode, EpisodeStep, EpisodeStatus
    from app.models.shot import Shot, ShotState
    from app.models.task_record import TaskRecord
    import app.services.storage_service as storage_service

    try:
        episode = await Episode.get(PydanticObjectId(episode_id))
        if not episode:
            raise ValueError("Episode not found")

        record = await TaskRecord.find_one(TaskRecord.celery_task_id == celery_id)

        # Get approved shots in order
        shots = await Shot.find(
            Shot.episode_id == episode.id,
            Shot.state == ShotState.approved,
        ).sort("+order").to_list()

        if not shots:
            raise ValueError("No approved shots found")

        if record:
            await record.set({"progress": 10})

        with tempfile.TemporaryDirectory() as tmpdir:
            video_paths = []
            total = len(shots)

            # Download all shot videos
            for i, shot in enumerate(shots):
                if not shot.video_url:
                    raise ValueError(f"Shot {shot.shot_code} has no video_url")

                local_path = os.path.join(tmpdir, f"shot_{i:03d}.mp4")
                from app.services.storage_service import presign_if_cos
                await storage_service.download_file(presign_if_cos(shot.video_url), local_path)
                video_paths.append(local_path)

                if record:
                    progress = 10 + int((i + 1) / total * 50)
                    await record.set({"progress": progress})

            if record:
                await record.set({"progress": 65})

            # Create concat file
            concat_path = os.path.join(tmpdir, "concat.txt")
            with open(concat_path, "w") as f:
                for p in video_paths:
                    f.write(f"file '{p}'\n")

            output_path = os.path.join(tmpdir, f"episode_{episode.number:02d}.mp4")

            # Run ffmpeg
            cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", concat_path, "-c", "copy", "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

            if record:
                await record.set({"progress": 85})

            # Upload final video to COS
            import uuid
            object_key = f"episodes/ep{episode.number:02d}_{uuid.uuid4().hex}.mp4"
            final_url = await storage_service.upload_file(
                file_path=output_path,
                object_key=object_key,
                content_type="video/mp4",
            )

        await episode.set({
            "final_video_url": final_url,
            "current_step": EpisodeStep.done,
            "status": EpisodeStatus.completed,
        })

        await finish_task_record(celery_id, result={"final_video_url": final_url})
        return {"final_video_url": final_url}

    except Exception as e:
        await finish_task_record(celery_id, error=str(e))
        raise
