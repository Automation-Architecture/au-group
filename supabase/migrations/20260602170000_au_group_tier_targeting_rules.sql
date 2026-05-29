-- KD-21: FR-4.2 tier-based targeting rules (configurable thresholds + title mappings)
-- Compatible with existing remote schema (label, title_pattern) and fresh local installs.

create table if not exists public.au_group_company_tiers (
  tier smallint primary key check (tier between 1 and 3),
  label text not null,
  min_revenue numeric(15, 2) not null default 0,
  min_employees integer not null default 0,
  active boolean not null default true,
  notes text,
  updated_at timestamptz not null default now()
);

alter table public.au_group_company_tiers
  add column if not exists label text,
  add column if not exists min_revenue numeric(15, 2) default 0,
  add column if not exists min_employees integer default 0,
  add column if not exists active boolean default true,
  add column if not exists notes text,
  add column if not exists updated_at timestamptz default now();

drop trigger if exists au_group_company_tiers_set_updated_at
  on public.au_group_company_tiers;
create trigger au_group_company_tiers_set_updated_at
  before update on public.au_group_company_tiers
  for each row execute function public.set_updated_at();

alter table public.au_group_company_tiers enable row level security;

insert into public.au_group_company_tiers (tier, label, min_revenue, min_employees, notes)
values
  (1, 'enterprise', 1000000000, 5000, 'PRD FR-4.2 Tier 1 — $1B+ revenue or 5,000+ employees'),
  (2, 'mid_market', 100000000, 500, 'PRD FR-4.2 Tier 2 — $100M–$1B or 500–5,000 employees'),
  (3, 'smb', 0, 0, 'PRD FR-4.2 Tier 3 — below mid-market thresholds')
on conflict (tier) do update
set
  label = excluded.label,
  min_revenue = excluded.min_revenue,
  min_employees = excluded.min_employees,
  notes = excluded.notes;

