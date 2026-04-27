"""Volcano Engine Seedream image generation service."""
from __future__ import annotations
import uuid
import httpx
from volcenginesdkarkruntime import Ark
from app.config import settings
import app.services.storage_service as storage_service


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
) -> str:
    """Generate image with Seedream, upload to COS, return permanent URL.
    
    Seedream URLs expire in 24h → we immediately re-upload to COS.
    """
    client = get_ark_client()
    result = client.images.generate(
        model=settings.ark_image_model,
        prompt=prompt,
        size=size,
        response_format="url",
        watermark=watermark,
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
    return permanent_url
