import pytest

from app.dedup.creditors import (
    _similarity,
    _sum_claim_amounts,
    deduplicate_creditors,
    normalize_creditor_key,
)
from app.models.schemas import CreditorRow


def test_normalize_creditor_key_strips_punctuation() -> None:
    key = normalize_creditor_key("ABC Corp.", "123 Main St., NY")
    assert key == "abc corp 123 main st ny"


def test_merge_abc_corp_variants_same_address() -> None:
    rows = [
        CreditorRow(
            creditor_name="ABC Corp",
            address="123 Main St",
            claim_amount=100.0,
            source_line_numbers=[1],
        ),
        CreditorRow(
            creditor_name="ABC Corporation",
            address="123 Main St",
            claim_amount=50.0,
            source_line_numbers=[2],
        ),
    ]
    deduped, stats = deduplicate_creditors(rows, threshold=85)
    assert stats.original_count == 2
    assert stats.deduped_count == 1
    assert stats.duplicates_removed == 1
    assert deduped[0].claim_amount == 150.0
    assert deduped[0].source_line_numbers == [1, 2]
    assert "ABC Corp" in (deduped[0].dedup_audit or {}).get("merged_names", [])
    assert "ABC Corporation" in (deduped[0].dedup_audit or {}).get("merged_names", [])


def test_does_not_merge_different_addresses() -> None:
    rows = [
        CreditorRow(creditor_name="ABC Corp", address="123 Main St", claim_amount=100.0),
        CreditorRow(creditor_name="ABC Corp", address="456 Oak Ave", claim_amount=50.0),
    ]
    deduped, stats = deduplicate_creditors(rows, threshold=85)
    assert stats.deduped_count == 2


def test_transitive_cluster_of_three() -> None:
    rows = [
        CreditorRow(creditor_name="Acme LLC", address="1 A St", claim_amount=10.0),
        CreditorRow(creditor_name="Acme L.L.C.", address="1 A Street", claim_amount=20.0),
        CreditorRow(creditor_name="Acme Limited", address="1 A St", claim_amount=30.0),
    ]
    deduped, stats = deduplicate_creditors(rows, threshold=75)
    assert stats.deduped_count == 1
    assert deduped[0].claim_amount == 60.0


def test_all_null_claims_stays_null() -> None:
    rows = [
        CreditorRow(creditor_name="Foo Inc", address="1 St"),
        CreditorRow(creditor_name="Foo, Inc.", address="1 St"),
    ]
    deduped, _ = deduplicate_creditors(rows, threshold=85)
    assert len(deduped) == 1
    assert deduped[0].claim_amount is None


def test_similarity_zero_when_normalized_keys_empty() -> None:
    left = CreditorRow(creditor_name="!!!", address=None)
    right = CreditorRow(creditor_name="???", address=None)
    assert _similarity(left, right) == 0.0


def test_sum_claim_amounts_empty_list_returns_none() -> None:
    assert _sum_claim_amounts([]) is None


def test_deduplicate_empty_list() -> None:
    deduped, stats = deduplicate_creditors([])
    assert deduped == []
    assert stats.original_count == 0
    assert stats.deduped_count == 0


def test_single_row_unchanged() -> None:
    rows = [CreditorRow(creditor_name="Solo Co", address="1 St", claim_amount=1.0)]
    deduped, stats = deduplicate_creditors(rows)
    assert len(deduped) == 1
    assert deduped[0].creditor_name == "Solo Co"
    assert deduped[0].claim_amount == 1.0
    assert deduped[0].dedup_audit is None
    assert stats.duplicates_removed == 0


def test_merge_uses_highest_confidence_canonical_row() -> None:
    rows = [
        CreditorRow(
            creditor_name="Low Confidence LLC",
            address="1 Main St",
            claim_amount=10.0,
            confidence_score=0.4,
        ),
        CreditorRow(
            creditor_name="High Confidence LLC",
            address="1 Main St",
            claim_amount=20.0,
            confidence_score=0.95,
        ),
    ]
    deduped, stats = deduplicate_creditors(rows, threshold=85)
    assert stats.deduped_count == 1
    assert deduped[0].creditor_name == "High Confidence LLC"
    assert deduped[0].confidence_score == pytest.approx(0.95)
