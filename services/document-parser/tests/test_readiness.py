"""Unit tests for readiness check helpers."""

from app.core.config import Settings
from app.core.readiness import check_s3, check_supabase, run_readiness_checks


def test_check_supabase_not_configured() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="",
        supabase_service_role_key="",
    )
    ok, detail = check_supabase(settings)
    assert ok is False
    assert detail == "supabase_not_configured"


def test_check_s3_not_configured() -> None:
    settings = Settings(
        api_key="test-key",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    ok, detail = check_s3(settings)
    assert ok is False
    assert detail == "s3_not_configured"


def test_run_readiness_checks_reports_both() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="",
        supabase_service_role_key="",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    checks = run_readiness_checks(settings)
    assert "supabase" in checks
    assert "s3" in checks
