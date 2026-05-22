-- SYS-02 v2: per-document parse results (aggregation barrier) + race-safe job acquire

-- One running document_intelligence job per bankruptcy
create unique index if not exists idx_processing_jobs_one_running_doc_intel
  on public.processing_jobs (bankruptcy_id)
  where status = 'running' and job_type = 'document_intelligence';

-- One running salesforce_push job per bankruptcy (SYS-04 parity)
create unique index if not exists idx_processing_jobs_one_running_salesforce_push
  on public.processing_jobs (bankruptcy_id)
  where status = 'running' and job_type = 'salesforce_push';

create table if not exists public.document_parse_results (
  id uuid primary key default gen_random_uuid(),
  processing_job_id uuid not null references public.processing_jobs (id) on delete cascade,
  bankruptcy_id uuid not null references public.bankruptcies (id) on delete cascade,
  doc_index integer not null,
  doc_key text not null,
  s3_key text,
  document_url text,
  document_id text,
  parser_status text not null,
  manual_review_required boolean not null default false,
  parser_result jsonb,
  parse_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (processing_job_id, doc_index)
);

create index if not exists idx_document_parse_results_job
  on public.document_parse_results (processing_job_id);

create index if not exists idx_document_parse_results_bankruptcy
  on public.document_parse_results (bankruptcy_id);

alter table public.document_parse_results enable row level security;

create policy document_parse_results_deny_public
  on public.document_parse_results
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

-- Race-safe acquire: INSERT first; on partial unique violation return existing running job
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

grant execute on function public.au_group_acquire_processing_job (uuid, public.au_group_job_type)
  to service_role;
