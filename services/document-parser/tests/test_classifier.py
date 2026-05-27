from app.classifiers.filing_type import classify_filing_type
from app.models.schemas import FilingType


def test_classify_form201() -> None:
    text = "Official Form 201\nVoluntary Petition for Non-Individuals"
    assert classify_filing_type(text) == FilingType.FORM_201


def test_classify_creditor_matrix() -> None:
    text = "List of Creditors Holding 20 Largest Unsecured Claims"
    assert classify_filing_type(text) == FilingType.CREDITOR_MATRIX


def test_classify_schedule_ef() -> None:
    text = (
        "Official Form 206E/F\n"
        "Schedule E/F — Creditors Holding Unsecured Nonpriority Claims"
    )
    assert classify_filing_type(text) == FilingType.SCHEDULE


def test_docket_hint_overrides() -> None:
    text = "random content"
    assert classify_filing_type(text, docket_hint=FilingType.FORM_201) == FilingType.FORM_201
