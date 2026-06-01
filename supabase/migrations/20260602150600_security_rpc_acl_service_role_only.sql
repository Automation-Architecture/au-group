-- Revoke anon/authenticated/PUBLIC execute on all public.au_group_* RPCs.
-- Callers must use service_role (document-parser, n8n with service key).
-- Fixes au_group_upsert_document_parse_result (was granted to anon).

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
