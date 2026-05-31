"""Unit tests for pipeline/alerts.py (KD-59 / WP-02)."""

from unittest.mock import MagicMock, patch

import pytest
from pipeline.alerts import post_slack, send_error_alert


class TestPostSlack:
    def test_posts_correct_payload(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}

        with patch("pipeline.alerts.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = mock_resp

            post_slack(bot_token="xoxb-test", channel_id="C123", text="hello")

        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["channel"] == "C123"
        assert kwargs["json"]["text"] == "hello"
        assert "Bearer xoxb-test" in kwargs["headers"]["Authorization"]

    def test_raises_on_slack_api_error(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "error": "not_in_channel"}

        with patch("pipeline.alerts.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = mock_resp

            with pytest.raises(RuntimeError, match="not_in_channel"):
                post_slack(bot_token="xoxb-test", channel_id="C123", text="hello")


class TestSendErrorAlert:
    def test_posts_formatted_error_block(self):
        with patch("pipeline.alerts.post_slack") as mock_post:
            send_error_alert(
                stage="intake.py — PACER auth",
                error="PACER timeout",
                bankruptcy_id="uuid-123",
                bot_token="xoxb-test",
                channel_id="C123",
            )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        text = kwargs.get("text") or mock_post.call_args[0][2]
        assert "intake.py" in text
        assert "PACER timeout" in text
        assert "uuid-123" in text
        assert "xoxb-test" not in text  # no secrets in the message body

    def test_never_raises_on_slack_failure(self):
        with patch("pipeline.alerts.post_slack", side_effect=Exception("network error")):
            # Should not raise — alert failures are logged, not propagated
            send_error_alert(
                stage="intake.py — RPC",
                error="DB connection refused",
                bot_token="xoxb-test",
                channel_id="C123",
            )

    def test_works_without_bankruptcy_id(self):
        with patch("pipeline.alerts.post_slack") as mock_post:
            send_error_alert(
                stage="report.py — Slack post",
                error="timeout",
                bot_token="xoxb-test",
                channel_id="C123",
            )
        mock_post.assert_called_once()

    def test_no_secrets_in_payload(self):
        captured = {}

        def capture(*args, **kwargs):
            captured["text"] = args[2] if len(args) > 2 else kwargs.get("text", "")

        with patch("pipeline.alerts.post_slack", side_effect=capture):
            send_error_alert(
                stage="enrich.py",
                error="ZoomInfo 401",
                bot_token="xoxb-supersecret-token",
                channel_id="C123",
            )

        assert "xoxb-supersecret-token" not in captured.get("text", "")
