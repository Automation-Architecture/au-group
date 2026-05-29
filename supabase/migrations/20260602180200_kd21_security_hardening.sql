-- KD-21 security hardening: scoped set_creditor, tier table RLS deny, config_audit RLS.

-- Explicit deny for API roles on tier config tables (service_role bypasses via dashboard/CI).
drop policy if exists au_group_company_tiers_deny_public on public.au_group_company_tiers;
create policy au_group_company_tiers_deny_public
  on public.au_group_company_tiers
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists au_group_tier_contact_titles_deny_public on public.au_group_tier_contact_titles;
create policy au_group_tier_contact_titles_deny_public
  on public.au_group_tier_contact_titles
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

alter table public.au_group_config_audit enable row level security;

drop policy if exists au_group_config_audit_deny_public on public.au_group_config_audit;
create policy au_group_config_audit_deny_public
  on public.au_group_config_audit
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

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
    and p_tier between 1 and 3
    and t.active is true
  order by t.sort_order asc, t.title_pattern asc;
$$;

drop function if exists public.au_group_set_creditor_company_tier(uuid, smallint);

create or replace function public.au_group_set_creditor_company_tier(
  p_creditor_id uuid,
  p_tier smallint,
  p_bankruptcy_id uuid default null
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

  if p_bankruptcy_id is not null then
    update public.creditors c
    set
      company_tier = p_tier,
      company_tier_assigned_at = now(),
      updated_at = now()
    where c.id = p_creditor_id
      and (
        exists (
          select 1
          from public.bankruptcy_creditors bc
          where bc.creditor_id = c.id
            and bc.bankruptcy_id = p_bankruptcy_id
        )
        or c.source_bankruptcy_id = p_bankruptcy_id
      );

    return found;
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

comment on function public.au_group_set_creditor_company_tier(uuid, smallint, uuid) is
  'KD-21: persist company tier; optional p_bankruptcy_id scopes update to case-linked creditors';

grant execute on function public.au_group_set_creditor_company_tier (uuid, smallint, uuid) to service_role;

revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint, uuid) from public;
revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint, uuid) from anon;
revoke all on function public.au_group_set_creditor_company_tier (uuid, smallint, uuid) from authenticated;

-- Re-apply ACL on all au_group_* RPCs after CREATE OR REPLACE above.
do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as func_sig
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname like 'au_group\_%'
  loop
    execute format('revoke all on function %s from public', r.func_sig);
    execute format('revoke all on function %s from anon', r.func_sig);
    execute format('revoke all on function %s from authenticated', r.func_sig);
    execute format('grant execute on function %s to service_role', r.func_sig);
  end loop;
end;
$$;
