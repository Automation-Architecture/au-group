"""Request correlation ID propagation."""

import logging

from app.core.logging import log_event
from app.core.request_context import bind_request_id, get_request_id, reset_request_id


def test_log_event_injects_correlation_id_from_context() -> None:
    token = bind_request_id("corr-123")
    try:
        logger = logging.getLogger("test.request_context")
        captured: list[dict] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(getattr(record, "extra_fields", {}))

        handler = _Capture()
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        log_event(logger, "test_event", status="ok")
        assert captured[0]["correlation_id"] == "corr-123"
        assert captured[0]["status"] == "ok"
    finally:
        reset_request_id(token)
        assert get_request_id() is None


def test_log_event_explicit_correlation_id_wins() -> None:
    token = bind_request_id("from-context")
    try:
        logger = logging.getLogger("test.request_context.explicit")
        captured: list[dict] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record.extra_fields)  # type: ignore[attr-defined]

        handler = _Capture()
        logger.addHandler(handler)
        log_event(logger, "evt", correlation_id="explicit-id")
        assert captured[0]["correlation_id"] == "explicit-id"
    finally:
        reset_request_id(token)
