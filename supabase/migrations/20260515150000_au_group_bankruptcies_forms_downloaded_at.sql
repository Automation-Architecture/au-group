-- AU Group: track when Form 201 / Form 204 were stored in S3 (per jira-backlog AU_GROUP-2.3)
alter table public.bankruptcies
  add column if not exists forms_downloaded_at timestamptz;

create index if not exists idx_bankruptcies_forms_downloaded_at
  on public.bankruptcies (forms_downloaded_at);
