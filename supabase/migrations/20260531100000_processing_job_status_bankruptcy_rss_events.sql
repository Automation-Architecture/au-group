-- Recovery migration: applied to live DB out-of-repo on 2026-05-31.
-- Captures: processing_job_status type, processing_jobs column migration + extra columns,
-- bankruptcy_chapter type, schedule_f_status type, missing columns on bankruptcies and
-- creditors, bankruptcy_rss_events table, update_updated_at_column trigger function.
--
-- All DDL is idempotent — safe to replay on fresh databases.

-- ---------------------------------------------------------------------------
-- 1. New enum types
-- ---------------------------------------------------------------------------

-- processing_job_status replaces au_group_job_status for processing_jobs.status.
-- Values differ: 'queued' (not 'pending'), and adds 'retrying'.
do $$ begin
  create type public.processing_job_status as enum (
    'queued', 'running', 'completed', 'failed', 'retrying'
  );
exception
  when duplicate_object then null;
end $$;

-- bankruptcy_chapter: additional chapter enum for the code-native pipeline.
-- Note: bankruptcies.chapter_type column remains au_group_chapter_type on the base schema;
-- this enum is an additional type used by new pipeline code, not a column replacement.
do $$ begin
  create type public.bankruptcy_chapter as enum ('7', '11', '13', '15');
exception
  when duplicate_object then null;
end $$;

-- schedule_f_status — lighter enum for code-native schedule-F pipeline.
do $$ begin
  create type public.schedule_f_status as enum (
    'pending', 'monitoring', 'detected', 'downloaded', 'parsed', 'failed'
  );
exception
  when duplicate_object then null;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Migrate processing_jobs.status from au_group_job_status → processing_job_status
--    No-op on live DB (already migrated). Guards replay on a fresh database.
-- ---------------------------------------------------------------------------
do $$
declare
  v_col_type text;
begin
  select udt_name into v_col_type
  from information_schema.columns
  where table_schema = 'public'
    and table_name   = 'processing_jobs'
    and column_name  = 'status';

  if v_col_type = 'au_group_job_status' then
    -- Drop partial indexes whose WHERE predicates reference the au_group_job_status
    -- enum before the ALTER -- PostgreSQL cannot rebuild index predicates across a
    -- column type change.  CREATE UNIQUE INDEX IF NOT EXISTS after this block
    -- recreates them with correct processing_job_status casts.
    drop index if exists idx_processing_jobs_one_running_pacer_poll;
    drop index if exists idx_processing_jobs_one_running_document_parse;
    drop index if exists idx_processing_jobs_one_running_zoom_info_enrich;
    drop index if exists idx_processing_jobs_one_running_doc_intel;
    drop index if exists idx_processing_jobs_one_running_salesforce_push;

    alter table public.processing_jobs
      alter column status type public.processing_job_status
      using case status::text
        when 'pending'                then 'queued'
        when 'manual_review_required' then 'failed'
        else status::text
      end::public.processing_job_status;
  end if;
end $$;

-- Recreate the running-singleton indexes with correct processing_job_status casts.
-- These are no-ops on the live DB (column was already migrated before this file ran).
-- On a fresh replay they are dropped (above) and recreated here.
create unique index if not exists idx_processing_jobs_one_running_pacer_poll
  on public.processing_jobs (bankruptcy_id)
  where status = 'running'::processing_job_status
    and job_type = 'pacer_poll'::au_group_job_type;

create unique index if not exists idx_processing_jobs_one_running_document_parse
  on public.processing_jobs (bankruptcy_id)
  where status = 'running'::processing_job_status
    and job_type = 'document_parse'::au_group_job_type;

create unique index if not exists idx_processing_jobs_one_running_zoom_info_enrich
  on public.processing_jobs (bankruptcy_id)
  where status = 'running'::processing_job_status
    and job_type = 'zoom_info_enrich'::au_group_job_type;

