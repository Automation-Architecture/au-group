import re

from app.models.schemas import FilingType

FORM_201_ANCHORS = (
    r"official\s+form\s+201",
    r"voluntary\s+petition",
    r"form\s+201",
)

CREDITOR_MATRIX_ANCHORS = (
    r"list\s+of\s+creditors",
    r"creditor\s+matrix",
    r"form\s+204",
    r"20\s+largest\s+unsecured",
)

SCHEDULE_ANCHORS = (
    r"schedule\s+[a-f]",
    r"schedule\s+e\s*/\s*f",
    r"form\s+206",
)

SOFA_ANCHORS = (
    r"statement\s+of\s+financial\s+affairs",
    r"\bsofa\b",
)


def _score_patterns(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.lower()
    score = 0
    for pattern in patterns:
        if re.search(pattern, lowered):
            score += 1
    return score


def classify_filing_type(
    text: str,
    *,
    docket_hint: FilingType | None = None,
) -> FilingType:
    if docket_hint and docket_hint != FilingType.UNKNOWN:
        return docket_hint

    scores = {
        FilingType.FORM_201: _score_patterns(text, FORM_201_ANCHORS),
        FilingType.CREDITOR_MATRIX: _score_patterns(text, CREDITOR_MATRIX_ANCHORS),
        FilingType.SCHEDULE: _score_patterns(text, SCHEDULE_ANCHORS),
        FilingType.SOFA: _score_patterns(text, SOFA_ANCHORS),
    }
    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return FilingType.UNKNOWN
    return best_type
