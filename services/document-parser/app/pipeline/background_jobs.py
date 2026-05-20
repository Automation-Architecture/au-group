"""Limit concurrent in-process background OCR jobs."""

from __future__ import annotations

import threading
from contextlib import contextmanager

_lock = threading.Lock()
_semaphore: threading.Semaphore | None = None
_max_slots: int | None = None


def _get_semaphore(max_concurrent: int) -> threading.Semaphore:
    global _semaphore, _max_slots
    with _lock:
        if _semaphore is None or _max_slots != max_concurrent:
            _semaphore = threading.Semaphore(max_concurrent)
            _max_slots = max_concurrent
        return _semaphore


def try_acquire_background_slot(max_concurrent: int) -> bool:
    return _get_semaphore(max_concurrent).acquire(blocking=False)


def release_background_slot(max_concurrent: int) -> None:
    _get_semaphore(max_concurrent).release()


@contextmanager
def background_parse_slot(max_concurrent: int):
    sem = _get_semaphore(max_concurrent)
    if not sem.acquire(blocking=False):
        from app.core.exceptions import BackgroundJobBusyError

        raise BackgroundJobBusyError()
    try:
        yield
    finally:
        sem.release()
