-- WP-04: creditors.company_tier + salesforce_accounts.sf_recency_status (KD-62)
--
-- creditors.company_tier
--   On the live DB this column already exists as smallint (int2) via the
--   out-of-repo migration 20260531100000 (recovered in PR #40).  The spec
--   (section 5.2) originally proposed VARCHAR(20) with string values
--   ('Enterprise', 'Mid-Market', 'SMB'), but the live implementation chose
--   smallint 1–3 (1=Enterprise, 2=Mid-Market, 3=SMB) for storage efficiency.
--   The ADD COLUMN IF NOT EXISTS below is a no-op on the live DB and creates
--   the column on a fresh replay.
--
-- salesforce_accounts.sf_recency_status
--   New column — does not exist on the live DB.  Persisted by the SF-push
--   stage (pipeline/salesforce.py) so the daily report reads the FR-5.5
--   recency flag without a live Salesforce call at report time.

alter table public.creditors
  add column if not exists company_tier smallint
    check (company_tier >= 1 and company_tier <= 3);

comment on column public.creditors.company_tier is
  'FR-4.2 ZoomInfo tier: 1=Enterprise, 2=Mid-Market, 3=SMB. NULL until SYS-03 enrichment runs.';

alter table public.salesforce_accounts
  add column if not exists sf_recency_status varchar(60);

comment on column public.salesforce_accounts.sf_recency_status is
  'FR-5.5 Salesforce-recency flag: "New Salesforce account" or "Existing activity in Salesforce". Persisted at SF-push time so the daily report does not require a live SF call.';
