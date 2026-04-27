"""Volcano Engine Seedance video generation service."""
from __future__ import annotations
import time
import uuid
import httpx
from volcenginesdkarkruntime import Ark
from app.config import settings
import app.services.storage_service as storage_service

POLL_INTERVAL = 30  # seconds
POLL_TIMEOUT = 600  # 10 minutes


def get_ark_client() -> Ark:
    # 显式传入不走代理的 http_client，火山引擎国内直连
    return Ark(
        base_url=settings.ark_base_url,
        api_key=settings.ark_api_key,
        http_client=httpx.Client(proxy=None),
    )


def build_video_content(
    prompt: str,
    first_frame_url: str | None = None,
    reference_images: list[str] | None = None,
) -> tuple[list[dict], bool]:
    """Build content list for Seedance 2.0.

    Seedance 2.0 有两种互斥模式：
    - 首帧模式（role=first_frame）：支持 duration 参数
    - 多模态参考模式（role=reference_image）：r2v 模式，不支持 duration 参数

    策略：有 first_frame_url 则用首帧模式（忽略 reference_images），
    否则用多模态参考模式。

    Returns: (content, is_first_frame_mode)
    """
    content: list[dict] = [{"type": "text", "text": prompt}]

    if first_frame_url:
        # 首帧模式：分镜剧照作为首帧，支持 duration
        content.append({
            "type": "image_url",
            "image_url": {"url": first_frame_url},
            "role": "first_frame",
        })
        return content, True
    else:
        # 多模态参考模式：用资产图作参考，不支持 duration
        for img_url in (reference_images or []):
            content.append({
                "type": "image_url",
                "image_url": {"url": img_url},
                "role": "reference_image",
            })
        return content, False


def generate_video_sync(
    prompt: str,
    first_frame_url: str | None = None,
    reference_images: list[str] | None = None,
    ratio: str = "9:16",
    duration: int = 5,
    resolution: str = "720p",
    generate_audio: bool = True,
    return_last_frame: bool = True,
) -> dict:
    """Synchronous video generation with polling (for Celery tasks).
    
    Returns: {"video_url": str, "last_frame_url": str|None, "task_id": str}
    """
    client = get_ark_client()
    content, is_first_frame_mode = build_video_content(prompt, first_frame_url, reference_images)

    # r2v（多模态参考）模式不支持 duration 参数
    extra_params: dict = {"ratio": ratio, "resolution": resolution}
    if is_first_frame_mode:
        extra_params["duration"] = duration

    create_result = client.content_generation.tasks.create(
        model=settings.ark_video_model,
        content=content,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
        watermark=False,
        **extra_params,
    )
    task_id = create_result.id

    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        result = client.content_generation.tasks.get(task_id=task_id)
        status = result.status

        if status == "succeeded":
            video_url = result.content.video_url
            last_frame_url = getattr(result.content, "last_frame_url", None)
            return {
                "video_url": video_url,
                "last_frame_url": last_frame_url,
                "task_id": task_id,
            }
        elif status == "failed":
            error_msg = ""
            if result.error:
                error_msg = f"{result.error.code}: {result.error.message}"
            raise RuntimeError(f"Seedance failed: {error_msg}")

    raise TimeoutError(f"Seedance timeout after {POLL_TIMEOUT}s, task_id={task_id}")


async def upload_video_to_cos(video_url: str) -> str:
    """Download Seedance video URL and re-upload to COS."""
    object_key = f"videos/{uuid.uuid4().hex}.mp4"
    return await storage_service.upload_from_url(video_url, object_key)
