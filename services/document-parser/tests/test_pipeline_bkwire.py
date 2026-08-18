"""Unit tests for pipeline/bkwire.py — the CSV feed that replaces PACER retrieval.

Shapes here come from a real 2026-08-04 BKwire export (100 rows, 9 cases,
91 distinct creditors), including its dirty values.
"""

from decimal import Decimal

import httpx
import pytest
from pipeline.bkwire import (
    BkwireFormatError,
    filter_rows,
    format_address,
    group_by_case,
    ingest_text,
    normalize_state,
    parse_csv,
    parse_loss,
)

from pipeline import bkwire

_HEADER = ("Date Added,Date Filed,Impacted Business,BKwire Zone,City,State,"
           "Case Number,Corporate Bankruptcy,Loss\n")


def _csv(*rows: str) -> str:
    return _HEADER + "".join(r if r.endswith("\n") else r + "\n" for r in rows)


_ROW = ('2026-08-04,2026-08-03,HIDALGO COUNTY TAX ASSESSOR,Business Services,'
        'Edinburg,TX,7:2026bk70239,"AGD, L.P.","$3,524"')


# ---------------------------------------------------------------------------
# parse_loss
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("$3,524", Decimal("3524")),
    ("$2,300,000", Decimal("2300000")),
    ("$104", Decimal("104")),
    ("$1,234.56", Decimal("1234.56")),
    ("", None),
    (None, None),
    ("n/a", None),
    ("$", None),
])
def test_parse_loss(raw, expected):
    assert parse_loss(raw) == expected


# ---------------------------------------------------------------------------
# normalize_state / format_address
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("TX", "TX"),
    ("tx", "TX"),
    (" NY ", "NY"),
    # Real value from the sample export — must not reach a varchar(2) column.
    ("see petition", None),
    ("", None),
    (None, None),
])
def test_normalize_state(raw, expected):
    assert normalize_state(raw) == expected


def test_format_address_carries_the_state_for_the_report():
    # au_group_parse_creditor_state reads the state back out of the address,
    # so the ", ST" suffix is load-bearing, not cosmetic.
    assert format_address("Edinburg", "TX") == "Edinburg, TX"
    assert format_address("Edinburg", None) == "Edinburg"
    assert format_address("", None) is None


# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------

def test_parse_csv_reads_a_row():
    rows, warnings = parse_csv(_csv(_ROW))
    assert warnings == []
    row = rows[0]
    assert row.creditor == "HIDALGO COUNTY TAX ASSESSOR"
    assert row.debtor == "AGD, L.P."
    assert row.case_number == "7:2026bk70239"
    assert row.state == "TX"
    assert row.claim_amount == Decimal("3524")
    assert row.line_number == 2


def test_parse_csv_rejects_a_file_that_is_not_a_bkwire_export():
    # Ingesting an unrelated CSV as creditor leads is far worse than failing.
    with pytest.raises(BkwireFormatError) as exc:
        parse_csv("name,amount\nACME,100\n")
    assert "Impacted Business" in str(exc.value)


def test_parse_csv_keeps_a_creditor_whose_state_is_unusable():
    row = _ROW.replace(",Edinburg,TX,", ",Edinburg,see petition,")
    rows, warnings = parse_csv(_csv(row))
    # The lead is still good — only the state is unknown.
    assert len(rows) == 1 and rows[0].state is None
    assert "see petition" in warnings[0]


def test_parse_csv_skips_rows_with_no_creditor_or_case():
    rows, warnings = parse_csv(_csv(
        '2026-08-04,2026-08-03,,Business Services,Edinburg,TX,7:2026bk70239,"AGD, L.P.","$1"',
        _ROW,
    ))
    assert len(rows) == 1
    assert "skipped" in warnings[0]


# ---------------------------------------------------------------------------
# group_by_case — the repeated-creditor case
# ---------------------------------------------------------------------------

def test_repeated_creditor_in_one_case_has_its_claims_summed():
    """The export really does repeat a creditor with different Loss values.

    9 of the sample's 100 rows do this — separate claims, not duplicates — and
    the creditor's true exposure is the sum.
    """
    groups, combined = group_by_case(parse_csv(_csv(
        _ROW,
        _ROW.replace('"$3,524"', '"$3,066"'),
    ))[0])
    assert combined == 1
    creditors = groups[0].creditors
    assert len(creditors) == 1
    assert creditors[0]["claim_amount"] == "6590"
    # Both source rows stay traceable.
    assert creditors[0]["source_line_numbers"] == [2, 3]


def test_repeated_creditor_match_ignores_case_and_padding():
    groups, combined = group_by_case(parse_csv(_csv(
        _ROW,
        _ROW.replace("HIDALGO COUNTY TAX ASSESSOR", " hidalgo county tax assessor "),
    ))[0])
    assert combined == 1 and len(groups[0].creditors) == 1


def test_same_creditor_in_a_different_case_is_not_combined():
    other = _ROW.replace("7:2026bk70239", "4:2026bk42690").replace('"AGD, L.P."', '"Big J, LLC"')
    groups, combined = group_by_case(parse_csv(_csv(_ROW, other))[0])
    assert combined == 0
    assert len(groups) == 2


