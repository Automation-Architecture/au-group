-- Fail processing_jobs stuck in queued/running beyond 24h (SYS-01 pacer_poll hygiene)

create or replace function public.au_group_fail_stale_processing_jobs (
  p_max_age interval default interval '24 hours'
) returns integer
language plpgsql
security invoker
set search_path to public
as $$
declare
  updated integer;
begin
  update public.processing_jobs
  set
    status = 'failed',
    error_message = coalesce(error_message, 'stale job auto-failed'),
    completed_at = now()
  where status in ('queued', 'running')
    and created_at < now() - p_max_age
    and completed_at is null;

  get diagnostics updated = row_count;
  return updated;
end;
$$;

grant execute on function public.au_group_fail_stale_processing_jobs (interval) to service_role;
