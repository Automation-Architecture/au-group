import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.request_context import get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    payload = dict(fields)
    correlation_id = payload.get("correlation_id") or get_request_id()
    if correlation_id is not None:
        payload.setdefault("correlation_id", correlation_id)

    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(structured)",
        0,
        message,
        (),
        None,
    )
    record.extra_fields = payload  # type: ignore[attr-defined]
    logger.handle(record)
