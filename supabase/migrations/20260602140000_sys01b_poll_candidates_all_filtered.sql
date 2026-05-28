-- SYS-01B: FR-1.1 — poll all qualifying cases; filters replace batch cap (p_limit).
-- AC-1.1 / FR-1.1: 100% of Chapter 11 filings in configured target states, zero missed via LIMIT.

drop function if exists public.au_group_list_pacer_poll_candidates (int);

create or replace function public.au_group_list_pacer_poll_candidates()
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
    and b.chapter_type::text in ('11', '11-Subchapter-V')
    and public.au_group_is_target_state(b.state)
  order by b.last_docket_check_at nulls first, b.created_at asc;
$$;

comment on function public.au_group_list_pacer_poll_candidates is
  'SYS-01B (FR-1.1): all Ch.11 cases in active target states with valid case_number; no row cap.';

grant execute on function public.au_group_list_pacer_poll_candidates () to service_role;
revoke execute on function public.au_group_list_pacer_poll_candidates () from public;

delete from public.au_group_runtime_config
where config_key = 'sys01b_max_cases_per_run';
