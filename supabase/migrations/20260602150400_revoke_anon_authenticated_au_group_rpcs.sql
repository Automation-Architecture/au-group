-- Supabase default grants EXECUTE to anon/authenticated on public functions.
-- REVOKE FROM PUBLIC alone is insufficient; lock all au_group_* RPCs to service_role.

do $$
declare
  r record;
begin
  for r in
    select
      n.nspname as schema_name,
      p.proname as func_name,
      pg_get_function_identity_arguments(p.oid) as func_args
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname like 'au_group\_%'
      and p.prokind = 'f'
  loop
    execute format(
      'revoke execute on function %I.%I(%s) from public, anon, authenticated',
      r.schema_name,
      r.func_name,
      r.func_args
    );
    execute format(
      'grant execute on function %I.%I(%s) to service_role',
      r.schema_name,
      r.func_name,
      r.func_args
    );
  end loop;
end;
$$;
