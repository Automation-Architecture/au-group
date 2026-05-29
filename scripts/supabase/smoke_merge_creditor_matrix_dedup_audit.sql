-- KD-40: smoke ON CONFLICT dedup_audit merge (requires 20260602150500 SRF WHERE fix).
-- Asserts: claim sum, merged_names union, numeric-only source_line_numbers filter.
\set ON_ERROR_STOP on

do $$
declare
  v_bid uuid;
  v_creditor_id uuid;
  v_row_count int;
  v_claim numeric;
  v_audit jsonb;
  v_lines jsonb;
  v_case text := 'KD40-SMOKE-' || replace(gen_random_uuid()::text, '-', '');
begin
  insert into public.bankruptcies (
    case_number,
    debtor_name,
    filing_date,
    court_district,
    chapter_type,
    state
  )
  values (
    v_case,
    'KD40 Smoke Debtor',
    current_date,
    'D. Delaware',
    '11',
    'DE'
  )
  returning id into v_bid;

  perform public.au_group_merge_creditor_matrix(
    v_bid,
    jsonb_build_array(
      jsonb_build_object(
        'creditor_name', 'Smoke Test Creditor LLC',
        'address', '1 Test Lane',
        'claim_amount', 100,
        'entity_type', 'company',
        'source_line_numbers', jsonb_build_array(1),
        'dedup_audit', jsonb_build_object(
          'dedup_group_id', 'smoke-g1',
          'merged_names', jsonb_build_array('Smoke Test Creditor LLC'),
          'source_line_numbers', jsonb_build_array(1, 'not-a-line'),
          'duplicate_count', 1
        )
      )
    ),
    null::numeric
  );

  perform public.au_group_merge_creditor_matrix(
    v_bid,
    jsonb_build_array(
      jsonb_build_object(
        'creditor_name', 'Smoke Test Creditor LLC',
        'address', '1 Test Lane',
        'claim_amount', 50,
        'entity_type', 'company',
        'source_line_numbers', jsonb_build_array(2),
        'dedup_audit', jsonb_build_object(
          'dedup_group_id', 'smoke-g2',
          'merged_names', jsonb_build_array('Smoke Test Creditor LLC'),
          'source_line_numbers', jsonb_build_array(2),
          'duplicate_count', 1
        )
      )
    ),
    null::numeric
  );

  select count(*)
  into v_row_count
  from public.creditors c
  where lower(trim(c.name)) = lower(trim('Smoke Test Creditor LLC'))
    and lower(trim(coalesce(c.address, ''))) = lower(trim('1 Test Lane'));

  if v_row_count <> 1 then
    raise exception 'smoke failed: expected 1 creditor, got %', v_row_count;
  end if;

  select c.id, c.claim_amount, c.dedup_audit
  into v_creditor_id, v_claim, v_audit
  from public.creditors c
  where lower(trim(c.name)) = lower(trim('Smoke Test Creditor LLC'))
    and lower(trim(coalesce(c.address, ''))) = lower(trim('1 Test Lane'));

  if v_creditor_id is null then
    raise exception 'smoke failed: creditor row not found after merge';
  end if;

  if v_claim is distinct from 150 then
    raise exception 'smoke failed: expected claim_amount 150, got %', v_claim;
  end if;

  if v_audit is null then
    raise exception 'smoke failed: dedup_audit is null after merge';
  end if;

  v_lines := v_audit -> 'source_line_numbers';
  if v_lines is null or jsonb_array_length(v_lines) <> 2 then
    raise exception 'smoke failed: expected 2 source_line_numbers, got %', v_lines;
  end if;

  if not (v_lines @> '[1]'::jsonb and v_lines @> '[2]'::jsonb) then
    raise exception 'smoke failed: source_line_numbers missing 1 or 2: %', v_lines;
  end if;

  if v_audit -> 'merged_names' is null
     or not (v_audit -> 'merged_names' @> '"Smoke Test Creditor LLC"'::jsonb) then
    raise exception 'smoke failed: merged_names missing canonical name: %', v_audit -> 'merged_names';
  end if;

  delete from public.bankruptcy_creditors where bankruptcy_id = v_bid;
  delete from public.creditors where id = v_creditor_id;
  delete from public.bankruptcies where id = v_bid;

  raise notice 'KD-40 merge_creditor_matrix dedup_audit smoke OK (case %)', v_case;
end;
$$;
