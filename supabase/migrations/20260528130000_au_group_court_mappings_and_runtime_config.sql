-- Data-driven court → state/district (replaces hardcoded n8n maps)
-- Runtime config for limits/defaults (replaces hardcoded n8n fallbacks)

create table if not exists public.au_group_court_mappings (
  court_id varchar(32) primary key,
  state char(2) not null,
  court_district varchar(100) not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists au_group_court_mappings_set_updated_at
  on public.au_group_court_mappings;
create trigger au_group_court_mappings_set_updated_at
  before update on public.au_group_court_mappings
  for each row execute function public.set_updated_at();

alter table public.au_group_court_mappings enable row level security;

insert into public.au_group_court_mappings (court_id, state, court_district)
values
  ('nysb', 'NY', 'Southern District of New York'),
  ('nyeb', 'NY', 'Eastern District of New York'),
  ('njb', 'NJ', 'District of New Jersey'),
  ('paeb', 'PA', 'Eastern District of Pennsylvania'),
  ('pawb', 'PA', 'Western District of Pennsylvania'),
  ('flsb', 'FL', 'Southern District of Florida'),
  ('flmb', 'FL', 'Middle District of Florida'),
  ('flnb', 'FL', 'Northern District of Florida'),
  ('maeb', 'MI', 'Eastern District of Michigan'),
  ('miwb', 'MI', 'Western District of Michigan'),
  ('txsb', 'TX', 'Southern District of Texas'),
  ('txnb', 'TX', 'Northern District of Texas'),
  ('deb', 'DE', 'District of Delaware')
on conflict (court_id) do nothing;

create table if not exists public.au_group_runtime_config (
  config_key text primary key,
  config_value text not null,
  notes text,
  updated_at timestamptz not null default now()
);

drop trigger if exists au_group_runtime_config_set_updated_at
  on public.au_group_runtime_config;
create trigger au_group_runtime_config_set_updated_at
  before update on public.au_group_runtime_config
  for each row execute function public.set_updated_at();

alter table public.au_group_runtime_config enable row level security;

create or replace function public.au_group_resolve_court_mapping(p_court_id text)
returns table (
  court_id varchar,
  state char(2),
  court_district varchar
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_court_id varchar;
begin
  v_court_id := lower(trim(coalesce(p_court_id, '')));
  if v_court_id = '' then
    return;
  end if;

  return query
  select m.court_id, m.state, m.court_district
  from public.au_group_court_mappings m
  where m.active is true
    and m.court_id = v_court_id;
end;
$$;

grant execute on function public.au_group_resolve_court_mapping (text) to service_role;

create or replace function public.au_group_get_runtime_config(p_key text)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select c.config_value
  from public.au_group_runtime_config c
  where c.config_key = trim(coalesce(p_key, ''));
$$;

grant execute on function public.au_group_get_runtime_config (text) to service_role;

create or replace function public.au_group_list_pacer_poll_candidates(p_limit int default null)
returns setof public.bankruptcies
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_limit int;
  v_config text;
begin
  v_limit := p_limit;
  if v_limit is null then
    select public.au_group_get_runtime_config('sys01b_max_cases_per_run') into v_config;
    if v_config is not null and trim(v_config) <> '' then
      v_limit := trim(v_config)::int;
    end if;
  end if;

  if v_limit is null or v_limit < 1 then
    raise exception 'au_group_list_pacer_poll_candidates: set p_limit or au_group_runtime_config.sys01b_max_cases_per_run';
  end if;

  return query
  select b.*
  from public.bankruptcies b
  where b.case_number is not null
    and trim(b.case_number) <> ''
    and b.state in (
      select t.state from public.au_group_target_states t where t.active is true
    )
  order by b.last_docket_check_at nulls first, b.created_at asc
  limit v_limit;
end;
$$;

grant execute on function public.au_group_list_pacer_poll_candidates (int) to service_role;

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('sys01b_max_cases_per_run', '20', 'PACER nightly poll batch size when n8n omits p_limit'),
  ('default_chapter_type', '11', 'RSS/SYS-01 chapter when feed item omits chapter')
on conflict (config_key) do nothing;
