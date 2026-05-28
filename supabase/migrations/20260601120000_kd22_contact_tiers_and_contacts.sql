-- KD-22 / FR-4.2–4.4: Admin-configurable tier rules + contact persistence for SYS-03.

-- ---------------------------------------------------------------------------
-- Tier thresholds (PRD defaults; Keith can UPDATE rows — no code deploy).
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_company_tiers (
  tier smallint primary key check (tier between 1 and 3),
  label text not null,
  min_revenue numeric(15, 2),
  min_employees integer,
  active boolean not null default true,
  notes text,
  updated_at timestamptz not null default now()
);

drop trigger if exists au_group_company_tiers_set_updated_at on public.au_group_company_tiers;
create trigger au_group_company_tiers_set_updated_at
  before update on public.au_group_company_tiers
  for each row execute function public.set_updated_at();

alter table public.au_group_company_tiers enable row level security;

insert into public.au_group_company_tiers (tier, label, min_revenue, min_employees, notes)
values
  (1, 'Enterprise', 1000000000, 5000, 'PRD FR-4.2 Tier 1'),
  (2, 'Mid-Market', 100000000, 500, 'PRD FR-4.2 Tier 2'),
  (3, 'SMB', null, null, 'PRD FR-4.2 Tier 3 — default when below Tier 2')
on conflict (tier) do nothing;

create table if not exists public.au_group_tier_contact_titles (
  id bigserial primary key,
  tier smallint not null references public.au_group_company_tiers (tier) on delete cascade,
  title_pattern text not null,
  sort_order smallint not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_au_group_tier_contact_titles_tier
  on public.au_group_tier_contact_titles (tier, sort_order)
  where active is true;

create unique index if not exists uq_au_group_tier_contact_titles_tier_title
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
  (3, 'AP Manager', 20),
  (3, 'AR Manager', 30),
  (3, 'Accounting Manager', 40),
  (3, 'Office Manager', 50),
  (3, 'Owner', 60)
on conflict (tier, title_pattern) do nothing;

-- ---------------------------------------------------------------------------
-- Classify company tier from firmographics (FR-4.2).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_classify_company_tier(
  p_revenue numeric default null,
  p_employees integer default null
)
returns smallint
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_tier smallint;
begin
  select t.tier
  into v_tier
  from public.au_group_company_tiers t
  where t.active is true
    and (
      (t.min_revenue is not null and p_revenue is not null and p_revenue >= t.min_revenue)
      or (
        t.min_employees is not null
        and p_employees is not null
        and p_employees >= t.min_employees
      )
    )
  order by t.tier asc
  limit 1;

  return coalesce(v_tier, 3::smallint);
end;
$$;

comment on function public.au_group_classify_company_tier is
  'KD-22: classify Enterprise/Mid-Market/SMB from revenue or headcount.';

grant execute on function public.au_group_classify_company_tier (numeric, integer) to service_role;
revoke execute on function public.au_group_classify_company_tier (numeric, integer) from public;

-- ---------------------------------------------------------------------------
-- Titles for a tier, then fallback tiers 2→3 (FR-4.4).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_list_contact_titles(
  p_tier smallint,
  p_include_fallback boolean default true
)
returns text[]
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    array_agg(distinct t.title_pattern order by t.title_pattern),
    '{}'::text[]
  )
  from public.au_group_tier_contact_titles t
  where t.active is true
    and (
      t.tier = p_tier
      or (p_include_fallback and t.tier > p_tier)
    );
$$;

comment on function public.au_group_list_contact_titles is
  'KD-22: job titles for ZoomInfo contact search (primary tier + lower tiers when fallback).';

grant execute on function public.au_group_list_contact_titles (smallint, boolean) to service_role;
revoke execute on function public.au_group_list_contact_titles (smallint, boolean) from public;

-- ---------------------------------------------------------------------------
-- Replace zoom_info_contacts for a creditor (max 3, ranked by engagement_score).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_upsert_zoom_info_contacts(
  p_creditor_id uuid,
  p_contacts jsonb,
  p_company_revenue numeric default null,
  p_company_employee_count integer default null,
  p_company_industry text default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_elem jsonb;
  v_count integer := 0;
  v_saved integer := 0;
begin
  if p_creditor_id is null then
    return 0;
  end if;

  delete from public.zoom_info_contacts where creditor_id = p_creditor_id;

  if p_contacts is null or jsonb_typeof(p_contacts) <> 'array' then
    return 0;
  end if;

  for v_elem in
    select value
    from jsonb_array_elements(p_contacts) as value
    order by coalesce((value->>'engagement_score')::integer, 0) desc
    limit 3
  loop
    v_count := v_count + 1;
    insert into public.zoom_info_contacts (
      creditor_id,
      full_name,
      title,
      email,
      phone,
      company_revenue,
      company_employee_count,
      company_industry,
      engagement_score
    )
    values (
      p_creditor_id,
      coalesce(nullif(trim(v_elem->>'full_name'), ''), 'Unknown'),
      nullif(trim(v_elem->>'title'), ''),
      nullif(trim(v_elem->>'email'), ''),
      nullif(trim(v_elem->>'phone'), ''),
      coalesce((v_elem->>'company_revenue')::numeric, p_company_revenue),
      coalesce((v_elem->>'company_employee_count')::integer, p_company_employee_count),
      coalesce(nullif(trim(v_elem->>'company_industry'), ''), p_company_industry),
      coalesce((v_elem->>'engagement_score')::integer, 0)
    );
    v_saved := v_saved + 1;
  end loop;

  return v_saved;
end;
$$;

comment on function public.au_group_upsert_zoom_info_contacts is
  'KD-22/SYS-03: persist up to 3 ZoomInfo contacts per creditor.';

grant execute on function public.au_group_upsert_zoom_info_contacts (
  uuid, jsonb, numeric, integer, text
) to service_role;
revoke execute on function public.au_group_upsert_zoom_info_contacts (
  uuid, jsonb, numeric, integer, text
) from public;
