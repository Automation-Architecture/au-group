from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str
    parser_version: str = "0.1.0"

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    aws_region: str = "us-east-1"
    s3_bucket: str = "bankruptcy-creditor-docs"

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
    allow_local_file_urls: bool = False

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("API_KEY must be set to a non-empty value")
        return value.strip()


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        raise RuntimeError(
            "API_KEY environment variable is required. "
            "Set API_KEY in .env (local) or Railway service variables (production)."
        ) from exc