def test_grouping_splits_by_case_and_keeps_the_debtor():
    rows, _ = parse_csv(_csv(
        _ROW,
        _ROW.replace("HIDALGO COUNTY TAX ASSESSOR", "Tommy HO"),
    ))
    groups, _ = group_by_case(rows)
    assert len(groups) == 1
    assert groups[0].debtor == "AGD, L.P."
    assert len(groups[0].creditors) == 2


def test_missing_claim_amount_does_not_block_the_sum():
    groups, _ = group_by_case(parse_csv(_csv(
        _ROW.replace('"$3,524"', ""),
        _ROW.replace('"$3,524"', '"$100"'),
    ))[0])
    assert groups[0].creditors[0]["claim_amount"] == "100"


# ---------------------------------------------------------------------------
# filter_rows
# ---------------------------------------------------------------------------

def test_state_filter_is_off_by_default():
    rows, _ = parse_csv(_csv(_ROW))
    kept, dropped = filter_rows(rows, None)
    assert len(kept) == 1 and dropped == 0


def test_state_filter_drops_out_of_scope_creditors():
    rows, _ = parse_csv(_csv(_ROW))
    kept, dropped = filter_rows(rows, {"NY", "NJ"})
    assert kept == [] and dropped == 1


# ---------------------------------------------------------------------------
# ingest_text
# ---------------------------------------------------------------------------

class _Settings:
    supabase_url = "https://sb.example"
    supabase_service_role_key = "svc"
    supabase_http_timeout_sec = 5.0
    bkwire_chapter_type = "unknown"
    bkwire_unknown_state = "XX"
    bkwire_state_filter = ""


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "http://x")
            raise httpx.HTTPStatusError("e", request=req,
                                        response=httpx.Response(self.status_code, request=req))


class _FakeClient:
    def __init__(self, calls, responses):
        self._calls = calls
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, **kwargs):
        self._calls.append({"url": url, "json": kwargs.get("json")})
        for fragment, resp in self._responses.items():
            if fragment in url:
                return resp() if callable(resp) else resp
        return _FakeResp(None)


def _patch(monkeypatch, responses):
    calls: list[dict] = []
    monkeypatch.setattr(bkwire.httpx, "Client",
                        lambda *a, **k: _FakeClient(calls, responses))
    return calls


_RPC = {
    "au_group_upsert_bankruptcy": _FakeResp("bk-uuid-1"),
    "au_group_merge_creditor_matrix": _FakeResp(2),
    "au_group_enqueue_job": _FakeResp(None),
}


def test_ingest_upserts_merges_and_enqueues(monkeypatch):
    calls = _patch(monkeypatch, _RPC)
    result = ingest_text(_csv(_ROW, _ROW.replace("HIDALGO COUNTY TAX ASSESSOR", "Tommy HO")),
                         settings=_Settings())
    assert result.cases == 1
    assert result.creditors_merged == 2
    assert [c["url"].rsplit("/", 1)[-1] for c in calls] == [
        "au_group_upsert_bankruptcy",
        "au_group_merge_creditor_matrix",
        "au_group_enqueue_job",
    ]


def test_ingest_sends_the_documented_sentinels(monkeypatch):
    calls = _patch(monkeypatch, _RPC)
    ingest_text(_csv(_ROW), settings=_Settings())
    payload = calls[0]["json"]
    assert payload["p_case_number"] == "7:2026bk70239"
    assert payload["p_debtor_name"] == "AGD, L.P."
    assert payload["p_court_district"] == "BKWIRE"   # the feed carries no court
    assert payload["p_state"] == "XX"                # nor the debtor's state
    # The feed carries no chapter, so record that rather than fabricate '11'
    # (enum member added in migration 20260818135336).
    assert payload["p_chapter_type"] == "unknown"


def test_ingest_hands_the_creditor_address_to_the_merge_rpc(monkeypatch):
    calls = _patch(monkeypatch, _RPC)
    ingest_text(_csv(_ROW), settings=_Settings())
    creditor = calls[1]["json"]["p_creditors"][0]
    assert creditor["creditor_name"] == "HIDALGO COUNTY TAX ASSESSOR"
    assert creditor["address"] == "Edinburg, TX"
    assert creditor["claim_amount"] == "3524"


def test_dry_run_writes_nothing(monkeypatch):
    calls = _patch(monkeypatch, _RPC)
    result = ingest_text(_csv(_ROW), dry_run=True, settings=_Settings())
    assert result.cases == 1
    assert calls == []


def test_one_failing_case_does_not_drop_the_rest_of_the_file(monkeypatch):
    responses = dict(_RPC)
    seen = {"n": 0}

    def _flaky():
        seen["n"] += 1
        return _FakeResp("bk-uuid", status_code=500 if seen["n"] == 1 else 200)

    responses["au_group_upsert_bankruptcy"] = _flaky
    _patch(monkeypatch, responses)
    other = _ROW.replace("7:2026bk70239", "4:2026bk42690").replace('"AGD, L.P."', '"Big J, LLC"')
    result = ingest_text(_csv(_ROW, other), settings=_Settings())
    assert len(result.errors) == 1
    assert result.creditors_merged == 2      # the second case still landed


def test_state_filter_setting_is_applied(monkeypatch):
    calls = _patch(monkeypatch, _RPC)

    class _Filtered(_Settings):
        bkwire_state_filter = "NY, NJ"

    result = ingest_text(_csv(_ROW), settings=_Filtered())
    assert result.cases == 0
    assert calls == []
