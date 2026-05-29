-- Re-apply service_role-only EXECUTE on all au_group_* RPCs after any later migrations
-- that CREATE OR REPLACE functions (Supabase may re-grant anon/authenticated).
-- Keep this migration last among au_group_* changes, or add a newer reapply sibling.

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
