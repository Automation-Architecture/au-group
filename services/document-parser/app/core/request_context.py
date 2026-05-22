"""Per-request correlation ID for structured logs and background tasks."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return str(uuid4())


def get_request_id() -> str | None:
    return _request_id.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)
