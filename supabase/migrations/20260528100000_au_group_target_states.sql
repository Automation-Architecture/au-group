-- KD-14: admin-configurable target states (FR-1.1)

create table if not exists public.au_group_target_states (
  state char(2) primary key,
  active boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists au_group_target_states_set_updated_at
  on public.au_group_target_states;
create trigger au_group_target_states_set_updated_at
  before update on public.au_group_target_states
  for each row execute function public.set_updated_at();

alter table public.au_group_target_states enable row level security;

insert into public.au_group_target_states (state, active, notes)
values
  ('NY', true, 'Discovery rollout — Keith 2026-05-21'),
  ('NJ', true, 'Discovery rollout — Keith 2026-05-21'),
  ('PA', true, 'Discovery rollout — Keith 2026-05-21'),
  ('FL', true, 'Discovery rollout — Keith 2026-05-21'),
  ('MI', true, 'Discovery rollout — Keith 2026-05-21')
on conflict (state) do nothing;

create table if not exists public.au_group_config_audit (
  id bigserial primary key,
  config_table text not null,
  action text not null,
  row_key text,
  old_data jsonb,
  new_data jsonb,
  changed_at timestamptz not null default now()
);

create or replace function public.au_group_audit_config_change()
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
    coalesce(new.state, old.state)::text,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end
  );
  return coalesce(new, old);
end;
$$;

drop trigger if exists au_group_target_states_audit on public.au_group_target_states;
create trigger au_group_target_states_audit
  after insert or update or delete on public.au_group_target_states
  for each row execute function public.au_group_audit_config_change();

create or replace function public.au_group_list_target_states()
returns setof char(2)
language sql
stable
security definer
set search_path = public
as $$
  select t.state
  from public.au_group_target_states t
  where t.active is true
  order by t.state;
$$;

comment on function public.au_group_list_target_states is
  'KD-14: active target states for PACER intake and poll filtering';

grant execute on function public.au_group_list_target_states () to service_role;

create or replace function public.au_group_is_target_state(p_state text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.au_group_target_states t
    where t.active is true
      and t.state = upper(left(trim(coalesce(p_state, '')), 2))
  );
$$;

comment on function public.au_group_is_target_state is
  'KD-14: true when state is in active target list';

grant execute on function public.au_group_is_target_state (text) to service_role;

create or replace function public.au_group_list_pacer_poll_candidates(p_limit int default 20)
returns setof public.bankruptcies
language sql
stable
security definer
set search_path = public
as $$
  select b.*
  from public.bankruptcies b
  where b.case_number is not null
    and trim(b.case_number) <> ''
    and b.state in (
      select t.state from public.au_group_target_states t where t.active is true
    )
  order by b.last_docket_check_at nulls first, b.created_at asc
  limit greatest(coalesce(p_limit, 20), 1);
$$;

comment on function public.au_group_list_pacer_poll_candidates is
  'SYS-01B: bankruptcies in target states due for PACER docket poll';

grant execute on function public.au_group_list_pacer_poll_candidates (int) to service_role;
