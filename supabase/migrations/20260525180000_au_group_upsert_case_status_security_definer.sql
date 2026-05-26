-- SYS-04 Update Case Status: run as definer so service_role/anon RPC callers bypass RLS on bankruptcy_case_status

create or replace function public.au_group_upsert_case_status (
  p_bankruptcy_id uuid,
  p_has_creditor_matrix boolean default null,
  p_has_schedule_f boolean default null,
  p_has_asset_schedule boolean default null,
  p_enrichment_completed boolean default null,
  p_outreach_ready boolean default null,
  p_lifecycle_stage text default null
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  insert into public.bankruptcy_case_status (
    bankruptcy_id,
    has_creditor_matrix,
    has_schedule_f,
    has_asset_schedule,
    enrichment_completed,
    outreach_ready,
    lifecycle_stage,
    updated_at
  )
  values (
    p_bankruptcy_id,
    coalesce(p_has_creditor_matrix, false),
    coalesce(p_has_schedule_f, false),
    coalesce(p_has_asset_schedule, false),
    coalesce(p_enrichment_completed, false),
    coalesce(p_outreach_ready, false),
    coalesce(p_lifecycle_stage, 'new'),
    now()
  )
  on conflict (bankruptcy_id) do update
  set
    has_creditor_matrix = coalesce(p_has_creditor_matrix, bankruptcy_case_status.has_creditor_matrix),
    has_schedule_f = coalesce(p_has_schedule_f, bankruptcy_case_status.has_schedule_f),
    has_asset_schedule = coalesce(p_has_asset_schedule, bankruptcy_case_status.has_asset_schedule),
    enrichment_completed = coalesce(
      p_enrichment_completed,
      bankruptcy_case_status.enrichment_completed
    ),
    outreach_ready = coalesce(p_outreach_ready, bankruptcy_case_status.outreach_ready),
    lifecycle_stage = coalesce(p_lifecycle_stage, bankruptcy_case_status.lifecycle_stage),
    updated_at = now();

  return p_bankruptcy_id;
end;
$$;

comment on function public.au_group_upsert_case_status is
  'Upsert bankruptcy_case_status lifecycle flags (security definer for n8n service_role RPC)';

grant execute on function public.au_group_upsert_case_status (
  uuid, boolean, boolean, boolean, boolean, boolean, text
) to service_role;
