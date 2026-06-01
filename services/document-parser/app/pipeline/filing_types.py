"""Filing types that produce creditor lists (matrix, Schedule E/F, etc.)."""

from app.models.schemas import FilingType

# KD-40 dedup + merge paths use this set. SCHEDULE is included so cache/dedup wiring
# is ready when AU_GROUP-3.1 parse_schedule_ef lands; extraction still matrix-only today.
CREDITOR_LIST_FILING_TYPES = frozenset(
    {
        FilingType.CREDITOR_MATRIX,
        FilingType.SCHEDULE,
    }
)


def is_creditor_list_filing(filing_type: FilingType | None) -> bool:
    return filing_type in CREDITOR_LIST_FILING_TYPES
