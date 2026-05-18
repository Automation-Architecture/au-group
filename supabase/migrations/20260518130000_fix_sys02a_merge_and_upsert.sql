-- Fix SYS-02A: creditor dedupe on merge, safe claim_amount cast, preserve review state on upsert

create or replace function public.au_group_safe_numeric (p_text text)
returns numeric
language plpgsql
immutable
set search_path to public
as $$
declare
  cleaned text;
begin
  cleaned := nullif(
    regexp_replace(coalesce(p_text, ''), '[^0-9.]', '', 'g'),
    ''
  );
  if cleaned is null or cleaned !~ '^\d+(\.\d+)?$' then
    return null;
  end if;
  return cleaned::numeric;
exception
  when invalid_text_representation then
    return null;
end;
$$;

-- Normalize duplicate creditors before unique index (re-link junction rows to keeper).
with normalized as (
  select
    id,
    row_number() over (
      partition by lower(trim(name)), lower(trim(coalesce(address, '')))
      order by created_at, id
    ) as rn,
    first_value(id) over (
      partition by lower(trim(name)), lower(trim(coalesce(address, '')))
      order by created_at, id
    ) as keeper_id
  from public.creditors
),
duplicates as (
  select id, keeper_id
  from normalized
  where rn > 1
)
delete from public.bankruptcy_creditors bc
using duplicates d
where bc.creditor_id = d.id
  and exists (
    select 1
    from public.bankruptcy_creditors existing
    where existing.bankruptcy_id = bc.bankruptcy_id
      and existing.creditor_id = d.keeper_id
  );

with normalized as (
  select
    id,
    row_number() over (
      partition by lower(trim(name)), lower(trim(coalesce(address, '')))
      order by created_at, id
    ) as rn,
    first_value(id) over (
      partition by lower(trim(name)), lower(trim(coalesce(address, '')))
      order by created_at, id
    ) as keeper_id
  from public.creditors
),
duplicates as (
  select id, keeper_id
  from normalized
  where rn > 1
)
update public.bankruptcy_creditors bc
set creditor_id = d.keeper_id
from duplicates d
where bc.creditor_id = d.id;

with normalized as (
  select
    id,
    row_number() over (
      partition by lower(trim(name)), lower(trim(coalesce(address, '')))
      order by created_at, id
    ) as rn
  from public.creditors
)
delete from public.creditors c
using normalized n
where c.id = n.id
  and n.rn > 1;

create unique index if not exists idx_creditors_normalized_name_address
  on public.creditors (
    lower(trim(name)),
    lower(trim(coalesce(address, '')))
  );

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
  v_display_name text;
  v_display_address text;
  merged integer := 0;
begin
  if p_creditors is null or jsonb_typeof(p_creditors) <> 'array' then
    return 0;
  end if;

  for item in select * from jsonb_array_elements(p_creditors)
  loop
    v_display_name := trim(coalesce(item->>'creditor_name', ''));
    v_name := lower(v_display_name);
    if v_name = '' then
      continue;
    end if;

    v_display_address := nullif(trim(coalesce(item->>'address', '')), '');
    v_address := lower(coalesce(v_display_address, ''));
    v_claim_amount := public.au_group_safe_numeric(item->>'claim_amount');

    insert into public.creditors (name, address, claim_amount, is_company)
    values (
      v_display_name,
      v_display_address,
      v_claim_amount,
      coalesce((item->>'entity_type') = 'company', true)
    )
    on conflict (
      lower(trim(name)),
      lower(trim(coalesce(address, '')))
    ) do nothing
    returning id into v_creditor_id;

    if v_creditor_id is null then
      select c.id
      into v_creditor_id
      from public.creditors c
      where lower(trim(c.name)) = v_name
        and lower(trim(coalesce(c.address, ''))) = v_address
      limit 1;
    end if;

    if v_creditor_id is null then
      continue;
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

grant execute on function public.au_group_safe_numeric (text) to service_role;

grant execute on function public.au_group_merge_creditor_matrix (uuid, jsonb) to service_role;