create table if not exists public.au_group_tier_contact_titles (
  id bigserial primary key,
  tier smallint not null references public.au_group_company_tiers (tier) on delete cascade,
  title_pattern text not null,
  sort_order smallint not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.au_group_tier_contact_titles
  add column if not exists title_pattern text,
  add column if not exists sort_order smallint default 0,
  add column if not exists active boolean default true,
  add column if not exists created_at timestamptz default now();

create unique index if not exists idx_au_group_tier_contact_titles_tier_pattern
  on public.au_group_tier_contact_titles (tier, title_pattern);

alter table public.au_group_tier_contact_titles enable row level security;

insert into public.au_group_tier_contact_titles (tier, title_pattern, sort_order)
values
  (1, 'VP of Finance', 10),
  (1, 'Treasurer', 20),
  (1, 'Director of Credit', 30),
  (1, 'VP of Credit Risk', 40),
  (2, 'CFO', 10),
  (2, 'Controller', 20),
  (2, 'Director of Finance', 30),
  (2, 'Credit Manager', 40),
  (3, 'CFO', 10),
  (3, 'AP/AR Manager', 20),
  (3, 'Accounting Manager', 30),
  (3, 'Office Manager', 40),
  (3, 'Owner', 50)
on conflict (tier, title_pattern) do update
set sort_order = excluded.sort_order;

create or replace function public.au_group_audit_tier_row_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.au_group_config_audit (config_table, action, row_key, old_data, new_data)
  values (
    tg_table_name,
    tg_op,
    coalesce(new.tier, old.tier)::text,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end
  );
  return coalesce(new, old);
end;
$$;

create or replace function public.au_group_audit_tier_title_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_key text;
begin
  v_key := coalesce(new.tier, old.tier)::text || ':' || coalesce(new.title_pattern, old.title_pattern);
  insert into public.au_group_config_audit (config_table, action, row_key, old_data, new_data)
  values (
    tg_table_name,
    tg_op,
    v_key,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end
  );
  return coalesce(new, old);
end;
$$;

drop trigger if exists au_group_company_tiers_audit on public.au_group_company_tiers;
create trigger au_group_company_tiers_audit
  after insert or update or delete on public.au_group_company_tiers
  for each row execute function public.au_group_audit_tier_row_change();

drop trigger if exists au_group_tier_contact_titles_audit on public.au_group_tier_contact_titles;
create trigger au_group_tier_contact_titles_audit
  after insert or update or delete on public.au_group_tier_contact_titles
  for each row execute function public.au_group_audit_tier_title_change();

alter table public.creditors
  add column if not exists company_tier smallint check (company_tier between 1 and 3),
  add column if not exists company_tier_assigned_at timestamptz;

comment on column public.creditors.company_tier is
  'KD-21: assigned Enterprise/Mid-Market/SMB tier (1–3) from ZoomInfo firmographics';
comment on column public.creditors.company_tier_assigned_at is
  'KD-21: when company_tier was last assigned by SYS-03 enrichment';

drop function if exists public.au_group_classify_company_tier(numeric, integer);

create or replace function public.au_group_classify_company_tier(
  p_revenue numeric,
  p_employees integer
)
returns table (
  tier smallint,
  tier_name text,
  min_revenue numeric,
  min_employees integer,
  matched_on text
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_row record;
begin
  if p_revenue is null and p_employees is null then
    return query
    select
      t.tier,
      t.label,
      t.min_revenue,
      t.min_employees,
      'default_null_firmographics'::text
    from public.au_group_company_tiers t
    where t.tier = 3
      and t.active is true;
    return;
  end if;

  for v_row in
    select t.tier, t.label, t.min_revenue, t.min_employees
    from public.au_group_company_tiers t
    where t.active is true
    order by t.tier asc
  loop
    if (p_revenue is not null and p_revenue >= v_row.min_revenue)
       or (p_employees is not null and p_employees >= v_row.min_employees) then
      return query
      select
        v_row.tier,
        v_row.label,
        v_row.min_revenue,
        v_row.min_employees,
        case
          when p_revenue is not null
               and p_revenue >= v_row.min_revenue
               and p_employees is not null
               and p_employees >= v_row.min_employees then 'revenue_and_employees'
          when p_revenue is not null and p_revenue >= v_row.min_revenue then 'revenue'
          else 'employees'
        end;
      return;
    end if;
  end loop;

  return query
  select
    t.tier,
    t.label,
    t.min_revenue,
    t.min_employees,
    'fallback_smb'::text
  from public.au_group_company_tiers t
  where t.tier = 3
    and t.active is true;
end;
$$;

comment on function public.au_group_classify_company_tier is
  'KD-21: classify company tier from revenue/employees using au_group_company_tiers (EC-2.3 inclusive >=)';

create or replace function public.au_group_list_tier_contact_titles(p_tier integer)
returns table (
  title text,
  sort_order integer
)
language sql
stable
security definer
set search_path = public
as $$
  select t.title_pattern as title, t.sort_order::integer
  from public.au_group_tier_contact_titles t
  where t.tier = p_tier
    and t.active is true
  order by t.sort_order asc, t.title_pattern asc;
$$;

comment on function public.au_group_list_tier_contact_titles is
  'KD-21: ordered decision-maker titles for a tier (SYS-03 ZoomInfo contact filter)';

create or replace function public.au_group_get_tier_targeting_config()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'tiers',
    coalesce(
      (
        select jsonb_agg(
          jsonb_build_object(
            'tier', t.tier,
            'name', t.label,
            'min_revenue', t.min_revenue,
            'min_employees', t.min_employees,
            'active', t.active,
            'titles',
            coalesce(
              (
                select jsonb_agg(ct.title_pattern order by ct.sort_order, ct.title_pattern)
                from public.au_group_tier_contact_titles ct
                where ct.tier = t.tier
                  and ct.active is true
              ),
              '[]'::jsonb
            )
          )
          order by t.tier
        )
        from public.au_group_company_tiers t
        where t.active is true
      ),
      '[]'::jsonb
    )
  );
$$;

comment on function public.au_group_get_tier_targeting_config is
  'KD-21: JSON snapshot of tier thresholds and title mappings for ops/debug';

create or replace function public.au_group_set_creditor_company_tier(
  p_creditor_id uuid,
  p_tier smallint
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_creditor_id is null then
    return false;
  end if;
  if p_tier is null or p_tier < 1 or p_tier > 3 then
    return false;
  end if;

  update public.creditors c
  set
    company_tier = p_tier,
    company_tier_assigned_at = now(),
    updated_at = now()
  where c.id = p_creditor_id;

  return found;
end;
$$;

comment on function public.au_group_set_creditor_company_tier is
  'KD-21: persist assigned company tier on creditors after SYS-03 enrichment';

grant execute on function public.au_group_classify_company_tier (numeric, integer) to service_role;
grant execute on function public.au_group_list_tier_contact_titles (integer) to service_role;
grant execute on function public.au_group_get_tier_targeting_config () to service_role;
grant execute on function public.au_group_set_creditor_company_tier (uuid, smallint) to service_role;

revoke all on function public.au_group_classify_company_tier (numeric, integer) from public;
revoke all on function public.au_group_classify_company_tier (numeric, integer) from anon;
revoke all on function public.au_group_classify_company_tier (numeric, integer) from authenticated;
revoke all on function public.au_group_list_tier_contact_titles (integer) from public;
revoke all on function public.au_group_list_tier_contact_titles (integer) from anon;
revoke all on function public.au_group_list_tier_contact_titles (integer) from authenticated;
revoke all on function public.au_group_get_tier_targeting_config () from public;
revoke all on function public.au_group_get_tier_targeting_config () from anon;
revoke all on function public.au_group_get_tier_targeting_config () from authenticated;
revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint) from public;
revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint) from anon;
revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint) from authenticated;
