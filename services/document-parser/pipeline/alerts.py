"""Pipeline error alerting — posts failures to Slack #au-group-sprint."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def send_error_alert(
    stage: str,
    error: str,
    bankruptcy_id: Optional[str] = None,
    *,
    webhook_url: str,
) -> None:
    """POST a formatted error block to the Slack webhook.

    Never raises — alert failures are logged but do not mask the original error.
    """
    lines = [f":x: *Pipeline error — {stage}*", f"```{error}```"]
    if bankruptcy_id:
        lines.append(f"bankruptcy_id: `{bankruptcy_id}`")
    payload = {"text": "\n".join(lines)}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send error alert to Slack")
