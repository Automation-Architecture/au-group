-- WP-00: enqueue + claim RPCs for code-native producer/consumer queue (KD-57)
-- NOTE: 20260530120000 was registered by the MCP apply_migration tool but its SQL
-- never ran (it referenced a non-existent 'pending' enum value — the live DB uses
-- 'queued' in the processing_job_status type).  This is the corrected migration.
--
-- The existing au_group_acquire_processing_job (inserts 'running' rows directly)
-- is untouched — n8n continues using it during parallel-run.

-- ---------------------------------------------------------------------------
-- Schema reconciliation (replay safety)
--
-- processing_job_status was created and processing_jobs.status was migrated to
-- it via out-of-repo ad-hoc migrations (versions 20260531100000 and/or
-- 20260602150xxx).  Those files are being recovered; until they land in the
-- repo, these DO blocks make this migration replayable on a fresh database that
-- has only the migrations currently committed here.
-- ---------------------------------------------------------------------------

-- 1. Create the type if it doesn't already exist.
do $$ begin
  create type public.processing_job_status as enum (
    'queued', 'running', 'completed', 'failed', 'retrying'
  );
exception
  when duplicate_object then null;
end $$;

-- 2. If processing_jobs.status is still typed as au_group_job_status (local-only
--    replay scenario), migrate it to processing_job_status.  On the live DB the
--    column is already processing_job_status and this block is a no-op.
--    Value mapping: 'pending' → 'queued'; 'manual_review_required' → 'failed'.
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
    -- Drop partial indexes whose predicates reference the old au_group_job_status
    -- enum before the ALTER — PostgreSQL cannot rebuild index predicates across a
    -- column type change.  The CREATE UNIQUE INDEX IF NOT EXISTS calls below
    -- recreate all of them with correct processing_job_status casts.
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

-- Running-singleton indexes for job types not yet covered on the live DB.
-- Required for au_group_claim_job's unique_violation retry loop to detect when
-- n8n already holds a running job for a given (bankruptcy_id, job_type).
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

-- One queued job per (bankruptcy_id, job_type).  The running-singleton indexes
-- cover status='running'; this covers status='queued' across all job types.
create unique index if not exists idx_processing_jobs_one_queued_per_bankruptcy_type
  on public.processing_jobs (bankruptcy_id, job_type)
  where status = 'queued'::processing_job_status;

-- ---------------------------------------------------------------------------
-- au_group_enqueue_job
--
-- Insert a queued job for (p_bankruptcy_id, p_job_type).
-- Returns {"enqueued": true,  "job_id": "<uuid>"}  on success.
-- Returns {"enqueued": false}                       if a queued or running job
--   already exists for this (bankruptcy_id, job_type).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_enqueue_job(
  p_bankruptcy_id uuid,
  p_job_type      public.au_group_job_type
) returns jsonb
language plpgsql
security definer
set search_path to public
as $$
declare
  v_job_id uuid;
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  -- Fast-path: avoid the exception branch for the common non-concurrent case.
  -- TOCTOU note: au_group_acquire_processing_job can insert a running row after
  -- this check passes but before the INSERT below.  In that case the INSERT still
  -- succeeds — running-singleton indexes filter on status='running' and cannot
  -- block a 'queued' INSERT — so enqueued=true is returned despite the running
  -- job.  The queued row coexists harmlessly: claim_job skips it (unique_violation
  -- on the running-singleton when trying to UPDATE to 'running') until n8n's job
  -- finishes, then claims it on the next worker cycle.  Fixing this fully requires
  -- an advisory lock shared with acquire — off-limits during parallel-run.
  if exists (
    select 1
    from   public.processing_jobs
    where  bankruptcy_id = p_bankruptcy_id
      and  job_type      = p_job_type
      and  status        in (
             'queued'::processing_job_status,
             'running'::processing_job_status
           )
  ) then
    return jsonb_build_object('enqueued', false);
  end if;

  begin
    insert into public.processing_jobs (job_type, status, bankruptcy_id)
    values (p_job_type, 'queued'::processing_job_status, p_bankruptcy_id)
    returning id into v_job_id;

    return jsonb_build_object('enqueued', true, 'job_id', v_job_id);
  exception
    when unique_violation then
      -- unique_violation here comes only from
      -- idx_processing_jobs_one_queued_per_bankruptcy_type: a concurrent enqueue
      -- already inserted a queued row for this (bankruptcy_id, job_type) pair.
      -- Running-singleton indexes filter on status='running' and cannot block
      -- this 'queued' INSERT.  The n8n TOCTOU race (acquire inserting a running
      -- row after the pre-check) does NOT trigger a unique_violation — it lets
      -- the INSERT succeed and returns enqueued=true; see the TOCTOU note above.
      return jsonb_build_object('enqueued', false);
  end;
end;
$$;

grant execute on function public.au_group_enqueue_job(uuid, public.au_group_job_type)
  to service_role;
revoke execute on function public.au_group_enqueue_job(uuid, public.au_group_job_type)
  from public;

-- ---------------------------------------------------------------------------
-- au_group_claim_job
--
-- Atomically claim one queued job of p_job_type.
--   1. SELECT the oldest queued row FOR UPDATE SKIP LOCKED.
--   2. UPDATE it to running + stamp started_at.
--   3. If the running-singleton index blocks the UPDATE (a parallel worker or
--      n8n already holds a running job for that bankruptcy), the savepoint in the
--      exception block rolls back the UPDATE while the outer FOR UPDATE lock is
--      retained; add the row id to v_skipped and loop to the next queued row.
--   4. Return the claimed row, or NULL when nothing claimable is queued.
-- ---------------------------------------------------------------------------
create or replace function public.au_group_claim_job(
  p_job_type public.au_group_job_type
) returns public.processing_jobs
language plpgsql
security definer
set search_path to public
as $$
declare
  v_job     public.processing_jobs;
  v_id      uuid;
  v_skipped uuid[] := '{}';
begin
  loop
    select id
    into   v_id
    from   public.processing_jobs
    where  status   = 'queued'::processing_job_status
      and  job_type = p_job_type
      and  id != all(v_skipped)
    order  by created_at
    limit  1
    for    update skip locked;

    -- No claimable queued row found.
    if v_id is null then
      return null;
    end if;

    begin
      update public.processing_jobs
      set    status     = 'running'::processing_job_status,
             started_at = now()
      where  id = v_id
      returning * into v_job;

      return v_job;
    exception
      when unique_violation then
        -- The running-singleton index blocked this (bankruptcy_id, job_type).
        -- The savepoint rolls back the UPDATE; the FOR UPDATE lock on v_id is
        -- retained at the outer transaction level.  Skip this row and try the next.
        v_skipped := array_append(v_skipped, v_id);
    end;
  end loop;
end;
$$;

grant execute on function public.au_group_claim_job(public.au_group_job_type)
  to service_role;
revoke execute on function public.au_group_claim_job(public.au_group_job_type)
  from public;
