-- KD-70 smoke: config audit trigger still writes under RLS (run as service_role / postgres).
-- Usage: psql $DATABASE_URL -f scripts/supabase/test-kd70-config-audit.sql

do $$
declare
  v_before bigint;
  v_after bigint;
begin
  select count(*) into v_before from public.au_group_config_audit;

  update public.au_group_target_states
  set notes = coalesce(notes, '') || ' [kd70-smoke]'
  where state = 'NY';

  select count(*) into v_after from public.au_group_config_audit;

  if v_after <= v_before then
    raise exception 'config audit trigger did not insert (before %, after %)', v_before, v_after;
  end if;

  raise notice 'KD-70 config audit smoke OK (rows % -> %)', v_before, v_after;
end;
$$;
