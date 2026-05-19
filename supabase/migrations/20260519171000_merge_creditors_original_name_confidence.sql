-- Populate creditors.original_name and confidence_score during creditor matrix merge
create or replace function public.au_group_merge_creditor_matrix (
  p_bankruptcy_id uuid,
  p_creditors jsonb,
  p_confidence_score numeric default null
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
  v_original_name text;
  v_confidence numeric;
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

    v_original_name := nullif(
      trim(coalesce(item->>'original_name', item->>'creditor_name', '')),
      ''
    );
    v_confidence := coalesce(
      public.au_group_safe_numeric(item->>'confidence_score'),
      p_confidence_score
    );

    v_display_address := nullif(trim(coalesce(item->>'address', '')), '');
    v_address := lower(coalesce(v_display_address, ''));
    v_claim_amount := public.au_group_safe_numeric(item->>'claim_amount');

    insert into public.creditors (
      name,
      original_name,
      address,
      claim_amount,
      is_company,
      confidence_score,
      source_bankruptcy_id
    )
    values (
      v_display_name,
      v_original_name,
      v_display_address,
      v_claim_amount,
      coalesce((item->>'entity_type') = 'company', true),
      v_confidence,
      p_bankruptcy_id
    )
    on conflict (
      lower(trim(name)),
      lower(trim(coalesce(address, '')))
    ) do update set
      original_name = coalesce(creditors.original_name, excluded.original_name),
      confidence_score = coalesce(creditors.confidence_score, excluded.confidence_score),
      source_bankruptcy_id = coalesce(creditors.source_bankruptcy_id, excluded.source_bankruptcy_id),
      updated_at = now()
    returning id into v_creditor_id;

    if v_creditor_id is null then
      select c.id
      into v_creditor_id
      from public.creditors c
      where lower(trim(c.name)) = v_name
        and lower(trim(coalesce(c.address, ''))) = v_address
      limit 1;

      if v_creditor_id is not null then
        update public.creditors c
        set
          original_name = coalesce(c.original_name, v_original_name),
          confidence_score = coalesce(c.confidence_score, v_confidence),
          source_bankruptcy_id = coalesce(c.source_bankruptcy_id, p_bankruptcy_id),
          updated_at = now()
        where c.id = v_creditor_id;
      end if;
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

grant execute on function public.au_group_merge_creditor_matrix (uuid, jsonb, numeric) to service_role;
