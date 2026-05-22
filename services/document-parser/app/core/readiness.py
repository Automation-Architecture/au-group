"""Dependency checks for GET /health/ready."""

from __future__ import annotations

import logging

import httpx
from app.core.config import Settings
from app.persistence.s3 import S3Client
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def check_supabase(settings: Settings) -> tuple[bool, str]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return False, "supabase_not_configured"
    url = settings.supabase_url.rstrip("/") + "/rest/v1/"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code >= 500:
                return False, f"supabase_http_{response.status_code}"
    except httpx.HTTPError as exc:
        logger.warning("readiness_supabase_failed", exc_info=exc)
        return False, "supabase_unreachable"
    return True, "ok"


def check_s3(settings: Settings) -> tuple[bool, str]:
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return False, "s3_not_configured"
    try:
        S3Client()._client.head_bucket(Bucket=settings.s3_bucket)  # noqa: SLF001
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        logger.warning("readiness_s3_failed code=%s", code, exc_info=exc)
        return False, f"s3_{code or 'error'}"
    except Exception as exc:
        logger.warning("readiness_s3_failed", exc_info=exc)
        return False, "s3_unreachable"
    return True, "ok"


def run_readiness_checks(settings: Settings) -> dict[str, str]:
    ok_sb, detail_sb = check_supabase(settings)
    ok_s3, detail_s3 = check_s3(settings)
    return {
        "supabase": "ok" if ok_sb else detail_sb,
        "s3": "ok" if ok_s3 else detail_s3,
    }
