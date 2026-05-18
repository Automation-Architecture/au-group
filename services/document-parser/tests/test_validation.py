from app.models.schemas import CreditorRow, Form201Data
from app.validation.engine import validate_creditor_matrix, validate_form201


def test_validate_empty_creditors() -> None:
    result = validate_creditor_matrix([])
    assert result.manual_review_required is True
    assert result.confidence_score == 0.0


def test_validate_partial_form201() -> None:
    data = Form201Data(debtor_name="Test Co")
    result = validate_form201(data)
    assert result.manual_review_required is True
    assert len(result.missing_fields) > 0


def test_validate_creditors_ok() -> None:
    rows = [
        CreditorRow(creditor_name="Acme Inc", entity_type="company"),
        CreditorRow(creditor_name="Beta LLC", entity_type="company"),
    ]
    result = validate_creditor_matrix(rows)
    assert result.confidence_score == 1.0
