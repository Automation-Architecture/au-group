-- Canonical company name from ZoomInfo enrichment (SYS-09 company_name column).
alter table public.creditors
  add column if not exists normalized_name text;

comment on column public.creditors.normalized_name is
  'Canonical company name from enrichment; daily report uses this for company_name when set.';
