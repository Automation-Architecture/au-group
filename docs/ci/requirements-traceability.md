# Requirements traceability — CI/CD gates

Maps [PRD](../project/prd.md) acceptance criteria (AC), non-functional requirements (NFR), and Jira epic **AU_GROUP-8** to automated checks in GitHub Actions.

**Definition of Done (AU_GROUP-8):** Each story has a row below with `automated: yes|no|scheduled`. `yes` = failing check blocks merge when paths touch that artifact (or always for security).

| ID | Requirement summary | Automated | Workflow / job | Notes |
|----|---------------------|-----------|----------------|-------|
| **AC-1.1** | Daily PACER filings by 8 AM | partial | `au_group_target_states`, SYS-01B `au_group_list_pacer_poll_candidates`, SYS-01 gate | Admin-configurable states in Supabase; push workflow JSON to n8n cloud |
| **AC-1.2** | Form 201 debtor metadata 95%+ | no | `docs/ci/manual/pacer-form201.md` | Parser unit tests + manual 95% sampling |
| **AC-1.3** | Top 20 in Salesforce within 24h | scheduled | `smoke-e2e.yml` | End-to-end via n8n SYS-01→02→03 |
| **AC-1.4** | Company vs individual 90%+ | yes | `ci-parser` → pytest | `tests/test_classifier.py` |
| **AC-2.1** | Monitoring queue for new Ch.11 | partial | SYS-06 `gGRp6dF85A015TMH`, `au_group_diff_pacer_favorites` | 0 Code nodes; activate after Keith UAT (KD-68) |
| **AC-2.2** | Schedule F within 7 days | scheduled | `smoke-e2e.yml` | SYS-06/07 not in deploy manifest |
| **AC-2.3** | Alert context complete | no | — | Product/n8n alert nodes |
| **AC-2.4** | PACER favorites approval | partial | `docs/workflows/sys-07-pacer-favorites.md`, SYS-06/07 n8n | Deploy `deploy-mvp.mjs --wave=1`; manual Keith test |
| **AC-3.1** | Structured Schedule E/F 95%+ | partial | `ci-parser` → pytest | `tests/test_schedules.py`, `tests/test_api_schedule_ef.py` (happy path); 95% accuracy sampling still manual |
| **AC-3.2** | Simple list extraction | yes | `ci-parser` → pytest | `tests/test_creditor_matrix.py` |
| **AC-3.3** | OCR + low-confidence flag | yes | `ci-parser` → pytest | `tests/test_validation.py`, `tests/test_api_review.py`, `tests/test_pipeline_*.py` |
| **AC-3.4** | Page classification 90%+ | yes | `ci-parser` → pytest | `tests/test_classifier.py` |
| **AC-3.5** | Fuzzy dedup | yes | `ci-parser` → pytest | `tests/test_deduplicate_creditors.py`, `tests/test_api_creditor_dedup.py` (parse + extract/creditor-matrix), `app/dedup/creditors.py` |
| **AC-4.1** | ZoomInfo 80%+ match | partial | KD-20 migration + SYS-03 company HTTP | Production match-rate smoke (KD-53) |
| **AC-4.2** | Tier identification 95%+ | partial | `au_group_classify_company_tier`, SYS-03 RPC | Manual sampling vs PRD tiers |
| **AC-4.3** | Contacts 80%+ | partial | `au_group_upsert_zoom_info_contacts`, SYS-03 contact HTTP | Live ZoomInfo + KD-53 |
| **AC-4.4** | Fallback logic | partial | `au_group_list_contact_titles(..., true)` | n8n passes merged title list |
| **AC-4.5** | Canonical names | partial | `au_group_normalize_company_name` (KD-20) | Trade-name rules KD-24 deferred |
| **AC-5.1** | Salesforce match 95%+ | no | — | AU_GROUP-5 |
| **AC-5.2** | Bankruptcy event fields | no | — | n8n SYS-03 + SF |
| **AC-5.3** | Territory 100% | partial | `au_group_territory_assignments`, `au_group_parse_creditor_state`, SYS-04 **Resolve Territory Rep** | Replace placeholder SF User IDs; push SYS-04 JSON; live OwnerId needs KD-53 |
| **AC-5.4** | DNC suppression | partial | `au_group_evaluate_outreach_gates`, SYS-04→SYS-05 Execute | SF `Do_Not_Contact__c` on handoff |
| **AC-5.5** | Active engagement gate | partial | same + SYS-05 Set-only gates | SF opp/activity queries on SYS-04 |
| **AC-5.6** | T+1 outreach | scheduled | `smoke-e2e.yml` | Timing verified in prod ops |
| **AC-6.2** | Exposure on SF account | partial | `creditor_exposure_summary`, SYS-08 | Keith Excel column map; SF field sync |
| **AC-6.3** | Repeat-exposure threshold | partial | `au_group_check_repeat_exposure` RPC | Wire RPC in SYS-05 when creditor_id on handoff |
| **AC-6.4** | Low-value geography flag | no | — | Phase 2 |
| **NFR-1.1** | Processing latency / 8 AM | scheduled | `smoke-e2e.yml` cron (strict) | Not PR-blocking |
| **NFR-1.2** | Throughput (50+ filings/day) | no | — | Load test / prod metrics |
| **NFR-1.3** | System responsiveness | no | — | PACER favorites / alerts — prod |
| **NFR-2.1** | Extraction accuracy | yes | `ci-parser` pytest | Thresholds in PRD; manual AC-1.2 for Form 201 |
| **NFR-2.2** | Matching accuracy | no | — | ZoomInfo/SF integration |
| **NFR-2.3** | Data quality (dedup, nulls) | yes | `ci-parser` → `test_idempotency.py` | |
| **NFR-3.1** | Uptime / health | yes | `ci-parser`, `ci-playwright`, `smoke-e2e` | `/health`, `/health/ready`, Playwright |
| **NFR-3.2** | Error handling (retry, flag) | partial | `ci-parser` unit tests | Full retry paths in integration |
| **NFR-3.3** | Data integrity | yes | `ci-supabase` | migrate-reset + `verify-supabase-rls.sh` |
| **NFR-4.1** | Volume scalability | no | — | Architecture / load test |
| **NFR-4.2** | Processing scalability | no | — | Celery/queue — prod |
| **NFR-5.1** | Credential management | no | — | GitHub Environments + AWS Secrets Manager |
| **NFR-5.2** | Data privacy (DNC, PII) | partial | `ci-supabase` RLS verify | App logic in n8n/SF |
| **NFR-5.3** | Access control | partial | `ci-supabase` RLS | SF territory — product |
| **NFR-6.1** | Purchase approval UX | no | — | SYS-07 / Keith workflow |
| **NFR-6.2** | Salesforce UX | no | — | SF config |
| **NFR-6.3** | Alert clarity | no | — | n8n templates |
| **NFR-7.1** | No-code config (Keith) | yes | `scripts/ci/count-workflow-code-nodes.py`, Supabase config tables | 0 Code in `workflows/pulled/au-group-sys-*.json`; Keith edits tables + SF + Engage |
| **NFR-7.2** | Monitoring | scheduled | `smoke-e2e.yml` | Sentry Phase 5 (AU_GROUP-8.4) |
| **NFR-7.3** | Documentation | yes | `ci-export` | Dashboard package JSON valid |
| **NFR-8.1** | PACER cost control | no | — | Human-in-the-loop — product |
| **NFR-8.2** | API cost optimization | no | — | ZoomInfo cache — prod |
| **NFR-9.1** | CAN-SPAM | no | — | Engage/SalesLoft templates |
| **NFR-9.2** | Data retention | no | — | S3 lifecycle + SF policy |
| **NFR-5** | Security / deps | yes | `ci-security`, `ci-codeql`, `ci-trivy`, `ci-parser` pip-audit | vbsec + CodeQL + Trivy fs on every PR |
| **AU_GROUP-8.1** | Unit + integration tests | yes | `ci-parser`, `integration-tests` | PR: runs when secrets set; skip + warn if missing. Cron: strict. Optional `INTEGRATION_CI_STRICT=true` |
| **AU_GROUP-8.2** | CI/CD pipeline | yes | `ci.yml`, deploy workflows | Deploy runs security + smoke (strict) |
| **AU_GROUP-8.3** | CloudWatch dashboards | no | — | Infra outside repo |
| **AU_GROUP-8.4** | Sentry | no | — | Phase 5 |
| **AU_GROUP-8.5** | Security scan | yes | `ci-security`, `ci-codeql`, `ci-trivy` on every PR + parser deploy | vbsec + CodeQL + Trivy fs + pip/npm audit |

