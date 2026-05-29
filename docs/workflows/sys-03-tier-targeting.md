# SYS-03 — KD-21 tier-based targeting (FR-4.2)

**Workflow:** `j26cimQ4S7kN67IP` — SYS-03 Creditor Enrichment  
**Depends on:** KD-20 company lookup (firmographics on item JSON)

## What changed

Tier thresholds and contact-title mappings live in Supabase (`au_group_company_tiers`, `au_group_tier_contact_titles`). SYS-03 calls RPCs instead of hardcoded `TIER_TITLES` in the Code node.

| RPC | Purpose |
|-----|---------|
| `au_group_classify_company_tier(revenue, employees)` | Returns tier 1–3 per PRD / EC-2.3 |
| `au_group_list_tier_contact_titles(tier)` | Ordered titles for ZoomInfo contact filter |
| `au_group_set_creditor_company_tier(creditor_id, tier, bankruptcy_id?)` | Persists `creditors.company_tier`; optional `bankruptcy_id` scopes update to case-linked creditors |
| `au_group_get_tier_targeting_config()` | Ops snapshot (all tiers + titles) |

## Deploy

```bash
# Apply migration first (remote or local)
supabase db push   # or CI migrate-reset

# Patch live workflow (requires N8N_API_KEY)
N8N_API_URL=https://automationarchitecture.app.n8n.cloud \
N8N_API_KEY=... \
  node scripts/n8n/patch-sys03-tier-rules.mjs --push
```

**Helpers source:** [scripts/n8n/lib/sys03-tier-rpc-helpers.js](../../scripts/n8n/lib/sys03-tier-rpc-helpers.js) (injected by `patch-sys03-tier-rules.mjs`). Uses `au_group_get_tier_targeting_config` once per creditor (no per-tier RPC fan-out). Passes `$json.bankruptcy_id` when persisting tier. Fails closed on RPC errors (no default to SMB).

## n8n item fields (after tier step)

| Field | Type | Notes |
|-------|------|-------|
| `assigned_tier` | 1 \| 2 \| 3 | Primary tier from firmographics |
| `tier_name` | string | `enterprise`, `mid_market`, `smb` |
| `target_titles` | string[] | Titles for first contact search |
| `tier_titles_map` | object | `{ "1": [...], "2": [...], "3": [...] }` for KD-23 fallback |

Contact search should filter on `target_titles` first; on zero results, iterate `tier_titles_map` from `assigned_tier + 1` through `3` (KD-23).

## Editing rules (NFR-7.1)

No code deploy required:

1. **Thresholds** — Supabase Table Editor → `au_group_company_tiers` (`min_revenue`, `min_employees`, `label`).
2. **Titles** — `au_group_tier_contact_titles` (`title_pattern`, `sort_order`, `active`).
3. Changes are audited in `au_group_config_audit`.

Re-run enrichment on a test creditor to verify new titles are used.

## Verification

```bash
# Local (after supabase db reset)
psql "$DB_URL" -f scripts/supabase/smoke_tier_classification.sql
```

Golden cases are embedded in `scripts/supabase/smoke_tier_classification.sql` (20 cases; CI enforces ≥95% accuracy per FR-4.2 / NFR-2.2).

## Migration

[supabase/migrations/20260602170000_au_group_tier_targeting_rules.sql](../../supabase/migrations/20260602170000_au_group_tier_targeting_rules.sql)
