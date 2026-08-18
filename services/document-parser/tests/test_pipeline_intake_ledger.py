"""Unit tests for intake's known-miss ledger (KD-83).

Under a CourtListener call budget a run only reaches part of the window, so
forward progress depends on remembering which cases were already looked up.
A filing-date watermark cannot express that (the _CL_LOOKBACK_DAYS overlap means
the attempted prefix usually sits at or before the watermark), and advancing the
watermark over un-attempted cases would lose them for good — discovery never
returns a case once the watermark passes its filing date.
"""

from datetime import date

from pipeline.intake import (
    _LEDGER_MAX_ENTRIES,
    _MISS_MAX_ATTEMPTS,
    _prune_missed_ledger,
    _record_miss,
    _should_skip_missed,
)

_TODAY = date(2026, 8, 18)


# ---------------------------------------------------------------------------
# _should_skip_missed — spend quota only on cases we know nothing about
# ---------------------------------------------------------------------------

def test_unknown_case_is_never_skipped():
    assert _should_skip_missed({}, _TODAY) is False


def test_case_missed_once_on_an_earlier_day_is_retried():
    # RECAP is an upload-as-purchased archive: a document absent yesterday can
    # be there today, so one retry is worth the call.
    entry = {"filed": "2026-08-10", "attempts": 1, "last": "2026-08-17"}
    assert _should_skip_missed(entry, _TODAY) is False


def test_case_already_attempted_today_is_not_re_checked():
    entry = {"filed": "2026-08-10", "attempts": 1, "last": _TODAY.isoformat()}
    assert _should_skip_missed(entry, _TODAY) is True


def test_case_is_suppressed_once_the_retry_allowance_is_used():
    entry = {"filed": "2026-08-10", "attempts": _MISS_MAX_ATTEMPTS, "last": "2026-08-17"}
    assert _should_skip_missed(entry, _TODAY) is True


def test_malformed_attempt_count_does_not_crash_the_run():
    assert _should_skip_missed({"attempts": "2", "last": "2026-08-01"}, _TODAY) is True


# ---------------------------------------------------------------------------
# _record_miss
# ---------------------------------------------------------------------------

def test_record_miss_creates_then_bumps():
    ledger: dict[str, dict] = {}
    _record_miss(ledger, "26-16653", "2026-08-10", _TODAY)
    assert ledger["26-16653"] == {"filed": "2026-08-10", "attempts": 1,
                                  "last": _TODAY.isoformat()}
    _record_miss(ledger, "26-16653", "2026-08-10", date(2026, 8, 19))
    assert ledger["26-16653"]["attempts"] == 2
    assert ledger["26-16653"]["last"] == "2026-08-19"
    # The original filing date survives the bump — pruning keys off it.
    assert ledger["26-16653"]["filed"] == "2026-08-10"


def test_second_miss_reaches_the_suppression_threshold():
    ledger: dict[str, dict] = {}
    _record_miss(ledger, "26-1", "2026-08-10", date(2026, 8, 17))
    _record_miss(ledger, "26-1", "2026-08-10", _TODAY)
    assert _should_skip_missed(ledger["26-1"], date(2026, 8, 19)) is True


# ---------------------------------------------------------------------------
# _prune_missed_ledger — size control only
# ---------------------------------------------------------------------------

def test_prune_drops_entries_past_the_retention_window():
    ledger = {
        "old": {"filed": "2026-01-01", "attempts": 2, "last": "2026-01-02"},
        "recent": {"filed": "2026-08-10", "attempts": 1, "last": "2026-08-17"},
    }
    kept = _prune_missed_ledger(ledger, _TODAY)
    # Safe to forget: the watermark has long since passed that filing date, so
    # discovery will never return the case again.
    assert set(kept) == {"recent"}


def test_prune_tolerates_entries_with_no_filing_date():
    ledger = {"x": {"attempts": 1, "last": "2026-08-17"}}
    assert set(_prune_missed_ledger(ledger, _TODAY)) == {"x"}


def test_prune_caps_total_size_keeping_the_most_recent():
    ledger = {
        f"case-{i}": {"filed": "2026-08-10", "attempts": 1,
                      "last": f"2026-08-{(i % 18) + 1:02d}"}
        for i in range(_LEDGER_MAX_ENTRIES + 50)
    }
    kept = _prune_missed_ledger(ledger, _TODAY)
    assert len(kept) == _LEDGER_MAX_ENTRIES
    assert min(e["last"] for e in kept.values()) >= "2026-08-01"


def test_prune_leaves_a_small_ledger_untouched():
    ledger = {"a": {"filed": "2026-08-10", "attempts": 1, "last": "2026-08-17"}}
    assert _prune_missed_ledger(ledger, _TODAY) == ledger
