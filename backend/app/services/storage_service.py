"""Tencent Cloud COS object storage service."""
import io
import uuid
from pathlib import Path
from qcloud_cos import CosConfig, CosS3Client
from app.config import settings


def _get_client() -> CosS3Client:
    config = CosConfig(
        Region=settings.cos_region,
        SecretId=settings.cos_secret_id,
        SecretKey=settings.cos_secret_key,
    )
    return CosS3Client(config)


def _public_url(object_key: str) -> str:
    """Return the permanent public URL for a COS object."""
    return (
        f"https://{settings.cos_bucket}.cos.{settings.cos_region}"
        f".myqcloud.com/{object_key}"
    )


async def upload_bytes(
    data: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload raw bytes to COS, return public URL.
    
    `filename` is used as the COS object key directly.
    For uniqueness, callers should include a UUID prefix in filename.
    """
    client = _get_client()
    # Add UUID prefix to avoid collisions
    object_key = f"{uuid.uuid4().hex}/{filename.lstrip('/')}"
    client.put_object(
        Bucket=settings.cos_bucket,
        Body=io.BytesIO(data),
        Key=object_key,
        ContentType=content_type,
    )
    return _public_url(object_key)


async def upload_file(
    file_path: str,
    object_key: str | None = None,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a local file to COS, return public URL."""
    client = _get_client()
    p = Path(file_path)
    if object_key is None:
        object_key = f"{uuid.uuid4().hex}/{p.name}"
    client.upload_file(
        Bucket=settings.cos_bucket,
        LocalFilePath=file_path,
        Key=object_key,
        ContentType=content_type,
    )
    return _public_url(object_key)


async def upload_from_url(source_url: str, object_key: str) -> str:
    """Download a URL and re-upload to COS (for expiring Seedream URLs)."""
    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.get(source_url, follow_redirects=True, timeout=120)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        data = resp.content

    client = _get_client()
    client.put_object(
        Bucket=settings.cos_bucket,
        Body=io.BytesIO(data),
        Key=object_key,
        ContentType=content_type,
    )
    return _public_url(object_key)


async def download_file(url: str, save_path: str) -> str:
    """Download a URL to local path."""
    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.get(url, follow_redirects=True, timeout=120)
        resp.raise_for_status()
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(resp.content)
    return save_path
