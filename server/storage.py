"""Garage S3 Object Storage Client with local filesystem fallback.

Connects to S3-compatible Garage endpoint or saves locally if unavailable.
"""

import os
from pathlib import Path
from typing import Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

# Configuration from Environment
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:3900")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "GK436e3a93075c0957462a5d81")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "3ec66c478ead94804f1e10edf7625a4b119391d95f093df77a3d5a9147be98cd")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "ocr-documents")
S3_REGION = os.getenv("S3_REGION", "garage")
USE_LOCAL_FALLBACK = os.getenv("USE_LOCAL_FALLBACK", "true").lower() == "true"

LOCAL_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "storage"
LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class StorageManager:
    def __init__(self):
        self.s3_client = None
        self.bucket_ready = False
        self._init_s3()

    def _init_s3(self):
        """Initialize S3 client for Garage."""
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT_URL,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                region_name=S3_REGION,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"})
            )
            # Check or create bucket
            self._ensure_bucket()
            self.bucket_ready = True
        except Exception:
            self.s3_client = None
            self.bucket_ready = False

    def _ensure_bucket(self):
        """Create bucket if not exists in Garage."""
        try:
            self.s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                self.s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
            else:
                raise

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload object to Garage S3, fallback to disk if S3 offline."""
        if self.bucket_ready and self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=key,
                    Body=data,
                    ContentType=content_type
                )
                return f"s3://{S3_BUCKET_NAME}/{key}"
            except Exception:
                pass

        # Local fallback
        dest = LOCAL_STORAGE_DIR / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"file://{dest}"

    def get_object(self, key: str) -> Optional[bytes]:
        """Retrieve object bytes from Garage S3 or local fallback."""
        if self.bucket_ready and self.s3_client:
            try:
                resp = self.s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                return resp["Body"].read()
            except Exception:
                pass

        dest = LOCAL_STORAGE_DIR / key
        if dest.exists():
            return dest.read_bytes()
        return None

    def delete_object(self, key: str) -> bool:
        """Delete object from Garage S3 or local fallback."""
        if self.bucket_ready and self.s3_client:
            try:
                self.s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=key)
            except Exception:
                pass

        dest = LOCAL_STORAGE_DIR / key
        if dest.exists():
            dest.unlink(missing_ok=True)
        return True

    def is_healthy(self) -> dict:
        """Check Garage S3 health status."""
        if not self.s3_client:
            return {"status": "fallback_local", "endpoint": S3_ENDPOINT_URL, "connected": False}
        try:
            self.s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
            return {"status": "connected", "endpoint": S3_ENDPOINT_URL, "connected": True, "bucket": S3_BUCKET_NAME}
        except Exception as e:
            return {"status": "error", "endpoint": S3_ENDPOINT_URL, "connected": False, "error": str(e)}


storage = StorageManager()
