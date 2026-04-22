"""Artifact upload helpers for S3-compatible object storage."""

from __future__ import annotations

from pathlib import Path
import hashlib
import mimetypes

import boto3

from .config import settings


def validate_storage_config() -> None:
    missing = []
    if not settings.r2_bucket:
        missing.append("R2_BUCKET")
    if not settings.r2_access_key_id:
        missing.append("R2_ACCESS_KEY_ID")
    if not settings.r2_secret_access_key:
        missing.append("R2_SECRET_ACCESS_KEY")
    if missing:
        raise RuntimeError(f"Missing object storage config: {', '.join(missing)}")


def build_storage_uri(key: str) -> str:
    if settings.r2_public_base:
        return f"{settings.r2_public_base.rstrip('/')}/{key.lstrip('/')}"
    return f"s3://{settings.r2_bucket}/{key}"


def s3_client():
    validate_storage_config()
    kwargs = {
        "aws_access_key_id": settings.r2_access_key_id,
        "aws_secret_access_key": settings.r2_secret_access_key,
    }
    if settings.r2_endpoint:
        kwargs["endpoint_url"] = settings.r2_endpoint
    return boto3.client("s3", **kwargs)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file(path: Path, key: str) -> str:
    client = s3_client()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    client.upload_file(
        str(path),
        settings.r2_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return build_storage_uri(key)
