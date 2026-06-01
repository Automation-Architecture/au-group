from app.models.schemas import FilingType
from app.pipeline.filing_types import CREDITOR_LIST_FILING_TYPES, is_creditor_list_filing


def test_creditor_list_filing_types_include_matrix_and_schedule() -> None:
    assert FilingType.CREDITOR_MATRIX in CREDITOR_LIST_FILING_TYPES
    assert FilingType.SCHEDULE in CREDITOR_LIST_FILING_TYPES
    assert FilingType.FORM_201 not in CREDITOR_LIST_FILING_TYPES


def test_is_creditor_list_filing() -> None:
    assert is_creditor_list_filing(FilingType.CREDITOR_MATRIX) is True
    assert is_creditor_list_filing(FilingType.SCHEDULE) is True
    assert is_creditor_list_filing(FilingType.FORM_201) is False
    assert is_creditor_list_filing(FilingType.UNKNOWN) is False
    assert is_creditor_list_filing(None) is False
