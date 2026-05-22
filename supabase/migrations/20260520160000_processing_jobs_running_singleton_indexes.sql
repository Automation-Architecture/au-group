-- One running job per bankruptcy for all au_group_job_type values (acquire RPC idempotency).
-- document_intelligence + salesforce_push: 20260520140000_sys02_document_parse_results.sql

create unique index if not exists idx_processing_jobs_one_running_pacer_poll
  on public.processing_jobs (bankruptcy_id)
  where status = 'running' and job_type = 'pacer_poll';

create unique index if not exists idx_processing_jobs_one_running_document_parse
  on public.processing_jobs (bankruptcy_id)
  where status = 'running' and job_type = 'document_parse';

create unique index if not exists idx_processing_jobs_one_running_zoom_info_enrich
  on public.processing_jobs (bankruptcy_id)
  where status = 'running' and job_type = 'zoom_info_enrich';

-- Pre-check before INSERT; unique_violation handler still covers races when indexes apply
create or replace function public.au_group_acquire_processing_job (
  p_bankruptcy_id uuid,
  p_job_type public.au_group_job_type,
  p_stale_interval interval default interval '24 hours'
) returns jsonb
language plpgsql
security definer
set search_path to public
as $$
declare
  v_existing uuid;
  v_job_id uuid;
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  update public.processing_jobs
  set
    status = 'failed',
    error_message = coalesce(error_message, 'stale job auto-failed before acquire'),
    completed_at = now()
  where bankruptcy_id = p_bankruptcy_id
    and job_type = p_job_type
    and status = 'running'
    and coalesce(started_at, created_at) < now() - p_stale_interval;

  select id
  into v_existing
  from public.processing_jobs
  where bankruptcy_id = p_bankruptcy_id
    and job_type = p_job_type
    and status = 'running'
  order by created_at desc
  limit 1;

  if v_existing is not null then
    return jsonb_build_object(
      'acquired', false,
      'job_id', v_existing,
      'reason', 'job_already_running'
    );
  end if;

  begin
    insert into public.processing_jobs (job_type, status, bankruptcy_id, started_at)
    values (p_job_type, 'running', p_bankruptcy_id, now())
    returning id into v_job_id;

    return jsonb_build_object(
      'acquired', true,
      'job_id', v_job_id,
      'reason', null
    );
  exception
    when unique_violation then
      select id
      into v_existing
      from public.processing_jobs
      where bankruptcy_id = p_bankruptcy_id
        and job_type = p_job_type
        and status = 'running'
      order by created_at desc
      limit 1;

      return jsonb_build_object(
        'acquired', false,
        'job_id', v_existing,
        'reason', 'job_already_running'
      );
  end;
end;
$$;

grant execute on function public.au_group_acquire_processing_job (
  uuid,
  public.au_group_job_type,
  interval
) to service_role;
