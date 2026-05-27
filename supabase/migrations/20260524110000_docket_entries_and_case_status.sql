-- SYS-01B / SYS-06: PACER docket rows and per-case lifecycle flags.
-- Remote project had these objects before repo migrations; required for fresh `supabase db start`.

alter table public.bankruptcies
  add column if not exists last_docket_check_at timestamptz;

create table if not exists public.bankruptcy_case_status (
  bankruptcy_id uuid primary key references public.bankruptcies (id) on delete cascade,
  has_creditor_matrix boolean not null default false,
  has_schedule_f boolean not null default false,
  has_asset_schedule boolean not null default false,
  enrichment_completed boolean not null default false,
  outreach_ready boolean not null default false,
  lifecycle_stage text not null default 'new',
  docket_last_checked_at timestamptz,
  latest_docket_number integer,
  priority_score numeric(8, 2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists bankruptcy_case_status_set_updated_at on public.bankruptcy_case_status;
create trigger bankruptcy_case_status_set_updated_at
  before update on public.bankruptcy_case_status
  for each row execute function public.set_updated_at();

create table if not exists public.docket_entries (
  id uuid primary key default gen_random_uuid(),
  bankruptcy_id uuid not null references public.bankruptcies (id) on delete cascade,
  docket_number text,
  filed_at timestamptz,
  title text,
  description text,
  document_url text,
  source_type text,
  raw_payload jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_docket_entries_bankruptcy_id
  on public.docket_entries (bankruptcy_id);

-- Existing deployments may have nullable bankruptcy_id from an earlier apply
delete from public.docket_entries
where bankruptcy_id is null;

alter table public.docket_entries
  alter column bankruptcy_id set not null;

alter table public.bankruptcy_case_status enable row level security;
alter table public.docket_entries enable row level security;
