from app.extractors.form201 import extract_form201
from app.validation.engine import validate_form201

SAMPLE_FORM201 = """
Official Form 201
Voluntary Petition
Debtor 1: Michael J Lombardo
City: New York
State: NY
United States Bankruptcy Court for the Southern District of New York
NAICS: 531120
estimated assets $1,000,000 to $10,000,000
estimated liabilities $10,000,000 to $50,000,000
200 to 999 creditors
"""


def test_extract_form201_fields() -> None:
    data = extract_form201(SAMPLE_FORM201)
    assert data.debtor_name == "Michael J Lombardo"
    assert data.city == "New York"
    assert data.state == "NY"
    assert data.industry_code == "531120"
    assert data.estimated_assets is not None
    assert data.estimated_assets.min_usd == 1_000_000


def test_validate_form201_high_confidence() -> None:
    data = extract_form201(SAMPLE_FORM201)
    result = validate_form201(data)
    assert result.confidence_score >= 0.85
    assert result.level in ("high", "medium")
