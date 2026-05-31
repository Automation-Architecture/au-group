"""Unit tests for pipeline/report.py formatting logic (KD-61 AC#3)."""

from unittest.mock import call, patch

import pytest
from pipeline.report import (
    _SPLIT_THRESHOLD,
    _build_and_post_report,
    _format_creditor_line,
    _parse_claim,
)


# ---------------------------------------------------------------------------
# _parse_claim
# ---------------------------------------------------------------------------


class TestParseClaim:
    def test_parses_formatted_dollar_string(self):
        assert _parse_claim("$1,234,567.89") == pytest.approx(1_234_567.89)

    def test_returns_zero_for_empty(self):
        assert _parse_claim("") == 0.0

    def test_returns_zero_for_invalid(self):
        assert _parse_claim("n/a") == 0.0


# ---------------------------------------------------------------------------
# _format_creditor_line
# ---------------------------------------------------------------------------


class TestFormatCreditorLine:
    def _row(self, **kwargs):
        base = {
            "creditor": "Acme Corp",
            "city": "Austin",
            "state": "TX",
            "claim": "$10,000.00",
            "tier": 1,
            "status": "Active",
            "zoominfo_url": "",
        }
        base.update(kwargs)
        return base

    def test_null_tier_renders_em_dash(self):
        line = _format_creditor_line(self._row(tier=None))
        assert "—" in line

    def test_numeric_tier_renders_as_string(self):
        line = _format_creditor_line(self._row(tier=2))
        assert "2" in line

    def test_zoominfo_url_omitted_when_empty_string(self):
        line = _format_creditor_line(self._row(zoominfo_url=""))
        assert "ZoomInfo" not in line

    def test_zoominfo_url_omitted_when_none(self):
        line = _format_creditor_line(self._row(zoominfo_url=None))
        assert "ZoomInfo" not in line

    def test_zoominfo_url_included_when_present(self):
        line = _format_creditor_line(self._row(zoominfo_url="https://www.zoominfo.com/c/acme/123"))
        assert "ZoomInfo" in line
        assert "https://www.zoominfo.com/c/acme/123" in line


# ---------------------------------------------------------------------------
# _build_and_post_report — sorting
# ---------------------------------------------------------------------------


def _make_rows(debtor_name: str, filing_date: str, creditors: list[dict]) -> list[dict]:
    """Build row dicts for one debtor with shared header fields."""
    return [
        {
            "debtor_name": debtor_name,
            "filing_date": filing_date,
            "case_number": "25-00001",
            "creditor": c["creditor"],
            "city": "Austin",
            "state": "TX",
            "claim": c["claim"],
            "tier": 1,
            "status": "Active",
            "zoominfo_url": "",
        }
        for c in creditors
    ]


class TestDebtorSortByFilingDateDesc:
    def test_newer_debtor_appears_first_in_message(self):
        rows = (
            _make_rows("OldCo", "2025-01-01", [{"creditor": "Vendor A", "claim": "$1,000.00"}])
            + _make_rows("NewCo", "2025-06-01", [{"creditor": "Vendor B", "claim": "$2,000.00"}])
        )
        data = {"rows": rows, "debtor_count": 2, "creditor_count": 2}
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        # Single message (2 creditors <= 40). NewCo should appear before OldCo.
        assert len(posted_texts) == 1
        msg = posted_texts[0]
        assert msg.index("NewCo") < msg.index("OldCo")


class TestCreditorSortByClaimDescNumeric:
    def test_creditors_sorted_by_numeric_claim_not_string(self):
        # String sort: "$9,000" > "$10,000" — numeric sort must produce the opposite.
        rows = _make_rows(
            "DebCo",
            "2025-03-01",
            [
                {"creditor": "SmallVendor", "claim": "$9,000.00"},
                {"creditor": "BigVendor", "claim": "$10,000.00"},
            ],
        )
        data = {"rows": rows, "debtor_count": 1, "creditor_count": 2}
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        msg = posted_texts[0]
        # BigVendor ($10k) must appear before SmallVendor ($9k)
        assert msg.index("BigVendor") < msg.index("SmallVendor")


# ---------------------------------------------------------------------------
# _build_and_post_report — split threshold
# ---------------------------------------------------------------------------


def _make_data(creditor_count: int) -> dict:
    """Return a data dict with `creditor_count` creditors under a single debtor."""
    rows = _make_rows(
        "MegaCo",
        "2025-04-01",
        [{"creditor": f"Vendor{i}", "claim": f"${i * 1000:,}.00"} for i in range(1, creditor_count + 1)],
    )
    return {"rows": rows, "debtor_count": 1, "creditor_count": creditor_count}


class TestSingleMessageWhenBelowOrAtThreshold:
    def test_exactly_at_threshold_is_single_message(self):
        data = _make_data(_SPLIT_THRESHOLD)
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        assert len(posted_texts) == 1

    def test_one_below_threshold_is_single_message(self):
        data = _make_data(_SPLIT_THRESHOLD - 1)
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        assert len(posted_texts) == 1


class TestMultipleMessagesWhenAboveThreshold:
    def test_one_above_threshold_splits_into_multiple_messages(self):
        data = _make_data(_SPLIT_THRESHOLD + 1)
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        # Header message + at least one debtor message
        assert len(posted_texts) >= 2

    def test_header_posted_first_on_split(self):
        data = _make_data(_SPLIT_THRESHOLD + 1)
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        assert "Daily Creditor Report" in posted_texts[0]


# ---------------------------------------------------------------------------
# _build_and_post_report — empty rows
# ---------------------------------------------------------------------------


class TestEmptyRows:
    def test_no_rows_posts_no_new_creditors_message(self):
        data = {"rows": [], "debtor_count": 0, "creditor_count": 0}
        posted_texts = []

        with patch("pipeline.report.post_slack", side_effect=lambda bt, ch, txt: posted_texts.append(txt)):
            _build_and_post_report("xoxb-test", "C123", data)

        assert len(posted_texts) == 1
        assert "No new creditors" in posted_texts[0]
