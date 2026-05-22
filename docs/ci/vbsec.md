# vbsec in CI/CD

[vbsec](https://github.com/tanviet12/vbsec) is an agent skill for reasoning-first security review (`/vbs-scan-security`). This repo runs a **deterministic CI layer** that exercises all **21 vbsec rule IDs** on every security workflow run.

## Two layers

| Layer | Where | What |
|-------|--------|------|
| **CI (deterministic)** | `.github/workflows/ci-security.yml` | All 21 rule IDs via gitleaks, bandit, pip-audit, npm audit, patterns → `vbsec-reports/ci-scan.json` |
| **Full vbsec (agent)** | Local: `scripts/install-vbsec-skill.sh` | Same rules with L1–L4 data-flow reasoning; deeper, fewer false negatives |

vbsec’s disclaimer applies: CI scan is a first line of defense, not a professional audit.

## CI behavior

- **Trigger:** **Every** PR/push via `ci.yml`; also `deploy-n8n`, `deploy-supabase`, `deploy-parser-railway` before deploy
- **Scope:** `diff` on PR (vs base branch); `workflow_dispatch` with `scope=all` for full repo
- **Pin:** [`.vbsec-ref`](../../.vbsec-ref) or repo variable `VBSEC_REF` (vbsec git ref for rule sync)
- **Fail:** `verdict: FAIL` (any CRITICAL finding) fails the job
- **Artifact:** `vbsec-ci-report` → `vbsec-reports/ci-scan.json` (includes `rules_coverage` for all 21 IDs)

## Rule mapping (CI — all 21)

| vbsec rule ID | CI implementation |
|---------------|-------------------|
| `HARDCODED-SECRET` | gitleaks + JSON workflow patterns |
| `SQL-INJECTION` | bandit B608 + SQL/migration patterns |
| `XSS` | HTML/DOM sink patterns (TS/JS/templates) |
| `IDOR` | FastAPI route heuristic (path param without auth) |
| `SLOPSQUATTING` | Typosquat package name list in requirements / lockfiles |
| `BRUTE-FORCE` | Login route without `@limiter.limit` pattern |
| `MASS-ASSIGNMENT` | `**kwargs` / `Object.assign` from request patterns |
| `INSECURE-DESERIALIZATION` | bandit B301 + pickle/yaml/marshal patterns |
| `SSRF` | HTTP client + **request-derived** URL patterns (skips `url_safety.py`, Supabase/readiness clients) |
| `PATH-TRAVERSAL` | Dynamic `open()` / `Path()` patterns |
| `CSRF` | Session cookie without SameSite patterns |
| `BROKEN-ACCESS-CONTROL` | bandit B501/B506/B701 + unauthenticated mutating routes |
| `WEAK-PASSWORD-HASHING` | bandit B303/B324 + MD5/SHA1 password patterns |
| `JWT-NONE-ALGORITHM` | `verify=False` / `none` algorithm patterns |
| `CORS-MISCONFIG` | Wildcard/echo origin + credentials patterns |
| `UNRESTRICTED-FILE-UPLOAD` | UploadFile/multer without validation patterns |
| `VERBOSE-ERROR-DEBUG-MODE` | bandit B201 + debug env patterns |
| `MISSING-RATE-LIMIT` | AI/email/SMS call without limiter patterns |
| `RACE-CONDITION` | check-then-act file write heuristic |
| `OUTDATED-DEPENDENCY` | [pip-audit](../../services/document-parser/pip-audit.toml) (parser) + npm audit (e2e lockfile) |
| `COMMAND-INJECTION` | bandit B102/B307 + shell=True / os.system patterns |

Patterns live in [`scripts/ci/vbsec_rules.py`](../../scripts/ci/vbsec_rules.py); orchestration in [`scripts/ci/vbsec_ci_scan.py`](../../scripts/ci/vbsec_ci_scan.py).

## Local commands

```bash
pip install bandit==1.8.3 pip-audit==2.9.0
# install gitleaks CLI separately

python3 scripts/ci/vbsec_ci_scan.py --scope all --fail-on critical

# Full vbsec skill (Claude/Cursor) — deeper reasoning on same rule set
./scripts/install-vbsec-skill.sh
# then: /vbs-scan-security lang=en
```

## Related

- [`requirements-traceability.md`](requirements-traceability.md) — AU_GROUP-8.5
- [`ci-parser.yml`](../../.github/workflows/ci-parser.yml) — also runs pip-audit on parser-only PRs
- [`pip-audit.toml`](../../services/document-parser/pip-audit.toml) — parser CVE ignore list for OUTDATED-DEPENDENCY
