-- Verify au_group_* RPCs are not executable by public, anon, or authenticated.
-- Run after migrations: psql $DATABASE_URL -f scripts/supabase/verify-rpc-acl.sql
-- Exit non-zero: \set ON_ERROR_STOP on (default in psql -f)

\set ON_ERROR_STOP on

do $$
declare
  v_violations integer;
begin
  select count(*)::integer
  into v_violations
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  join aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a on true
  join pg_roles r on r.oid = a.grantee
  where n.nspname = 'public'
    and p.proname like 'au_group\_%'
    and a.privilege_type = 'EXECUTE'
    and r.rolname in ('public', 'anon', 'authenticated');  -- Supabase grants anon by default

  if v_violations > 0 then
    raise exception
      'RPC ACL: % au_group_* function(s) still executable by public/anon/authenticated',
      v_violations;
  end if;
end;
$$;

\echo '=== RPC ACL violations: none (OK) ==='

\echo ''
\echo '=== service_role execute on critical RPCs (expect 1 row each) ==='

select p.proname, count(*) filter (where r.rolname = 'service_role') as service_role_grants
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
left join aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a on true
left join pg_roles r on r.oid = a.grantee and a.privilege_type = 'EXECUTE'
where n.nspname = 'public'
  and p.proname in (
    'au_group_upsert_document_parse_result',
    'au_group_list_company_creditors',
    'au_group_count_company_creditors',
    'au_group_company_lookup_prepare',
    'au_group_normalize_company_name'
  )
group by p.proname
order by 1;
