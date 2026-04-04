import io
import logging
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from bot.config import settings

log = logging.getLogger(__name__)


class S3Storage:
    """S3-compatible storage abstraction (works with MinIO for local dev)."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
    ):
        self.bucket = bucket or settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or settings.s3_endpoint,
            aws_access_key_id=access_key or settings.s3_access_key,
            aws_secret_access_key=secret_key or settings.s3_secret_key,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create the bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
                log.info(f"Created S3 bucket: {self.bucket}")
            except ClientError as e:
                log.warning(f"Could not create bucket {self.bucket}: {e}")

    def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload data to S3 and return the key."""
        if isinstance(data, bytes):
            data = io.BytesIO(data)

        self.client.upload_fileobj(
            data,
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        log.info(f"Uploaded to s3://{self.bucket}/{key}")
        return key

    def download(self, key: str) -> bytes:
        """Download data from S3 and return as bytes."""
        buf = io.BytesIO()
        self.client.download_fileobj(self.bucket, key, buf)
        buf.seek(0)
        return buf.read()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for the given key."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str):
        """Delete an object from S3."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
        log.info(f"Deleted s3://{self.bucket}/{key}")


# Singleton — lazy init so it doesn't fail if MinIO isn't running
_storage: S3Storage | None = None


def get_storage() -> S3Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage
