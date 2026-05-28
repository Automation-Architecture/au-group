# SYS-04 — Salesforce Push

**n8n workflow:** `AU Group - SYS-04 - Salesforce Push`  
**Cloud ID:** `YWmFi1GkJqJMB8bJ`  
**Upstream:** SYS-03 Creditor Enrichment (`j26cimQ4S7kN67IP`)  
**Downstream:** SYS-05 Outreach Trigger (`SWES563HTLR2t9Gv`)  
**Error workflow:** SYS-99 `vLIKLIOnhNRhNReU`

## PRD mapping

| PRD | Implementation |
|-----|----------------|
| FR-5.1 Account match/create | `au_group_list_company_creditors` → SF SOQL Name + `BillingState`; `Parse SF Search` disambiguates by state/street |
| FR-5.2 Bankruptcy event | `SF Create Bankruptcy Event` → `Bankruptcy_Event__c` |
| FR-5.3 Territory | `au_group_resolve_territory_rep` → `OwnerId` on create/update |
| FR-5.4–5.5 Gates | SF DNC + open opp + Task 90d → `suppress` / `active_engagement`; repeat exposure in SYS-05 RPC |
| FR-5.6 Outreach | `outreach_eligible` → `Execute SYS-05 Outreach` (T+1 schedule on SYS-05) |

## Handoff from SYS-03

Required fields on Execute Workflow input: `bankruptcy_id`, `case_number`, `debtor_name`, `dry_run` (optional).

Per-creditor loop uses RPC `au_group_list_company_creditors` (`creditor_id`, `creditor_name`, `normalized_name`, `creditor_address`, `creditor_state`, `claim_amount`).

## Ops prerequisites

- KD-53: Salesforce OAuth2 credential on all `SF *` HTTP nodes
- AU_GROUP-5.1: `Bankruptcy_Event__c`, Account custom fields (`Do_Not_Contact__c`, outreach fields)
- Replace `005PLACEHOLDER*` in `au_group_territory_assignments` (Keith / KD-60)
- Supabase migration `20260602120000_sys04_list_creditors_normalized_name.sql` applied

## Per-creditor loop (wiring)

```
Merge Loop + SF Map
  → Set Territory State → Valid Territory State?
       → RPC Resolve Territory Rep → Extract Territory Rep ─┐
       → Extract Territory Rep (Skip) ──────────────────────┴→ Combine Territory Output
  → Get Zoom Contacts → … → SF Account / Bankruptcy Event
  → SF Get Account DNC → … → Apply Outreach Gates
  → Is DNC?
       true  → Flag Suppressed → Record Loop Outcome
       false → Execute SYS-05 Outreach → Patch SF Recommendation? → …
  → Needs SF Recommendation?
       true  → Set Recommendation Fields → Record Loop Outcome
       false → Flag Suppressed → Record Loop Outcome
```

## Dry run

When `dry_run === true` on handoff: `Dry Run?` → stub SF id, skip live Account/Event writes, `outreach_eligible` false.