## Workflow file index

| Workflow | Path | Trigger |
|----------|------|---------|
| CI orchestrator | `.github/workflows/ci.yml` | PR, push to main/develop |
| Document parser | `.github/workflows/ci-parser.yml` | Called by ci.yml / deploy |
| Integration tests | `.github/workflows/integration-tests.yml` | PR (parser paths, strict), weekly cron |
| Supabase | `.github/workflows/ci-supabase.yml` | Called by ci.yml / deploy-supabase |
| n8n validate | — | No standalone workflow file currently present; validation coverage must be documented where implemented |
| Export package | `.github/workflows/ci-export.yml` | Called by `ci.yml`; validates `export/aaa-client-dashboard/` |
| Playwright E2E | `.github/workflows/ci-playwright.yml` | Called by ci.yml |
| vbsec security | `.github/workflows/ci-security.yml` | **Every** PR/push; all deploy workflows |
| CodeQL (parser) | `.github/workflows/ci-codeql.yml` | **Every** PR/push; parser deploy workflows |
| Trivy fs (parser deps) | `.github/workflows/ci-trivy.yml` | **Every** PR/push; parser deploy workflows |
| Deploy parser (Railway) | `.github/workflows/deploy-parser-railway.yml` | push main, dispatch → smoke strict |
| Deploy n8n | — | No standalone workflow file currently present; remove stale `deploy-n8n.yml` reference |
| Deploy Supabase | `.github/workflows/deploy-supabase.yml` | push main → security |
| Smoke E2E | `.github/workflows/smoke-e2e.yml` | deploy jobs, cron (strict), dispatch |
| Deploy EC2 | `.github/workflows/deploy-parser-ec2.yml` | dispatch only (Phase 4) |

## CI gate behavior (2026-05)

- **Security:** `security`, `codeql`, and `trivy` run on every PR/push (`ci.yml`), not path-filtered.
- **Integration:** runs when `services/document-parser/**` changes; skips with warning if staging secrets missing (unless `INTEGRATION_CI_STRICT=true` or weekly cron).
- **all-green:** path-matched jobs must `success`; security always required.
- **Smoke:** `strict=true` on deploy and daily cron — fails if `PARSER_*_URL` / n8n secrets missing.

## Related

- [Environments](./environments.md)
- [Rollback](./rollback.md)
- [Manual tests](./manual/README.md)
- [vbsec](./vbsec.md)
- [Security layers](./security-layers.md)
- [PR auto-fix (no merge)](./pr-autofix.md)
