-- Fail if any public.au_group_* function is executable by anon or authenticated.
-- Run after migrations: scripts/ci/verify-supabase-rpc-acl.sh (local CI) or psql on staging.

\set ON_ERROR_STOP on

do $$
declare
  r record;
  bad text[] := array[]::text[];
begin
  for r in
    select
      p.proname,
      pg_get_function_identity_arguments(p.oid) as args,
      role_name
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    cross join lateral (
      values
        ('anon', has_function_privilege('anon', p.oid, 'EXECUTE')),
        ('authenticated', has_function_privilege('authenticated', p.oid, 'EXECUTE')),
        ('public', has_function_privilege('public', p.oid, 'EXECUTE'))
    ) as priv(role_name, allowed)
    where n.nspname = 'public'
      and p.proname like 'au_group\_%'
      and priv.allowed
  loop
    bad := array_append(
      bad,
      format('%s(%s) -> %s', r.proname, r.args, r.role_name)
    );
  end loop;

  if coalesce(array_length(bad, 1), 0) > 0 then
    raise exception 'au_group_* RPC ACL violation (anon/authenticated/public execute): %',
      array_to_string(bad, '; ');
  end if;
end;
$$;

do $$
declare
  v_missing text;
begin
  select string_agg(p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')', ', ')
  into v_missing
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'au_group_merge_creditor_matrix'
    and not has_function_privilege('service_role', p.oid, 'EXECUTE');

  if v_missing is not null then
    raise exception 'service_role missing EXECUTE on: %', v_missing;
  end if;
end;
$$;
