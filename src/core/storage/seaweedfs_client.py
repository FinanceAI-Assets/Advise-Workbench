"""SeaweedFS document storage through its S3 gateway."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.core.config import settings

logger = logging.getLogger(__name__)


class SeaweedFSClient:
    """Store and fetch document bytes in one S3 bucket."""

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str = "us-east-1",
        timeout_sec: int = 60,
    ):
        if not endpoint_url or not bucket:
            raise ValueError("S3_ENDPOINT_URL and S3_BUCKET must be set for document storage")
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        # SeaweedFS stores boto3>=1.36 default checksum framing as part of the object;
        # "when_required" keeps uploads byte-identical.
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=timeout_sec,
            read_timeout=timeout_sec,
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=config,
            verify=settings.tls_verify,
        )

    def upload_file(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
        sha256 = hashlib.sha256(data).hexdigest()
        resp = self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": sha256},
        )
        logger.info("[S3] Uploaded s3://%s/%s (%d bytes)", self.bucket, key, len(data))
        return {
            "bucket": self.bucket,
            "key": key,
            "size": len(data),
            "sha256": sha256,
            "etag": str(resp.get("ETag", "")).strip('"'),
        }

    def get_file(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def head_file(self, key: str) -> dict[str, Any] | None:
        try:
            resp = self._s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return {"size": resp.get("ContentLength"), "content_type": resp.get("ContentType"), "etag": resp.get("ETag")}

    def delete_file(self, key: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=key)

    def health_check(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self.bucket)
            return True
        except (BotoCoreError, ClientError) as e:
            logger.warning("[S3] Health check failed for bucket %s: %s", self.bucket, e)
            return False


_client: SeaweedFSClient | None = None


def get_seaweedfs_client() -> SeaweedFSClient:
    global _client
    if _client is None:
        _client = SeaweedFSClient(
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            timeout_sec=settings.s3_timeout_sec,
        )
    return _client
