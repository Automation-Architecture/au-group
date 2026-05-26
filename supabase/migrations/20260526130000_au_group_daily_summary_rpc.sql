-- Wave 5: Daily summary metrics for SYS-09 (Keith 8AM report)

create or replace function public.au_group_daily_pipeline_summary(p_since timestamptz default now() - interval '24 hours')
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_result jsonb;
begin
  select jsonb_build_object(
    'since', p_since,
    'new_bankruptcies', (select count(*) from public.bankruptcies where created_at >= p_since),
    'new_creditors', (select count(*) from public.creditors where created_at >= p_since),
    'zoom_contacts_added', (select count(*) from public.zoom_info_contacts where created_at >= p_since),
    'salesforce_accounts_synced', (select count(*) from public.salesforce_accounts where last_sync_at >= p_since),
    'pacer_poll_completed', (
      select count(*) from public.processing_jobs
      where job_type = 'pacer_poll' and status = 'completed' and completed_at >= p_since
    ),
    'pacer_poll_failed', (
      select count(*) from public.processing_jobs
      where job_type = 'pacer_poll' and status = 'failed' and completed_at >= p_since
    ),
    'manual_review_pending', (select count(*) from public.manual_review_queue),
    'schedule_f_monitoring', (
      select count(*) from public.schedule_f_queue where status = 'monitoring'
    ),
    'schedule_f_pending_approval', (
      select count(*) from public.schedule_f_queue where status = 'pending_approval'
    ),
    'outreach_ready_cases', (
      select count(*) from public.bankruptcy_case_status where outreach_ready = true
    ),
    'pipeline_executions_failed', (
      select count(*) from public.pipeline_executions
      where status = 'failed' and created_at >= p_since
    )
  )
  into v_result;

  return v_result;
end;
$$;

comment on function public.au_group_daily_pipeline_summary is
  'SYS-09 Daily Summary: 24h pipeline metrics for Keith';

grant execute on function public.au_group_daily_pipeline_summary (timestamptz) to service_role;