create unique index if not exists idx_processing_jobs_one_running_doc_intel
  on public.processing_jobs (bankruptcy_id)
  where status = 'running'::processing_job_status
    and job_type = 'document_intelligence'::au_group_job_type;

create unique index if not exists idx_processing_jobs_one_running_salesforce_push
  on public.processing_jobs (bankruptcy_id)
  where status = 'running'::processing_job_status
    and job_type = 'salesforce_push'::au_group_job_type;

-- ---------------------------------------------------------------------------
-- 3. Extra columns on processing_jobs (not in local original migration)
-- ---------------------------------------------------------------------------
alter table public.processing_jobs
  add column if not exists worker_name  text,
  add column if not exists job_payload  jsonb;

-- ---------------------------------------------------------------------------
-- 4. Missing columns on bankruptcies (added ad-hoc before this version)
-- ---------------------------------------------------------------------------
alter table public.bankruptcies
  add column if not exists is_business        boolean default true,
  add column if not exists monitoring_enabled boolean default true,
  add column if not exists source_type        text default 'rss',
  add column if not exists rss_guid           text,
  add column if not exists court_id           text,
  add column if not exists lead_score         integer default 0,
  add column if not exists lead_priority      text,
  add column if not exists sales_ready        boolean default false;

-- ---------------------------------------------------------------------------
-- 5. Missing columns on creditors (zoominfo enrichment fields + tier)
-- ---------------------------------------------------------------------------
alter table public.creditors
  add column if not exists dedup_audit               jsonb,
  add column if not exists zoominfo_match_confidence numeric,
  add column if not exists zoominfo_match_status     text,
  add column if not exists zoominfo_firmographics    jsonb,
  add column if not exists zoominfo_enriched_at      timestamptz,
  add column if not exists company_tier              smallint,
  add column if not exists company_tier_assigned_at  timestamptz;

-- ---------------------------------------------------------------------------
-- 6. bankruptcy_rss_events table
-- ---------------------------------------------------------------------------
create table if not exists public.bankruptcy_rss_events (
  id           uuid primary key default gen_random_uuid(),
  unique_key   text not null unique,
  case_number  text not null,
  court_id     text not null,
  rss_guid     text,
  event_number text,
  event_type   text,
  raw_payload  jsonb,
  created_at   timestamptz not null default now(),
  bankruptcy_id uuid references public.bankruptcies (id),
  processed    boolean default false,
  qualified    boolean default false
);

alter table public.bankruptcy_rss_events enable row level security;

create unique index if not exists idx_rss_event_dedupe
  on public.bankruptcy_rss_events (case_number, court_id, event_number);

create index if not exists idx_rss_events_bankruptcy_id
  on public.bankruptcy_rss_events (bankruptcy_id);

create index if not exists idx_rss_events_unprocessed
  on public.bankruptcy_rss_events (created_at)
  where processed is not true;

-- ---------------------------------------------------------------------------
-- 7. update_updated_at_column trigger function + triggers on existing tables
-- ---------------------------------------------------------------------------
create or replace function public.update_updated_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Applied to bankruptcies and creditors (confirmed via pg_trigger on live).
-- Use DROP/CREATE for PG15 compatibility (CREATE OR REPLACE TRIGGER is PG16+).
-- Also drop the old *_set_updated_at triggers from the base migration (20260215180000)
-- so only one BEFORE UPDATE trigger fires per table.
drop trigger if exists bankruptcies_set_updated_at on public.bankruptcies;
drop trigger if exists update_bankruptcies_updated_at on public.bankruptcies;
create trigger update_bankruptcies_updated_at
  before update on public.bankruptcies
  for each row execute function public.update_updated_at_column();

drop trigger if exists creditors_set_updated_at on public.creditors;
drop trigger if exists update_creditors_updated_at on public.creditors;
create trigger update_creditors_updated_at
  before update on public.creditors
  for each row execute function public.update_updated_at_column();
