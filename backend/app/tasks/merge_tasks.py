"""Video merge Celery task: concatenate all approved shots into final episode."""
from __future__ import annotations
from app.celery_app import celery_app
from app.tasks.base import run_async, finish_task_record


TARGET_WIDTH = 720
TARGET_HEIGHT = 1280
SEGMENT_GAP_SECONDS = 0.18
CROSSFADE_SECONDS = 0.22


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

    def run_ffmpeg(cmd: list[str], timeout: int = 3600) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    def probe_duration(path: str) -> float:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return 0.0
        try:
            return float(result.stdout.strip() or 0)
        except ValueError:
            return 0.0

    def has_audio_stream(path: str) -> bool:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=index", "-of", "csv=p=0", path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def transition_type_for(prev_shot: Shot | None, shot: Shot) -> str:
        if not prev_shot:
            return "hard_cut"
        explicit = (shot.transition_type or "").strip()
        if explicit:
            return explicit
        if prev_shot.segment_code and shot.segment_code and prev_shot.segment_code != shot.segment_code:
            transition_text = f"{prev_shot.transition_out} {shot.transition_in}"
            continuous_words = ("承接", "同场", "视线", "动作连续", "声音延续", "直接接")
            return "hard_cut" if any(word in transition_text for word in continuous_words) else "black_gap"
        return "hard_cut"

    def make_black_gap(path: str) -> None:
        run_ffmpeg([
            "ffmpeg", "-f", "lavfi", "-i",
            f"color=c=black:s={TARGET_WIDTH}x{TARGET_HEIGHT}:d={SEGMENT_GAP_SECONDS}",
            "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:d={SEGMENT_GAP_SECONDS}",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-y", path,
        ], timeout=120)

    def merge_crossfade(prev_path: str, current_path: str, output_path: str, duration: float = CROSSFADE_SECONDS) -> None:
        prev_duration = probe_duration(prev_path)
        current_duration = probe_duration(current_path)
        safe_duration = min(duration, max(prev_duration - 0.1, 0.05), max(current_duration - 0.1, 0.05))
        if safe_duration <= 0.05:
            # Fall back to concat if either clip is too short for a meaningful transition.
            concat_path = f"{output_path}.txt"
            with open(concat_path, "w") as f:
                f.write(f"file '{prev_path}'\n")
                f.write(f"file '{current_path}'\n")
            run_ffmpeg(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_path, "-c", "copy", "-y", output_path])
            return

        offset = max(prev_duration - safe_duration, 0)
        run_ffmpeg([
            "ffmpeg", "-i", prev_path, "-i", current_path,
            "-filter_complex",
            (
                f"[0:v][1:v]xfade=transition=fade:duration={safe_duration:.2f}:offset={offset:.2f},format=yuv420p[v];"
                f"[0:a][1:a]acrossfade=d={safe_duration:.2f}:c1=tri:c2=tri[a]"
            ),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-y", output_path,
        ])

    def normalize_clip(input_path: str, output_path: str) -> None:
        duration = probe_duration(input_path)
        fade_out_start = max(duration - 0.12, 0) if duration else 0
        vf = (
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,format=yuv420p"
        )
        af = f"afade=t=in:st=0:d=0.06,afade=t=out:st={fade_out_start:.2f}:d=0.12"
        if has_audio_stream(input_path):
            cmd = [
                "ffmpeg", "-i", input_path,
                "-vf", vf, "-af", af,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", "-y", output_path,
            ]
        else:
            silent_duration = max(duration, 0.1)
            cmd = [
                "ffmpeg", "-i", input_path,
                "-f", "lavfi", "-i",
                f"anullsrc=channel_layout=stereo:sample_rate=48000:d={silent_duration}",
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-shortest", "-movflags", "+faststart", "-y", output_path,
            ]
        run_ffmpeg(cmd)

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
                processed_path = os.path.join(tmpdir, f"shot_{i:03d}_normalized.mp4")
                normalize_clip(local_path, processed_path)

                transition_type = transition_type_for(shots[i - 1] if i > 0 else None, shot)
                if i > 0 and transition_type == "black_gap":
                    gap_path = os.path.join(tmpdir, f"gap_{i:03d}.mp4")
                    make_black_gap(gap_path)
                    video_paths.append(gap_path)
                    video_paths.append(processed_path)
                elif i > 0 and transition_type == "crossfade" and video_paths:
                    prev_path = video_paths.pop()
                    combined_path = os.path.join(tmpdir, f"xfade_{i:03d}.mp4")
                    merge_crossfade(prev_path, processed_path, combined_path)
                    video_paths.append(combined_path)
                else:
                    video_paths.append(processed_path)

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

            # Run ffmpeg. Clips are normalized first so concat remains reliable.
            cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", concat_path, "-c", "copy", "-y", output_path,
            ]
            run_ffmpeg(cmd)

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
