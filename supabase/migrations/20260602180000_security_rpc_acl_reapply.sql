-- Re-apply service_role-only EXECUTE after KD-21 tier RPCs (20260602170000).
-- CREATE FUNCTION may re-grant anon/authenticated; keep this migration last in the 20260602* batch.

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
