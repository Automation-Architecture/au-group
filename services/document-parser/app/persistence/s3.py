import hashlib
import logging
import tempfile
from pathlib import Path

import boto3
from app.core.config import get_settings
from app.core.s3_validation import validate_s3_key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def _client_error_to_exception(exc: ClientError, s3_key: str) -> Exception:
    code = exc.response.get("Error", {}).get("Code", "")
    if code in {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}:
        return FileNotFoundError(f"S3 object not found: {s3_key}")
    if code in {"403", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
        return PermissionError(
            f"S3 access denied for key {s3_key!r}. "
            "Check S3_ENDPOINT, AWS credentials, and S3_BUCKET."
        )
    return RuntimeError(f"S3 error ({code}): {s3_key}")


class S3Client:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        client_kwargs: dict[str, str] = {"region_name": settings.aws_region}
        if settings.s3_endpoint:
            client_kwargs["endpoint_url"] = settings.s3_endpoint.rstrip("/")
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        self._client = boto3.client("s3", **client_kwargs)

    def download_to_temp(self, s3_key: str) -> Path:
        validate_s3_key(s3_key, operation="read")
        suffix = Path(s3_key).suffix or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            self._client.download_file(self._bucket, s3_key, str(tmp_path))
        except ClientError as exc:
            tmp_path.unlink(missing_ok=True)
            raise _client_error_to_exception(exc, s3_key) from exc
        return tmp_path

    def put_text(self, s3_key: str, content: str) -> None:
        validate_s3_key(s3_key, operation="write")
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
        except ClientError as exc:
            raise _client_error_to_exception(exc, s3_key) from exc

    def put_json(self, s3_key: str, content: str) -> None:
        validate_s3_key(s3_key, operation="write")
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as exc:
            raise _client_error_to_exception(exc, s3_key) from exc

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
