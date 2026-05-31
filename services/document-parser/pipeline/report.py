"""Daily creditor report — WP-03b (KD-61).

Invoked by the daily-report Railway cron service:
    python -m pipeline.report

Calls au_group_daily_creditor_report_grouped(), groups rows by debtor,
formats the Slack message per spec §4.3, and posts via Slack chat.postMessage.

Exit 0 on success, exit 1 on any unhandled failure (after alerting).

Railway cron service config (no port binding):
    rootDirectory:  services/document-parser
    startCommand:   python -m pipeline.report
    schedule:       0 13 * * 1-5   (8 AM ET standard / 9 AM EDT — see OD-1)
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import httpx

from pipeline.alerts import post_slack, send_error_alert
from pipeline.settings import get_pipeline_settings

logger = logging.getLogger(__name__)

# Split into per-debtor messages when total creditors exceed this threshold.
_SPLIT_THRESHOLD = 40

# Slack mrkdwn column separator (middot, matches PRD FR-5.7 spec).
_SEP = " · "


# ---------------------------------------------------------------------------
# Supabase RPC
# ---------------------------------------------------------------------------

def _call_grouped_report_rpc(
    supabase_url: str,
    service_role_key: str,
    timeout: float,
) -> dict[str, Any]:
    """Call au_group_daily_creditor_report_grouped() and return the parsed JSONB."""
    url = supabase_url.rstrip("/") + "/rest/v1/rpc/au_group_daily_creditor_report_grouped"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json={})
        resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _parse_claim(claim_str: str) -> float:
    """Parse formatted claim string ($1,234,567.00) to float for numeric sort."""
    if not claim_str:
        return 0.0
    try:
        return float(claim_str.replace("$", "").replace(",", ""))
    except ValueError:
        return 0.0


def _format_date(filing_date: str | date | None) -> str:
    if not filing_date:
        return ""
    if isinstance(filing_date, str):
        try:
            return datetime.strptime(filing_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return str(filing_date)
    return str(filing_date)


def _format_creditor_line(row: dict[str, Any]) -> str:
    """One bullet line per creditor per FR-5.7: Creditor · City · State · Claim · Tier · Status · ZoomInfo."""
    creditor = row.get("creditor") or ""
    city = row.get("city") or ""
    state = row.get("state") or ""
    claim = row.get("claim") or ""
    tier = row.get("tier")
    status = row.get("status") or ""
    zoominfo_url = row.get("zoominfo_url") or ""

    tier_str = str(tier) if tier is not None else "—"  # em dash for NULL

    parts = [f"*{creditor}*", city, state, claim, tier_str, status]
    line = "• " + _SEP.join(p for p in parts if p)

    if zoominfo_url:
        line += _SEP + f"<{zoominfo_url}|ZoomInfo>"

    return line


def _format_debtor_block(debtor_name: str, rows: list[dict[str, Any]]) -> str:
    """Header + creditor lines for one bankrupt company."""
    first = rows[0]
    case_number = first.get("case_number") or ""
    filing_date = _format_date(first.get("filing_date"))

    header = f"*{debtor_name}* | Case {case_number} | Filed {filing_date}"
    lines = [header] + [_format_creditor_line(r) for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slack posting
# ---------------------------------------------------------------------------

def _build_and_post_report(
    bot_token: str,
    channel_id: str,
    data: dict[str, Any],
) -> None:
    rows: list[dict[str, Any]] = data.get("rows") or []
    debtor_count: int = data.get("debtor_count") or 0
    creditor_count: int = data.get("creditor_count") or 0

    today = datetime.now(tz=timezone.utc).strftime("%a %-d %b %Y")
    header = (
        f"*Daily Creditor Report — {today}*\n"
        f"Processed {creditor_count} company creditor{'s' if creditor_count != 1 else ''} "
        f"from {debtor_count} bankruptc{'ies' if debtor_count != 1 else 'y'}."
    )

    if not rows:
        post_slack(bot_token, channel_id, header + "\n\nNo new creditors in this window.")
        return

    # Group by debtor; sort debtors by filing_date DESC; creditors within by claim DESC.
    by_debtor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_debtor[row.get("debtor_name") or "(unknown debtor)"].append(row)

    def _debtor_filing_date(name: str) -> str:
        first = by_debtor[name][0]
        return first.get("filing_date") or ""

    sorted_debtors = sorted(by_debtor.keys(), key=_debtor_filing_date, reverse=True)

    for name in sorted_debtors:
        by_debtor[name].sort(key=lambda r: _parse_claim(r.get("claim") or ""), reverse=True)

    if creditor_count <= _SPLIT_THRESHOLD:
        # Single message: header + all debtor blocks.
        blocks = [header]
        for name in sorted_debtors:
            blocks.append("---")
            blocks.append(_format_debtor_block(name, by_debtor[name]))
        post_slack(bot_token, channel_id, "\n\n".join(blocks))
    else:
        # Multi-message: header first, then one message per debtor group.
        post_slack(bot_token, channel_id, header)
        for name in sorted_debtors:
            body = "---\n\n" + _format_debtor_block(name, by_debtor[name])
            post_slack(bot_token, channel_id, body)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_pipeline_settings()

    try:
        data = _call_grouped_report_rpc(
            settings.supabase_url,
            settings.supabase_service_role_key,
            settings.supabase_http_timeout_sec,
        )
    except Exception as exc:
        logger.error("Failed to call grouped report RPC: %s", exc)
        send_error_alert(
            stage="report.py — RPC",
            error=str(exc),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
        sys.exit(1)

    try:
        _build_and_post_report(settings.slack_bot_token, settings.slack_channel_id, data)
    except Exception as exc:
        logger.error("Failed to post Slack report: %s", exc)
        send_error_alert(
            stage="report.py — Slack post",
            error=str(exc),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
        sys.exit(1)

    logger.info("Daily report posted successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
