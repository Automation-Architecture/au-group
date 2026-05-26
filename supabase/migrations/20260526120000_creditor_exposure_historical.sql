-- Wave 4: Historical import + exposure scoring (FR-6)

create table if not exists public.historical_import_batches (
  id uuid primary key default gen_random_uuid(),
  source_filename text not null,
  row_count integer not null default 0,
  status text not null default 'pending',
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.creditor_exposure_summary (
  creditor_id uuid primary key references public.creditors (id) on delete cascade,
  filing_count integer not null default 0,
  total_claim_amount numeric(15, 2) not null default 0,
  first_seen date,
  last_seen date,
  historical_import_count integer not null default 0,
  platform_filing_count integer not null default 0,
  updated_at timestamptz not null default now()
);

drop trigger if exists creditor_exposure_summary_set_updated_at on public.creditor_exposure_summary;
create trigger creditor_exposure_summary_set_updated_at
  before update on public.creditor_exposure_summary
  for each row execute function public.set_updated_at();

alter table public.historical_import_batches enable row level security;
alter table public.creditor_exposure_summary enable row level security;

create or replace function public.au_group_recompute_exposure(p_creditor_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
  v_total numeric(15, 2);
  v_first date;
  v_last date;
begin
  if p_creditor_id is null then
    raise exception 'p_creditor_id is required';
  end if;

  select
    count(*)::integer,
    coalesce(sum(c.claim_amount), 0),
    min(b.filing_date),
    max(b.filing_date)
  into v_count, v_total, v_first, v_last
  from public.bankruptcy_creditors bc
  join public.creditors c on c.id = bc.creditor_id
  join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.creditor_id = p_creditor_id;

  insert into public.creditor_exposure_summary (
    creditor_id,
    filing_count,
    total_claim_amount,
    first_seen,
    last_seen,
    platform_filing_count,
    updated_at
  )
  values (
    p_creditor_id,
    coalesce(v_count, 0),
    coalesce(v_total, 0),
    v_first,
    v_last,
    coalesce(v_count, 0),
    now()
  )
  on conflict (creditor_id) do update
  set
    filing_count = excluded.filing_count + creditor_exposure_summary.historical_import_count,
    total_claim_amount = excluded.total_claim_amount,
    first_seen = least(creditor_exposure_summary.first_seen, excluded.first_seen),
    last_seen = greatest(creditor_exposure_summary.last_seen, excluded.last_seen),
    platform_filing_count = excluded.platform_filing_count,
    updated_at = now();
end;
$$;

create or replace function public.au_group_check_repeat_exposure(
  p_creditor_id uuid,
  p_threshold integer default 4,
  p_window_months integer default 18
)
returns table (
  is_repeat boolean,
  filing_count integer,
  total_claim_amount numeric,
  suggested_message text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
  v_total numeric(15, 2);
  v_cutoff date;
begin
  v_cutoff := (current_date - (p_window_months || ' months')::interval)::date;

  select count(*)::integer, coalesce(sum(c.claim_amount), 0)
  into v_count, v_total
  from public.bankruptcy_creditors bc
  join public.creditors c on c.id = bc.creditor_id
  join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.creditor_id = p_creditor_id
    and b.filing_date >= v_cutoff;

  return query
  select
    v_count >= p_threshold,
    v_count,
    v_total,
    format(
      'Repeat exposure: %s filings since %s totaling $%s — use alternate messaging',
      v_count,
      v_cutoff,
      to_char(v_total, 'FM999,999,999.00')
    );
end;
$$;

grant execute on function public.au_group_recompute_exposure (uuid) to service_role;
grant execute on function public.au_group_check_repeat_exposure (uuid, integer, integer) to service_role;
