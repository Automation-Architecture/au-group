-- KD-40: fix dedup_audit source_line_numbers merge on ON CONFLICT.
-- WHERE cannot reference SELECT-list aliases from jsonb_array_elements_text SRFs;
-- filter via FROM ... AS elem WHERE elem ~ '^\d+$' (same pattern as v_source_lines parse).

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
  v_source_lines integer[];
  v_dedup_audit jsonb;
  v_existing_audit jsonb;
  v_merged_lines integer[];
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

    if public.au_group_is_junk_creditor_name(v_display_name) then
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

    v_source_lines := coalesce(
      (
        select array_agg(elem::integer order by elem::integer)
        from jsonb_array_elements_text(coalesce(item->'source_line_numbers', '[]'::jsonb)) as elem
        where elem ~ '^\d+$'
      ),
      '{}'::integer[]
    );

    v_dedup_audit := item->'dedup_audit';
    if v_dedup_audit is null or v_dedup_audit = 'null'::jsonb then
      v_dedup_audit := null;
    end if;

    insert into public.creditors (
      name,
      original_name,
      address,
      claim_amount,
      is_company,
      confidence_score,
      source_bankruptcy_id,
      dedup_audit
    )
    values (
      v_display_name,
      v_original_name,
      v_display_address,
      v_claim_amount,
      coalesce((item->>'entity_type') = 'company', true),
      v_confidence,
      p_bankruptcy_id,
      v_dedup_audit
    )
    on conflict (
      lower(trim(name)),
      lower(trim(coalesce(address, '')))
    ) do update set
      claim_amount = coalesce(creditors.claim_amount, 0) + coalesce(excluded.claim_amount, 0),
      original_name = coalesce(creditors.original_name, excluded.original_name),
      confidence_score = coalesce(creditors.confidence_score, excluded.confidence_score),
      source_bankruptcy_id = coalesce(creditors.source_bankruptcy_id, excluded.source_bankruptcy_id),
      dedup_audit = case
        when creditors.dedup_audit is null then excluded.dedup_audit
        when excluded.dedup_audit is null then creditors.dedup_audit
        else (
          with merged as (
            select coalesce(jsonb_agg(distinct n), '[]'::jsonb) as names
            from (
              select jsonb_array_elements_text(
                coalesce(creditors.dedup_audit->'merged_names', '[]'::jsonb)
              ) as n
              union
              select jsonb_array_elements_text(
                coalesce(excluded.dedup_audit->'merged_names', '[]'::jsonb)
              ) as n
            ) names_src
          )
          select jsonb_build_object(
            'dedup_group_id', coalesce(
              excluded.dedup_audit->>'dedup_group_id',
              creditors.dedup_audit->>'dedup_group_id'
            ),
            'merged_names', names,
            'source_line_numbers', to_jsonb(
              (
                select array_agg(distinct ln::integer order by ln::integer)
                from (
                  select elem as ln
                  from jsonb_array_elements_text(
                    coalesce(creditors.dedup_audit->'source_line_numbers', '[]'::jsonb)
                  ) as elem
                  where elem ~ '^\d+$'
                  union
                  select elem as ln
                  from jsonb_array_elements_text(
                    coalesce(excluded.dedup_audit->'source_line_numbers', '[]'::jsonb)
                  ) as elem
                  where elem ~ '^\d+$'
                  union
                  select unnest(v_source_lines)::text as ln
                ) lines
              )
            ),
            'duplicate_count', greatest(1, jsonb_array_length(names))
          )
          from merged
        )
      end,
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
        select c.dedup_audit into v_existing_audit
        from public.creditors c
        where c.id = v_creditor_id;

        v_merged_lines := (
          select coalesce(array_agg(distinct ln order by ln), '{}'::integer[])
          from (
            select unnest(
              coalesce(
                (
                  select array_agg(elem::integer)
                  from jsonb_array_elements_text(
                    coalesce(v_existing_audit->'source_line_numbers', '[]'::jsonb)
                  ) as elem
                  where elem ~ '^\d+$'
                ),
                '{}'::integer[]
              )
            ) as ln
            union
            select unnest(v_source_lines) as ln
          ) combined
        );

        update public.creditors c
        set
          claim_amount = coalesce(c.claim_amount, 0) + coalesce(v_claim_amount, 0),
          original_name = coalesce(c.original_name, v_original_name),
          confidence_score = coalesce(c.confidence_score, v_confidence),
          source_bankruptcy_id = coalesce(c.source_bankruptcy_id, p_bankruptcy_id),
          dedup_audit = case
            when v_dedup_audit is null and v_existing_audit is null then null
            when v_existing_audit is null then v_dedup_audit
            when v_dedup_audit is null then v_existing_audit
            else (
              with merged as (
                select coalesce(jsonb_agg(distinct n), '[]'::jsonb) as names
                from (
                  select jsonb_array_elements_text(
                    coalesce(v_existing_audit->'merged_names', '[]'::jsonb)
                  ) as n
                  union
                  select jsonb_array_elements_text(
                    coalesce(v_dedup_audit->'merged_names', '[]'::jsonb)
                  ) as n
                ) names_src
              )
              select jsonb_build_object(
                'dedup_group_id', coalesce(
                  v_dedup_audit->>'dedup_group_id',
                  v_existing_audit->>'dedup_group_id'
                ),
                'merged_names', names,
                'source_line_numbers', to_jsonb(v_merged_lines),
                'duplicate_count', greatest(1, jsonb_array_length(names))
              )
              from merged
            )
          end,
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
