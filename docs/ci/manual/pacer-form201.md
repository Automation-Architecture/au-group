# Manual verification — Form 201 debtor metadata (AC-1.2)

**Requirement:** FR-1.2 / AC-1.2 — debtor metadata correctly extracted from **95%+** of filings.

**Automated partial coverage:** `services/document-parser` unit tests (`tests/test_*` for Form 201 / debtor fields). This script is the **sampling gate** for labeled fixtures before release.

## When to run

- Sprint review when parser extraction logic changes
- Before raising `cov-fail-under` or promoting parser deploy
- After adding new state/court PDF fixtures

## Steps

1. Ensure labeled fixtures exist under `services/document-parser/tests/fixtures/` (or a dedicated `fixtures/form201-labeled/` set agreed with QA).
2. From repo root:

```bash
cd services/document-parser
pip install -r requirements-dev.txt
pytest tests/ -q -k "form201 or form_201 or debtor" --tb=no
```

3. Run sampling against **held-out** PDFs (not in unit test fixtures):

```bash
# Example: batch score script (add labeled CSV: case_id,expected_debtor_name,expected_state)
python3 scripts/ci/score-form201-sample.py \
  --fixtures-dir tests/fixtures/form201-labeled \
  --min-accuracy 0.95
```

If `score-form201-sample.py` is not yet present, record results manually in the sprint review table below.

## Record results

| Date | Fixture set | N samples | Accuracy | Pass (≥95%) | Reviewer |
|------|-------------|-----------|----------|-------------|----------|
| | | | | | |

## Fail criteria

- Accuracy **< 95%** on labeled sample → do not merge parser changes; open defect in Jira (AU_GROUP-2 / AU_GROUP-3).

## Related

- [Requirements traceability](../requirements-traceability.md) — AC-1.2
- [CI — document-parser](../../../.github/workflows/ci-parser.yml)
