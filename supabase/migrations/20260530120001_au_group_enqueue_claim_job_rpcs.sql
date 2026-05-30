-- WP-00: enqueue + claim RPCs for code-native producer/consumer queue (KD-57)
-- NOTE: 20260530120000 was registered by the MCP apply_migration tool but its SQL
-- never ran (it referenced a non-existent 'pending' enum value — the live DB uses
-- 'queued' in the processing_job_status type).  This is the corrected migration.
--
-- The existing au_group_acquire_processing_job (inserts 'running' rows directly)
-- is untouched — n8n continues using it during parallel-run.

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
      -- Concurrent enqueue hit the queued partial index, or a running-singleton
      -- index blocked us (n8n acquired a running job between the pre-check and INSERT).
      return jsonb_build_object('enqueued', false);
  end;
end;
$$;

grant execute on function public.au_group_enqueue_job(uuid, public.au_group_job_type)
  to service_role;

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
