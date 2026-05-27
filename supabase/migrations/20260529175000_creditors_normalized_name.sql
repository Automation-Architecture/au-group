-- ZoomInfo/canonical name column; referenced by SYS-09 daily sheet (20260529180000).

alter table public.creditors
  add column if not exists normalized_name text;

comment on column public.creditors.normalized_name is
  'Canonical company name after enrichment (ZoomInfo); filing name stays in name/original_name.';
