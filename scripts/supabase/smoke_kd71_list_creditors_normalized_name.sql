-- KD-71: smoke au_group_list_company_creditors.normalized_name (requires 20260603130001).
-- Asserts: (1) the new normalized_name column equals au_group_normalize_company_name(name)
-- for a seeded company creditor, and (2) the recreated function is service-role-only
-- (DROP+CREATE must not have left EXECUTE granted to public/anon/authenticated).
\set ON_ERROR_STOP on

do $$
declare
  v_bid uuid;
  v_case text := 'KD71-SMOKE-' || replace(gen_random_uuid()::text, '-', '');
  v_raw_name text := 'Acme Holdings Incorporated';
  v_got_normalized text;
  v_expected_normalized text;
  v_creditor_ids uuid[];
begin
  insert into public.bankruptcies (
    case_number, debtor_name, filing_date, court_district, chapter_type, state
  )
  values (
    v_case, 'KD71 Smoke Debtor', current_date, 'D. Delaware', '11', 'DE'
  )
  returning id into v_bid;

  -- Seed one company creditor via the canonical merge RPC (sets is_company + links).
  perform public.au_group_merge_creditor_matrix(
    v_bid,
    jsonb_build_array(
      jsonb_build_object(
        'creditor_name', v_raw_name,
        'address', '1 Test Lane',
        'claim_amount', 100,
        'entity_type', 'company',
        'source_line_numbers', jsonb_build_array(1)
      )
    ),
    null::numeric
  );

  -- (1) normalized_name column matches the normalizer RPC.
  select l.normalized_name
  into v_got_normalized
  from public.au_group_list_company_creditors(v_bid) l
  where l.creditor_name = v_raw_name;

  v_expected_normalized := public.au_group_normalize_company_name(v_raw_name);

  if v_got_normalized is null then
    raise exception 'smoke failed: creditor % not returned by list_company_creditors', v_raw_name;
  end if;

  if v_got_normalized is distinct from v_expected_normalized then
    raise exception 'smoke failed: normalized_name % <> normalizer output %',
      v_got_normalized, v_expected_normalized;
  end if;

  -- (2) service-role-only ACL on the recreated function. anon/authenticated inherit any
  -- PUBLIC grant, so checking them catches a leaked default-PUBLIC EXECUTE too. ('public'
  -- is a pseudo-role, not a valid has_function_privilege argument.)
  if has_function_privilege('anon',          'public.au_group_list_company_creditors(uuid)', 'execute')
     or has_function_privilege('authenticated', 'public.au_group_list_company_creditors(uuid)', 'execute') then
    raise exception 'smoke failed: list_company_creditors EXECUTE leaked to anon/authenticated (or PUBLIC)';
  end if;

  if not has_function_privilege('service_role', 'public.au_group_list_company_creditors(uuid)', 'execute') then
    raise exception 'smoke failed: service_role missing EXECUTE on list_company_creditors';
  end if;

  -- Cleanup (collect creditor ids before dropping the link rows).
  select array_agg(bc.creditor_id) into v_creditor_ids
  from public.bankruptcy_creditors bc where bc.bankruptcy_id = v_bid;

  delete from public.bankruptcy_creditors where bankruptcy_id = v_bid;
  if v_creditor_ids is not null then
    delete from public.creditors where id = any(v_creditor_ids);
  end if;
  delete from public.bankruptcies where id = v_bid;

  raise notice 'KD-71 list_company_creditors normalized_name smoke OK (case %, normalized=%)',
    v_case, v_expected_normalized;
end;
$$;
