"""Tencent Cloud COS object storage service."""
import io
import uuid
from pathlib import Path
from urllib.parse import quote
from qcloud_cos import CosConfig, CosS3Client
from app.config import settings


def _get_client() -> CosS3Client:
    config = CosConfig(
        Region=settings.cos_region,
        SecretId=settings.cos_secret_id,
        SecretKey=settings.cos_secret_key,
        # COS 是腾讯云，大陆直连无需代理，强制绕过
        Proxies={"http": "", "https": ""},
    )
    return CosS3Client(config)


def _public_url(object_key: str) -> str:
    """Return the permanent COS URL for an object (bucket may be private)."""
    return (
        f"https://{settings.cos_bucket}.cos.{settings.cos_region}"
        f".myqcloud.com/{object_key}"
    )


def get_presigned_url(object_key: str, expires: int = 3600) -> str:
    """Return a temporary pre-signed URL valid for `expires` seconds (default 1h).

    Works even if the bucket is private — the signed URL embeds auth credentials.
    Suitable for passing to third-party APIs (e.g. Volcano Seedance) that need to
    download the image without requiring bucket public access.
    """
    client = _get_client()
    return client.get_presigned_url(
        Method="GET",
        Bucket=settings.cos_bucket,
        Key=object_key,
        Expired=expires,
    )


def get_presigned_download_url(url: str, filename: str, expires: int = 600) -> str:
    """Return a signed URL that asks COS to send the object as an attachment."""
    object_key = cos_url_to_object_key(url)
    if not object_key:
        return url

    safe_filename = filename.replace("\r", "").replace("\n", "").strip() or "video.mp4"
    ascii_fallback = "".join(ch if ch.isascii() and ch not in {'"', "\\"} else "_" for ch in safe_filename)
    ascii_fallback = ascii_fallback.strip("._ ") or "video.mp4"
    disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(safe_filename)}"
    )

    client = _get_client()
    return client.get_presigned_url(
        Method="GET",
        Bucket=settings.cos_bucket,
        Key=object_key,
        Expired=expires,
        Params={
            "response-content-disposition": disposition,
            "response-content-type": "video/mp4",
        },
    )


def cos_url_to_object_key(url: str) -> str | None:
    """Extract the COS object key from a full COS URL, or return None if not a COS URL."""
    import re
    pattern = (
        rf"https://{re.escape(settings.cos_bucket)}\.cos\."
        rf"{re.escape(settings.cos_region)}\.myqcloud\.com/(.+)"
    )
    m = re.match(pattern, url)
    return m.group(1) if m else None


def presign_if_cos(url: str, expires: int = 3600) -> str:
    """If `url` is a COS URL, return a pre-signed version; otherwise return as-is."""
    key = cos_url_to_object_key(url)
    if key:
        return get_presigned_url(key, expires=expires)
    return url


def get_sts_credentials(duration_seconds: int = 43200) -> dict:
    """申请 STS 临时密钥，默认有效期 12 小时（最长 43200 秒）。

    返回前端所需字段：
      tmpSecretId, tmpSecretKey, sessionToken, expiredTime, bucket, region
    """
    from sts.sts import Sts  # qcloud-python-sts

    sts = Sts({
        "url": "https://sts.tencentcloudapi.com/",
        "domain": "sts.tencentcloudapi.com",
        "secret_id": settings.cos_secret_id,
        "secret_key": settings.cos_secret_key,
        "duration_seconds": duration_seconds,
        "bucket": settings.cos_bucket,
        "region": settings.cos_region,
        "allow_prefix": "*",
        "allow_actions": ["name/cos:GetObject", "name/cos:HeadObject"],
    })
    resp = sts.get_credential()
    cred = resp["credentials"]
    return {
        "tmpSecretId": cred["tmpSecretId"],
        "tmpSecretKey": cred["tmpSecretKey"],
        "sessionToken": cred["sessionToken"],
        "expiredTime": resp["expiredTime"],  # unix timestamp
        "bucket": settings.cos_bucket,
        "region": settings.cos_region,
    }


async def upload_bytes(
    data: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload raw bytes to COS, return permanent URL."""
    client = _get_client()
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
    """Upload a local file to COS, return permanent URL."""
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
    # 火山引擎图片链接是国内地址，不走代理
    async with httpx.AsyncClient(proxy=None) as http:
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
