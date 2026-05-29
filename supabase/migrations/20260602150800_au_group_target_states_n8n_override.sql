-- KD-14: allow n8n workflows to pass target_states[] (workflow Set node) instead of Supabase table only.

create or replace function public.au_group_active_target_states(p_states text[] default null)
returns setof char(2)
language sql
stable
security definer
set search_path = public
as $$
  select distinct upper(left(trim(s), 2))::char(2)
  from unnest(
    case
      when p_states is not null and coalesce(array_length(p_states, 1), 0) > 0 then
        p_states
      else
        coalesce(
          (select array_agg(t.state::text) from public.au_group_target_states t where t.active),
          array[]::text[]
        )
    end
  ) as u(s)
  where length(trim(s)) >= 2;
$$;

comment on function public.au_group_active_target_states is
  'KD-14: active target state codes; p_states from n8n overrides au_group_target_states table';

grant execute on function public.au_group_active_target_states (text[]) to service_role;
revoke execute on function public.au_group_active_target_states (text[]) from public;

drop function if exists public.au_group_is_target_state(text);

create or replace function public.au_group_is_target_state(
  p_state text,
  p_states text[] default null
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.au_group_active_target_states(p_states) active
    where active = upper(left(trim(coalesce(p_state, '')), 2))::char(2)
  );
$$;

comment on function public.au_group_is_target_state is
  'KD-14: true when state is active; pass p_states from n8n Config — Target States to skip table lookup';

grant execute on function public.au_group_is_target_state (text, text[]) to service_role;
revoke execute on function public.au_group_is_target_state (text, text[]) from public;

drop function if exists public.au_group_list_pacer_poll_candidates(int);

create or replace function public.au_group_list_pacer_poll_candidates(
  p_limit int default null,
  p_states text[] default null
)
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
    and b.state in (select active from public.au_group_active_target_states(p_states) active)
  order by b.last_docket_check_at nulls first, b.created_at asc
  limit v_limit;
end;
$$;

comment on function public.au_group_list_pacer_poll_candidates is
  'SYS-01B: poll candidates in target states; pass p_states from n8n Config — Target States';

grant execute on function public.au_group_list_pacer_poll_candidates (int, text[]) to service_role;
revoke execute on function public.au_group_list_pacer_poll_candidates (int, text[]) from public;
