-- KD-70: Backfill bankruptcy_rss_events (SYS-01 RSS intake dedup store).
-- Version aligned with prod schema_migrations (MCP apply 20260528140329).

create table if not exists public.bankruptcy_rss_events (
  id uuid primary key default gen_random_uuid(),
  unique_key text not null,
  case_number text not null,
  court_id text not null,
  rss_guid text,
  event_number text,
  event_type text,
  raw_payload jsonb,
  created_at timestamptz not null default now(),
  bankruptcy_id uuid references public.bankruptcies (id),
  processed boolean default false,
  qualified boolean default false
);

create unique index if not exists bankruptcy_rss_events_unique_key_key
  on public.bankruptcy_rss_events (unique_key);

create unique index if not exists idx_rss_event_dedupe
  on public.bankruptcy_rss_events (case_number, court_id, event_number);

create index if not exists idx_rss_events_bankruptcy_id
  on public.bankruptcy_rss_events (bankruptcy_id);

create index if not exists idx_rss_events_unprocessed
  on public.bankruptcy_rss_events (created_at)
  where processed is not true;

alter table public.bankruptcy_rss_events enable row level security;

drop policy if exists bankruptcy_rss_events_deny_public on public.bankruptcy_rss_events;
create policy bankruptcy_rss_events_deny_public
  on public.bankruptcy_rss_events
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
