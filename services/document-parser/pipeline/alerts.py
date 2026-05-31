"""Pipeline error alerting — posts failures to Slack #au-group-sprint."""

from __future__ import annotations

import logging


import httpx

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api/chat.postMessage"


def post_slack(bot_token: str, channel_id: str, text: str) -> None:
    """POST a message via Slack chat.postMessage.  Raises on HTTP or API error."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            _SLACK_API,
            headers={"Authorization": f"Bearer {bot_token}"},
            json={"channel": channel_id, "text": text},
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"Slack API error: {body.get('error')}")


def send_error_alert(
    stage: str,
    error: str,
    bankruptcy_id: str | None = None,
    *,
    bot_token: str,
    channel_id: str,
) -> None:
    """Post a :x: error block to Slack.

    Never raises — alert failures are logged but do not mask the original error.
    """
    lines = [f":x: *Pipeline error — {stage}*", f"```{error}```"]
    if bankruptcy_id:
        lines.append(f"bankruptcy_id: `{bankruptcy_id}`")
    try:
        post_slack(bot_token, channel_id, "\n".join(lines))
    except Exception:
        logger.exception("Failed to send error alert to Slack")
