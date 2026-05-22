-- Idempotent job acquisition for n8n orchestrators (SYS-02, SYS-03, SYS-04)

create or replace function public.au_group_acquire_processing_job (
  p_bankruptcy_id uuid,
  p_job_type public.au_group_job_type
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

  insert into public.processing_jobs (job_type, status, bankruptcy_id, started_at)
  values (p_job_type, 'running', p_bankruptcy_id, now())
  returning id into v_job_id;

  return jsonb_build_object(
    'acquired', true,
    'job_id', v_job_id,
    'reason', null
  );
end;
$$;

grant execute on function public.au_group_acquire_processing_job (uuid, public.au_group_job_type)
  to service_role;

-- One Supabase row per creditor for SF mapping (upsert from SYS-04)
create unique index if not exists idx_salesforce_accounts_creditor_id_unique
  on public.salesforce_accounts (creditor_id);
