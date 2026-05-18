import hashlib
import logging
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        self._client = boto3.client("s3", region_name=settings.aws_region)

    def download_to_temp(self, s3_key: str) -> Path:
        suffix = Path(s3_key).suffix or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            self._client.download_file(self._bucket, s3_key, str(tmp_path))
        except ClientError as exc:
            tmp_path.unlink(missing_ok=True)
            raise FileNotFoundError(f"S3 object not found: {s3_key}") from exc
        return tmp_path

    def put_text(self, s3_key: str, content: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )

    def put_json(self, s3_key: str, content: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType="application/json",
        )

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def ocr_output_key(self, case_number: str, document_id: str) -> str:
        return f"ocr-outputs/{case_number}/{document_id}.txt"

    def parsed_output_key(self, case_number: str, document_id: str) -> str:
        return f"parsed-outputs/{case_number}/{document_id}.json"
