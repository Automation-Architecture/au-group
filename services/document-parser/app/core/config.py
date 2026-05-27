from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/document-parser — stable .env path regardless of process cwd (uvicorn, IDE)
SERVICE_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = SERVICE_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str
    parser_version: str = "0.1.0"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_http_timeout_sec: float = 60.0

    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket: str = "bankruptcy-creditor-docs"
    # Supabase Storage S3: https://<project-ref>.storage.supabase.co/storage/v1/s3
    s3_endpoint: str | None = None

    host: str = "0.0.0.0"
    # Railway injects PORT; local default 8001
    port: int = 8001
    log_level: str = "INFO"

    tesseract_cmd: str | None = None
    ocr_dpi: int = 300
    ocr_max_workers: int = 4
    structured_text_min_chars: int = 50
    structured_page_coverage: float = 0.8
    max_pdf_pages: int = 500

    confidence_review_threshold: float = 0.85
    confidence_level_high: float = 0.95
    confidence_level_medium: float = 0.8
    ocr_confidence_review_threshold: float = 0.9
    # Must match au_group_runtime_config: creditor_name_min_length, creditor_line_number_max_digits
    creditor_name_min_length: int = 3
    creditor_line_number_max_digits: int = 3
    allow_local_file_urls: bool = False
    local_file_root: str | None = None

    app_env: str = "development"
    expose_openapi: bool = False

    allow_document_url: bool = False
    allowed_download_host_suffixes: str = ""
    max_download_bytes: int = 52_428_800
    http_download_timeout_sec: float = 30.0
    http_max_redirects: int = 3

    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"
    rate_limit_parse: str = "10/minute"
    rate_limit_login: str = "5/minute"
    rate_limit_extract: str = "10/minute"
    rate_limit_review: str = "30/minute"

    async_parse_enabled: bool = True
    async_parse_max_concurrent: int = 2

    # When true, POST /parse/document requires bankruptcy_id (production default).
    require_bankruptcy_id: bool = True

    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    auth_username: str | None = None
    auth_password: str | None = None

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("API_KEY must be set to a non-empty value")
        return value.strip()

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def download_host_suffixes(self) -> tuple[str, ...]:
        return tuple(
            s.strip().lower().lstrip(".")
            for s in self.allowed_download_host_suffixes.split(",")
            if s.strip()
        )

    @property
    def require_https_downloads(self) -> bool:
        return self.is_production

    def validate_api_key_strength(self) -> None:
        if self.is_production and len(self.api_key) < 32:
            raise ValueError("API_KEY must be at least 32 characters in production")

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters when set")
        return stripped

    @field_validator("auth_username", "auth_password")
    @classmethod
    def strip_optional_credential(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


@lru_cache
def get_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:
        api_key_errors = [e for e in exc.errors() if e.get("loc") == ("api_key",)]
        if api_key_errors:
            raise RuntimeError(
                "API_KEY environment variable is required. "
                "Set API_KEY in .env (local) or Railway service variables (production)."
            ) from exc
        raise RuntimeError(f"Invalid configuration: {exc}") from exc

    try:
        settings.validate_api_key_strength()
    except ValueError as exc:
        raise RuntimeError(f"Invalid API_KEY configuration: {exc}") from exc

    return settings
