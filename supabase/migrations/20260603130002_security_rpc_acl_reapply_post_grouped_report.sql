-- Re-apply service_role-only EXECUTE on all au_group_* RPCs.
--
-- Sibling of 20260602150900_security_rpc_acl_reapply.sql, whose own header warns it must
-- stay last among au_group_* changes "or add a newer reapply sibling". Two later migrations
-- broke that: 20260603120000 (KD-60) created au_group_daily_creditor_report_grouped and
-- au_group_creditor_pipeline_status with only `revoke ... from public` — leaving the
-- Supabase-default anon/authenticated EXECUTE grants in place (caught by verify-rpc-acl.sql).
-- This re-runs the sweep so every au_group_* function — including those and KD-71's
-- recreated list_company_creditors — is locked to service_role only. Idempotent.

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
