"""Unit tests for offline company name normalization (KD-20 / KD-24 mirror)."""

from app.enrichment.company_name import (
    CompanyNameRule,
    build_company_lookup_cache_key,
    normalize_company_name,
)


def test_normalize_strips_inc_suffix() -> None:
    assert normalize_company_name("Acme Inc.") == "ACME"


def test_normalize_empty_returns_empty() -> None:
    assert normalize_company_name("") == ""
    assert normalize_company_name("   ") == ""


def test_normalize_alias_rule() -> None:
    rules = (
        CompanyNameRule(rule_type="alias", pattern="BIG CO", replacement="BIG COMPANY"),
    )
    assert normalize_company_name("Big Co", rules=rules) == "BIG COMPANY"


def test_normalize_token_replace_rule() -> None:
    rules = (CompanyNameRule(rule_type="token_replace", pattern=r"\bCO\b", replacement="COMPANY"),)
    assert normalize_company_name("Acme Co", rules=rules) == "ACME COMPANY"


def test_cache_key_stable_for_same_inputs() -> None:
    key_a = build_company_lookup_cache_key("Acme Inc.", "123 Main St")
    key_b = build_company_lookup_cache_key("Acme Inc.", "123 Main St")
    assert key_a == key_b
    assert len(key_a) == 32


def test_cache_key_differs_when_address_changes() -> None:
    key_a = build_company_lookup_cache_key("Acme Inc.", "123 Main St")
    key_b = build_company_lookup_cache_key("Acme Inc.", "456 Oak Ave")
    assert key_a != key_b
