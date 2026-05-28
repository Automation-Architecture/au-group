# Client Ops Runbook — AU Group (Keith)

**Audience:** Keith / AU Group operations (no GitHub, no n8n editor, no Railway).  
**AAA:** Deploys workflows, SQL migrations, and parser; wires credentials (KD-53).

## Keith may change (Supabase Table Editor)

| Table / config | What it controls |
|----------------|------------------|
| `au_group_target_states` | Which states qualify for pipeline (KD-14) |
| `au_group_company_tiers` | Revenue/employee tier thresholds (KD-22) |
| `au_group_tier_contact_titles` | Job titles per tier for ZoomInfo contact search |
| `au_group_suppression_lenders` | Lender name patterns excluded from enrichment |
| `au_group_suppression_keywords` | Keyword patterns excluded from enrichment |
| `au_group_runtime_config` | `repeat_exposure_*`, `creditor_name_min_length`, `creditor_line_number_max_digits`, `creditor_dedup_threshold` |
| `au_group_territory_assignments` | State → Salesforce User ID for routing |

## Keith may change (external UIs)

| System | What |
|--------|------|
| **PACER** | Favorites list (Schedule F approval queue — SYS-06/07) |
| **Salesforce** | Account fields, DNC, custom bankruptcy fields, territory ownership |
| **ZoomInfo Engage / SalesLoft** | Email cadence templates and copy |

## Keith must not touch

- GitHub repo, Railway, n8n workflow editor
- `processing_jobs`, `document_parse_results`, `au_group_enrich_loop_staging` (operational scratch)
- Workflow JSON in this repo

## AAA prerequisites (blocking production)

| Task | Owner | Ticket |
|------|-------|--------|
| Production ZoomInfo + Salesforce API credentials | Keith → AAA | KD-53 |
| Replace `005PLACEHOLDER*` in `au_group_territory_assignments` with real Salesforce User IDs | Keith | KD-60 |
| Seed `au_group_suppression_lenders` / `au_group_suppression_keywords` from discovery list | Keith | KD-60 |
| Salesforce custom fields: DNC, engagement flags, bankruptcy event | Keith SF admin | AC-5.4/5.5 |
| n8n: service_role on Supabase HTTP nodes; ZoomInfo cred on SYS-03 | AAA | — |

See [production-credentials-client-checklist.md](../project/production-credentials-client-checklist.md).

## UAT (no n8n editor)

1. Add a row to `au_group_suppression_keywords` → re-run enrich → creditor skipped at load.
2. Change a tier row in `au_group_company_tiers` → re-run enrich → contact titles reflect new tier.
3. Edit `creditor_dedup_threshold` in `au_group_runtime_config` → parse matrix → dedup behavior changes (parser reads config).

## Support

AAA: Automation Architecture — workflow/SQL/parser changes only via deploy, not Keith self-service.
