-- AU Group — bankruptcy creditor pipeline (public schema)
-- Run once in Supabase SQL Editor on the project where tables are missing.
--
-- If you use Cursor Supabase MCP, confirm the linked project matches the dashboard:
--   MCP `get_project_url` / dashboard URL must use the same project ref.
-- This repo’s .cursor/mcp.json uses project_ref umivttszdnsrosbqryia — if MCP was
-- linked to a different account/project, migrations may have landed elsewhere.

create extension if not exists pg_trgm with schema extensions;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path to public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$ begin
  create type public.au_group_chapter_type as enum ('11', '7', '11-Subchapter-V');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.au_group_job_type as enum (
    'pacer_poll',
    'document_parse',
    'zoom_info_enrich',
    'salesforce_push'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.au_group_job_status as enum (
    'pending',
    'running',
    'completed',
    'failed'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type public.au_group_schedule_f_status as enum (
    'monitoring',
    'detected',
    'pending_approval',
    'approved',
    'rejected',
    'processed'
  );
exception
  when duplicate_object then null;
end $$;

create table if not exists public.bankruptcies (
  id uuid primary key default gen_random_uuid(),
  case_number varchar(50) not null unique,
  debtor_name varchar(255) not null,
  filing_date date not null,
  court_district varchar(100) not null,
  estimated_assets numeric(15, 2),
  estimated_liabilities numeric(15, 2),
  estimated_creditor_count integer,
  chapter_type public.au_group_chapter_type not null,
  state varchar(2) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.creditors (
  id uuid primary key default gen_random_uuid(),
  name varchar(500) not null,
  address text,
  claim_amount numeric(15, 2),
  claim_date date,
  nature_of_claim varchar(255),
  is_company boolean not null default true,
  is_contingent boolean not null default false,
  is_unliquidated boolean not null default false,
  is_disputed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bankruptcy_creditors (
  bankruptcy_id uuid not null references public.bankruptcies (id) on delete cascade,
  creditor_id uuid not null references public.creditors (id) on delete cascade,
  primary key (bankruptcy_id, creditor_id)
);

drop trigger if exists bankruptcies_set_updated_at on public.bankruptcies;
create trigger bankruptcies_set_updated_at
  before update on public.bankruptcies
  for each row execute function public.set_updated_at();

drop trigger if exists creditors_set_updated_at on public.creditors;
create trigger creditors_set_updated_at
  before update on public.creditors
  for each row execute function public.set_updated_at();

create table if not exists public.zoom_info_contacts (
  id uuid primary key default gen_random_uuid(),
  creditor_id uuid not null references public.creditors (id) on delete cascade,
  full_name varchar(255) not null,
  title varchar(255),
  email varchar(255),
  phone varchar(50),
  company_revenue numeric(15, 2),
  company_employee_count integer,
  company_industry varchar(255),
  engagement_score integer,
  created_at timestamptz not null default now()
);

create table if not exists public.salesforce_accounts (
  id uuid primary key default gen_random_uuid(),
  creditor_id uuid not null references public.creditors (id) on delete cascade,
  salesforce_account_id varchar(18) not null unique,
  territory_rep varchar(100),
  last_sync_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  job_type public.au_group_job_type not null,
  status public.au_group_job_status not null,
  bankruptcy_id uuid references public.bankruptcies (id),
  retry_count integer not null default 0,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.schedule_f_queue (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid not null references public.bankruptcies (id) on delete cascade,
  status public.au_group_schedule_f_status not null,
  docket_entry_number varchar(50),
  page_count integer,
  estimated_cost numeric(6, 2),
  last_scanned_at timestamptz,
  detected_at timestamptz,
  approved_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.pipeline_executions (
  id bigserial primary key,
  n8n_workflow_id text,
  n8n_execution_id text,
  processing_job_id uuid references public.processing_jobs (id) on delete set null,
  bankruptcy_id uuid references public.bankruptcies (id) on delete set null,
  status text not null default 'started',
  error_message text,
  payload jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.bankruptcies enable row level security;
alter table public.creditors enable row level security;
alter table public.bankruptcy_creditors enable row level security;
alter table public.zoom_info_contacts enable row level security;
alter table public.salesforce_accounts enable row level security;
alter table public.processing_jobs enable row level security;
alter table public.schedule_f_queue enable row level security;
alter table public.pipeline_executions enable row level security;

create index if not exists idx_bankruptcies_filing_date on public.bankruptcies (filing_date);
create index if not exists idx_bankruptcies_state on public.bankruptcies (state);
create index if not exists idx_creditors_name_gin on public.creditors using gin (name gin_trgm_ops);
create index if not exists idx_processing_jobs_status on public.processing_jobs (status);
create index if not exists idx_processing_jobs_bankruptcy_id on public.processing_jobs (bankruptcy_id);
create index if not exists idx_schedule_f_queue_status on public.schedule_f_queue (status);
create index if not exists idx_zoom_info_contacts_creditor_id on public.zoom_info_contacts (creditor_id);
create index if not exists idx_salesforce_accounts_creditor_id on public.salesforce_accounts (creditor_id);
create index if not exists idx_pipeline_executions_created_at on public.pipeline_executions (created_at desc);
create index if not exists idx_pipeline_executions_n8n_execution on public.pipeline_executions (n8n_execution_id)
  where n8n_execution_id is not null;
