-- KD-71: Drop FR-6 Phase 3 P1 tables not in MVP scope.
-- PRD FR-6.1: Keith may import Excel outside project.
-- PRD FR-6.2: Creditor exposure lives on Salesforce Account.
-- FR-6.3 repeat-exposure uses au_group_check_repeat_exposure → bankruptcy_creditors (unchanged).

drop function if exists public.au_group_recompute_exposure(uuid);

drop table if exists public.creditor_exposure_summary cascade;
drop table if exists public.historical_import_batches cascade;
