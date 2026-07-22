"""
Local disk storage standing in for S3 (audit finding: S3 costs money and
needs an AWS account — this gets you running for $0). The interface
(put/get/delete by key) mirrors an S3 client on purpose: swapping this for
boto3 later means changing this file only, nothing that calls it.
"""
import os
from pathlib import Path

from app.config import settings


class StorageError(Exception):
    pass


class LocalStorage:
    def __init__(self, root: str = settings.STORAGE_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Prevent path traversal — a filename like "../../etc/passwd" must
        # never escape the storage root.
        full_path = (self.root / key).resolve()
        if not str(full_path).startswith(str(self.root.resolve())):
            raise StorageError("Invalid storage key (path traversal attempt).")
        return full_path

    def put(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise StorageError(f"Storage key not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()


class S3Storage:
    """
    S3-compatible object storage — works with Cloudflare R2, AWS S3,
    Backblaze B2, or anything else speaking the S3 API. Same four-method
    interface as LocalStorage on purpose: nothing that calls `storage.get/
    put/delete/exists` needs to know or care which backend is active.

    R2 is the free-tier recommendation (10GB storage, no egress fees,
    genuinely free — not a 30-day trial). Point S3_ENDPOINT_URL at your R2
    account's S3 endpoint and this works unmodified.
    """

    def __init__(self):
        import boto3
        from app.config import settings

        if not settings.S3_BUCKET:
            raise StorageError("STORAGE_BACKEND=s3 but S3_BUCKET is not set.")

        client_kwargs = {
            "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
            "region_name": settings.S3_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client("s3", **client_kwargs)

    def put(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise StorageError(f"Storage key not found: {key}")
            raise StorageError(f"S3 error reading {key}: {e}")

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


def _build_storage():
    """Factory — reads STORAGE_BACKEND at import time and returns the
    matching backend. This is the ONLY place that decides which backend is
    active; everything else just calls the four common methods."""
    from app.config import settings
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage()


storage = _build_storage()
