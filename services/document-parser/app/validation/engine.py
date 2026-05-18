from app.core.config import get_settings
from app.models.schemas import CreditorRow, Form201Data, ValidationResult

FORM201_REQUIRED_FIELDS = (
    "debtor_name",
    "city",
    "state",
    "court_district",
    "industry_code",
    "estimated_assets",
    "estimated_liabilities",
    "estimated_creditor_count",
)

CREDITOR_REQUIRED_FIELDS = ("creditor_name",)


def _missing_form201_fields(form201: Form201Data) -> list[str]:
    missing: list[str] = []
    data = form201.model_dump()
    for field in FORM201_REQUIRED_FIELDS:
        value = data.get(field)
        if value is None:
            missing.append(field)
        elif isinstance(value, dict) and not any(value.values()):
            missing.append(field)
    return missing


def validate_form201(form201: Form201Data, *, ocr_used: bool = False) -> ValidationResult:
    missing = _missing_form201_fields(form201)
    total = len(FORM201_REQUIRED_FIELDS)
    present = total - len(missing)
    confidence = present / total if total else 0.0

    if len(missing) == 0:
        level = "high"
    elif len(missing) <= 2:
        level = "medium"
    else:
        level = "low"

    settings = get_settings()
    manual_review = (
        confidence < settings.confidence_review_threshold
        or "debtor_name" in missing
        or (ocr_used and confidence < 0.9)
    )

    return ValidationResult(
        confidence_score=round(confidence, 4),
        manual_review_required=manual_review,
        missing_fields=missing,
        level=level,
    )


def validate_creditor_matrix(creditors: list[CreditorRow]) -> ValidationResult:
    if not creditors:
        return ValidationResult(
            confidence_score=0.0,
            manual_review_required=True,
            missing_fields=["creditors"],
            level="low",
        )
    valid_rows = sum(1 for row in creditors if row.creditor_name)
    confidence = valid_rows / len(creditors)
    missing: list[str] = []
    if valid_rows < len(creditors):
        missing.append("creditor_name")

    settings = get_settings()
    manual_review = confidence < settings.confidence_review_threshold

    level = "high" if confidence >= 0.95 else "medium" if confidence >= 0.8 else "low"
    return ValidationResult(
        confidence_score=round(confidence, 4),
        manual_review_required=manual_review,
        missing_fields=missing,
        level=level,
    )


def should_review_for_error(reason: str) -> ValidationResult:
    return ValidationResult(
        confidence_score=0.0,
        manual_review_required=True,
        missing_fields=[reason],
        level="low",
    )
