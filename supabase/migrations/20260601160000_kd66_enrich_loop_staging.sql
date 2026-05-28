-- KD-66: Replace SYS-03 workflow staticData aggregation with SQL staging.

create table if not exists public.au_group_enrich_loop_staging (
  job_id uuid not null,
  creditor_id uuid not null,
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (job_id, creditor_id)
);

create index if not exists idx_au_group_enrich_loop_staging_job
  on public.au_group_enrich_loop_staging (job_id);

alter table public.au_group_enrich_loop_staging enable row level security;

drop policy if exists au_group_enrich_loop_staging_deny_public on public.au_group_enrich_loop_staging;
create policy au_group_enrich_loop_staging_deny_public
  on public.au_group_enrich_loop_staging
  for all
  using (false);

create or replace function public.au_group_enrich_loop_push(
  p_job_id uuid,
  p_creditor_id uuid,
  p_result jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_job_id is null or p_creditor_id is null then
    raise exception 'job_id and creditor_id required' using errcode = 'P0001';
  end if;

  insert into public.au_group_enrich_loop_staging (job_id, creditor_id, result, updated_at)
  values (p_job_id, p_creditor_id, coalesce(p_result, '{}'::jsonb), now())
  on conflict (job_id, creditor_id) do update
    set result = public.au_group_enrich_loop_staging.result || excluded.result,
        updated_at = now();

  return jsonb_build_object('ok', true, 'job_id', p_job_id, 'creditor_id', p_creditor_id);
end;
$$;

create or replace function public.au_group_enrich_loop_finalize(
  p_job_id uuid,
  p_bankruptcy_id uuid default null,
  p_pipeline_execution_id uuid default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_all jsonb;
  v_matched text[] := array['matched', 'cached', 'dry_run'];
begin
  select coalesce(jsonb_agg(s.result order by s.creditor_id), '[]'::jsonb)
  into v_all
  from public.au_group_enrich_loop_staging s
  where s.job_id = p_job_id;

  delete from public.au_group_enrich_loop_staging where job_id = p_job_id;

  return jsonb_build_object(
    'bankruptcy_id', p_bankruptcy_id,
    'enrich_job_id', p_job_id,
    'pipeline_execution_id', p_pipeline_execution_id,
    'enrichment_summary', jsonb_build_object(
      'creditors_processed', jsonb_array_length(v_all),
      'zoominfo_company_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where coalesce(e->>'zoominfo_company_id', '') <> ''
           or (e->>'zoominfo_status') = any (v_matched)
      ),
      'zoominfo_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'matched'
      ),
      'cache_hits', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where (e->>'cache_hit')::boolean is true
      ),
      'no_match', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'no_match'
      ),
      'ambiguous', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'ambiguous'
      ),
      'no_contact_found', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' in ('no_contact_found', 'no_match')
          and coalesce((e->>'contacts_saved')::integer, 0) = 0
      ),
      'rate_limited', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'rate_limited'
      ),
      'contacts_saved', (
        select coalesce(sum((e->>'contacts_saved')::integer), 0)::integer
        from jsonb_array_elements(v_all) e
      ),
      'skipped_individual', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'skipped_individual'
      ),
      'errors', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'error'
      )
    )
  );
end;
$$;

grant execute on function public.au_group_enrich_loop_push(uuid, uuid, jsonb) to service_role;
grant execute on function public.au_group_enrich_loop_finalize(uuid, uuid, uuid) to service_role;
