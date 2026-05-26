-- Wave 2B: admin-configurable state → rep mapping (FR-5.3)

create table if not exists public.au_group_territory_assignments (
  state char(2) primary key,
  rep_name varchar(100) not null,
  salesforce_user_id varchar(18) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists au_group_territory_assignments_set_updated_at
  on public.au_group_territory_assignments;
create trigger au_group_territory_assignments_set_updated_at
  before update on public.au_group_territory_assignments
  for each row execute function public.set_updated_at();

alter table public.au_group_territory_assignments enable row level security;

-- Seed placeholder map (replace salesforce_user_id with real 18-char Ids from Keith)
insert into public.au_group_territory_assignments (state, rep_name, salesforce_user_id)
values
  ('TX', 'Mike', '005PLACEHOLDER01'),
  ('NY', 'Frazier', '005PLACEHOLDER02'),
  ('CA', 'Mike', '005PLACEHOLDER01'),
  ('FL', 'Frazier', '005PLACEHOLDER02'),
  ('NJ', 'Frazier', '005PLACEHOLDER02')
on conflict (state) do nothing;

create or replace function public.au_group_resolve_territory_rep(p_state text)
returns table (
  state char(2),
  rep_name varchar,
  salesforce_user_id varchar
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_state char(2);
begin
  v_state := upper(left(trim(coalesce(p_state, '')), 2));
  if v_state = '' then
    return;
  end if;

  return query
  select t.state, t.rep_name, t.salesforce_user_id
  from public.au_group_territory_assignments t
  where t.state = v_state;

  if not found then
    return query
    select v_state, 'rep_default'::varchar, '005PLACEHOLDER99'::varchar;
  end if;
end;
$$;

comment on function public.au_group_resolve_territory_rep is
  'SYS-00 Resolve Territory: map creditor/bankruptcy state to Salesforce OwnerId';

grant execute on function public.au_group_resolve_territory_rep (text) to service_role;
