-- Fix SYS-02A: creditor dedupe on merge, safe claim_amount cast, preserve review state on upsert

create or replace function public.au_group_upsert_bankruptcy_from_form201 (
  p_bankruptcy_id uuid,
  p_debtor_name text default null,
  p_city text default null,
  p_state text default null,
  p_court_district text default null,
  p_industry_code text default null,
  p_estimated_assets jsonb default null,
  p_estimated_liabilities jsonb default null,
  p_estimated_creditor_count jsonb default null,
  p_confidence_score numeric default null,
  p_manual_review_required boolean default null
) returns uuid
language plpgsql
security invoker
set search_path to public
as $$
begin
  update public.bankruptcies
  set
    debtor_name = coalesce(p_debtor_name, debtor_name),
    city = coalesce(p_city, city),
    state = coalesce(p_state, state),
    court_district = coalesce(p_court_district, court_district),
    industry_code = coalesce(p_industry_code, industry_code),
    estimated_assets_range = coalesce(p_estimated_assets, estimated_assets_range),
    estimated_liabilities_range = coalesce(p_estimated_liabilities, estimated_liabilities_range),
    estimated_creditor_count_range = coalesce(
      p_estimated_creditor_count,
      estimated_creditor_count_range
    ),
    estimated_assets = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_assets),
      estimated_assets
    ),
    estimated_liabilities = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_liabilities),
      estimated_liabilities
    ),
    estimated_creditor_count = coalesce(
      public.au_group_jsonb_midpoint_count(p_estimated_creditor_count),
      estimated_creditor_count
    ),
    extraction_confidence_score = coalesce(
      p_confidence_score,
      extraction_confidence_score
    ),
    manual_review_required = coalesce(manual_review_required, false)
      or coalesce(p_manual_review_required, false),
    updated_at = now()
  where id = p_bankruptcy_id;

  return p_bankruptcy_id;
end;
$$;

create or replace function public.au_group_merge_creditor_matrix (
  p_bankruptcy_id uuid,
  p_creditors jsonb
) returns integer
language plpgsql
security invoker
set search_path to public
as $$
declare
  item jsonb;
  v_creditor_id uuid;
  v_name text;
  v_address text;
  v_claim_amount numeric;
  merged integer := 0;
begin
  if p_creditors is null or jsonb_typeof(p_creditors) <> 'array' then
    return 0;
  end if;

  for item in select * from jsonb_array_elements(p_creditors)
  loop
    v_name := lower(trim(coalesce(item->>'creditor_name', '')));
    if v_name = '' then
      continue;
    end if;

    v_address := lower(trim(coalesce(item->>'address', '')));
    v_claim_amount := nullif(
      regexp_replace(coalesce(item->>'claim_amount', ''), '[^0-9.]', '', 'g'),
      ''
    )::numeric;

    select c.id
    into v_creditor_id
    from public.creditors c
    where lower(trim(c.name)) = v_name
      and lower(trim(coalesce(c.address, ''))) = v_address
    limit 1;

    if v_creditor_id is null then
      insert into public.creditors (name, address, claim_amount, is_company)
      values (
        item->>'creditor_name',
        item->>'address',
        v_claim_amount,
        coalesce((item->>'entity_type') = 'company', true)
      )
      returning id into v_creditor_id;
    end if;

    insert into public.bankruptcy_creditors (bankruptcy_id, creditor_id)
    values (p_bankruptcy_id, v_creditor_id)
    on conflict do nothing;

    merged := merged + 1;
  end loop;

  return merged;
end;
$$;

grant execute on function public.au_group_upsert_bankruptcy_from_form201 (
  uuid, text, text, text, text, text, jsonb, jsonb, jsonb, numeric, boolean
) to service_role;

grant execute on function public.au_group_merge_creditor_matrix (uuid, jsonb) to service_role;
