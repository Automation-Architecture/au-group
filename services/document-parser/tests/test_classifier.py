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


def test_combined_petition_misclassifies_without_a_hint() -> None:
    """The failure KD-82 exists to prevent — documented, not hypothetical.

    RECAP returns the whole voluntary petition for most cases, because the
    20-largest list is filed inside it rather than as a standalone document.
    Anchor scoring then picks FORM_201, the router runs Form 201 extraction, and
    zero creditors come out while every stage reports success.
    """
    combined = (
        "Official Form 201\n"
        "Voluntary Petition for Non-Individuals Filing for Bankruptcy\n"
        "...\n"
        "Official Form 204\n"
        "List of Creditors Who Have the 20 Largest Unsecured Claims\n"
    )
    assert classify_filing_type(combined) == FilingType.FORM_201
    # The hint is what makes the creditor list reachable.
    assert (
        classify_filing_type(combined, docket_hint=FilingType.CREDITOR_MATRIX)
        == FilingType.CREDITOR_MATRIX
    )
