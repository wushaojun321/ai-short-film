"""Volcano Engine Seedream image generation service."""
from __future__ import annotations
from dataclasses import dataclass
import logging
import uuid
import httpx
from volcenginesdkarkruntime import Ark
from app.config import settings
import app.services.storage_service as storage_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageGenerationResult:
    url: str
    provider_url: str


def get_ark_client() -> Ark:
    # 显式传入不走代理的 http_client，避免系统 HTTP_PROXY 环境变量影响火山引擎（国内直连）
    return Ark(
        base_url=settings.ark_base_url,
        api_key=settings.ark_api_key,
        http_client=httpx.Client(proxy=None),
    )


async def generate_image(
    prompt: str,
    size: str = "2048x2048",
    watermark: bool = False,
    image: str | list[str] | None = None,
) -> str:
    result = await generate_image_with_metadata(
        prompt=prompt,
        size=size,
        watermark=watermark,
        image=image,
    )
    return result.url


async def generate_image_with_metadata(
    prompt: str,
    size: str = "2048x2048",
    watermark: bool = False,
    image: str | list[str] | None = None,
) -> ImageGenerationResult:
    """Generate image with Seedream, upload to COS, return permanent URL.
    
    Seedream URLs expire in 24h → we immediately re-upload to COS.
    """
    reference_images = image
    if isinstance(reference_images, list):
        reference_images = [storage_service.presign_if_cos(url) for url in reference_images if url]
    elif reference_images:
        reference_images = storage_service.presign_if_cos(reference_images)

    ref_count = len(reference_images) if isinstance(reference_images, list) else int(bool(reference_images))
    logger.info(
        "[IMAGE PROMPT] model=%s size=%s watermark=%s reference_images=%d\n--- PROMPT START ---\n%s\n--- PROMPT END ---",
        settings.ark_image_model, size, watermark, ref_count, prompt,
    )
    client = get_ark_client()
    result = client.images.generate(
        model=settings.ark_image_model,
        prompt=prompt,
        image=reference_images or None,
        size=size,
        response_format="url",
        watermark=watermark,
        sequential_image_generation="disabled",
    )

    if not result.data:
        raise RuntimeError("Seedream returned empty response")

    first = result.data[0]
    if hasattr(first, "error") and first.error:
        raise RuntimeError(f"Seedream error: {first.error.message}")

    temp_url = first.url
    # Re-upload to COS so URL doesn't expire
    object_key = f"images/{uuid.uuid4().hex}.jpg"
    permanent_url = await storage_service.upload_from_url(temp_url, object_key)
    return ImageGenerationResult(url=permanent_url, provider_url=temp_url)
