-- SYS-02A: document intelligence tables and bankruptcy extensions

do $$ begin
  create type public.au_group_filing_type as enum (
    'FORM_201',
    'CREDITOR_MATRIX',
    'SCHEDULE',
    'SOFA',
    'UNKNOWN'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.au_group_parse_mode as enum ('structured', 'ocr');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.au_group_review_status as enum (
    'pending',
    'in_review',
    'resolved',
    'rejected'
  );
exception
  when duplicate_object then null;
end $$;

alter type public.au_group_job_status add value if not exists 'manual_review_required';

alter table public.bankruptcies
  add column if not exists city text,
  add column if not exists industry_code text,
  add column if not exists estimated_assets_range jsonb,
  add column if not exists estimated_liabilities_range jsonb,
  add column if not exists estimated_creditor_count_range jsonb,
  add column if not exists extraction_confidence_score numeric(5, 4),
  add column if not exists manual_review_required boolean not null default false;

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid references public.bankruptcies (id) on delete set null,
  s3_key text not null,
  content_sha256 text not null,
  page_count integer not null default 0,
  filing_type public.au_group_filing_type not null default 'UNKNOWN',
  parse_mode public.au_group_parse_mode not null default 'structured',
  ocr_used boolean not null default false,
  parser_version text not null,
  raw_extraction jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (content_sha256, parser_version)
);

drop trigger if exists documents_set_updated_at on public.documents;
create trigger documents_set_updated_at
  before update on public.documents
  for each row execute function public.set_updated_at();

create table if not exists public.form201_extractions (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid references public.bankruptcies (id) on delete cascade,
  document_id uuid references public.documents (id) on delete cascade,
  debtor_name text,
  city text,
  state text,
  court_district text,
  industry_code text,
  estimated_assets jsonb,
  estimated_liabilities jsonb,
  estimated_creditor_count jsonb,
  confidence_score numeric(5, 4),
  manual_review_required boolean not null default false,
  raw_extraction jsonb,
  parser_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.creditor_matrix_extractions (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid references public.bankruptcies (id) on delete cascade,
  document_id uuid references public.documents (id) on delete cascade,
  creditor_count integer not null default 0,
  confidence_score numeric(5, 4),
  manual_review_required boolean not null default false,
  parser_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.creditor_matrix_rows (
  id uuid primary key default gen_random_uuid(),
  extraction_id uuid not null references public.creditor_matrix_extractions (id) on delete cascade,
  creditor_name text not null,
  address text,
  claim_amount numeric(15, 2),
  entity_type text,
  created_at timestamptz not null default now()
);

create table if not exists public.manual_review_queue (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid references public.bankruptcies (id) on delete set null,
  document_id uuid references public.documents (id) on delete set null,
  review_reason text not null,
  status public.au_group_review_status not null default 'pending',
  assigned_to text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists manual_review_queue_set_updated_at on public.manual_review_queue;
create trigger manual_review_queue_set_updated_at
  before update on public.manual_review_queue
  for each row execute function public.set_updated_at();

create index if not exists idx_documents_bankruptcy_id on public.documents (bankruptcy_id);
create index if not exists idx_documents_filing_type on public.documents (filing_type);
create index if not exists idx_form201_extractions_bankruptcy_id on public.form201_extractions (bankruptcy_id);
create index if not exists idx_creditor_matrix_rows_extraction_id on public.creditor_matrix_rows (extraction_id);
create index if not exists idx_manual_review_queue_status on public.manual_review_queue (status);

alter table public.documents enable row level security;
alter table public.form201_extractions enable row level security;
alter table public.creditor_matrix_extractions enable row level security;
alter table public.creditor_matrix_rows enable row level security;
alter table public.manual_review_queue enable row level security;

create or replace function public.au_group_jsonb_midpoint_usd(range jsonb)
returns numeric
language sql
immutable
as $$
  select case
    when range is null then null
    when (range->>'min_usd') is not null and (range->>'max_usd') is not null then
      ((range->>'min_usd')::numeric + (range->>'max_usd')::numeric) / 2
    when (range->>'min_usd') is not null then (range->>'min_usd')::numeric
    when (range->>'max_usd') is not null then (range->>'max_usd')::numeric
    else null
  end;
$$;

create or replace function public.au_group_jsonb_midpoint_count(range jsonb)
returns integer
language sql
immutable
as $$
  select case
    when range is null then null
    when (range->>'min') is not null and (range->>'max') is not null then
      (((range->>'min')::integer + (range->>'max')::integer) / 2)
    when (range->>'min') is not null then (range->>'min')::integer
    when (range->>'max') is not null then (range->>'max')::integer
    else null
  end;
$$;

create or replace function public.au_group_upsert_bankruptcy_from_form201 (
  p_bankruptcy_id uuid,
  p_debtor_name text default null,
  p_city text default null,
  p_state text default null,
  p_court_district text default null,
  p_industry_code text default null,
  p_estimated_assets jsonb default null,
  p_estimated_liabilities jsonb default null,
  p_estimated_creditor_count jsonb default null,
  p_confidence_score numeric default null,
  p_manual_review_required boolean default false
) returns uuid
language plpgsql
security invoker
set search_path to public
as $$
begin
  update public.bankruptcies
  set
    debtor_name = coalesce(p_debtor_name, debtor_name),
    city = coalesce(p_city, city),
    state = coalesce(p_state, state),
    court_district = coalesce(p_court_district, court_district),
    industry_code = coalesce(p_industry_code, industry_code),
    estimated_assets_range = coalesce(p_estimated_assets, estimated_assets_range),
    estimated_liabilities_range = coalesce(p_estimated_liabilities, estimated_liabilities_range),
    estimated_creditor_count_range = coalesce(
      p_estimated_creditor_count,
      estimated_creditor_count_range
    ),
    estimated_assets = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_assets),
      estimated_assets
    ),
    estimated_liabilities = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_liabilities),
      estimated_liabilities
    ),
    estimated_creditor_count = coalesce(
      public.au_group_jsonb_midpoint_count(p_estimated_creditor_count),
      estimated_creditor_count
    ),
    extraction_confidence_score = p_confidence_score,
    manual_review_required = p_manual_review_required,
    updated_at = now()
  where id = p_bankruptcy_id;

  return p_bankruptcy_id;
end;
$$;

create or replace function public.au_group_merge_creditor_matrix (
  p_bankruptcy_id uuid,
  p_creditors jsonb
) returns integer
language plpgsql
security invoker
set search_path to public
as $$
declare
  item jsonb;
  v_creditor_id uuid;
  merged integer := 0;
begin
  if p_creditors is null or jsonb_typeof(p_creditors) <> 'array' then
    return 0;
  end if;

  for item in select * from jsonb_array_elements(p_creditors)
  loop
    insert into public.creditors (name, address, claim_amount, is_company)
    values (
      item->>'creditor_name',
      item->>'address',
      nullif(item->>'claim_amount', '')::numeric,
      coalesce((item->>'entity_type') = 'company', true)
    )
    returning id into v_creditor_id;

    insert into public.bankruptcy_creditors (bankruptcy_id, creditor_id)
    values (p_bankruptcy_id, v_creditor_id)
    on conflict do nothing;

    merged := merged + 1;
  end loop;

  return merged;
end;
$$;

grant execute on function public.au_group_upsert_bankruptcy_from_form201 (
  uuid, text, text, text, text, text, jsonb, jsonb, jsonb, numeric, boolean
) to service_role;

grant execute on function public.au_group_merge_creditor_matrix (uuid, jsonb) to service_role;
