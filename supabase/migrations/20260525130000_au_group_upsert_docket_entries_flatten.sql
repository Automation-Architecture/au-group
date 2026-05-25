-- Flatten nested p_entries (n8n Aggregate append yields [[{...},{...}]]) and coerce numeric docket #s.

create or replace function public.au_group_upsert_docket_entries (
  p_bankruptcy_id uuid,
  p_entries jsonb
) returns integer
language plpgsql
security definer
set search_path to public
as $$
declare
  v_outer jsonb;
  v_entry jsonb;
  v_flat jsonb := '[]'::jsonb;
  v_count integer := 0;
  v_docket_number text;
  v_filed_at timestamptz;
  v_description text;
  v_title text;
  v_document_url text;
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  if p_entries is null or jsonb_typeof(p_entries) <> 'array' then
    update public.bankruptcies
    set last_docket_check_at = now(), updated_at = now()
    where id = p_bankruptcy_id;

    return 0;
  end if;

  for v_outer in select value from jsonb_array_elements(p_entries) as t(value)
  loop
    if jsonb_typeof(v_outer) = 'array' then
      v_flat := v_flat || v_outer;
    elsif jsonb_typeof(v_outer) = 'object' then
      v_flat := v_flat || jsonb_build_array(v_outer);
    end if;
  end loop;

  for v_entry in select value from jsonb_array_elements(v_flat) as t(value)
  loop
    if jsonb_typeof(v_entry) <> 'object' then
      continue;
    end if;

    v_docket_number := coalesce(
      nullif(btrim(v_entry->>'docketEntryNumber'), ''),
      nullif(btrim(v_entry->>'docket_number'), ''),
      nullif(btrim(v_entry->>'docketNumber'), ''),
      nullif(btrim(v_entry->>'entryNumber'), ''),
      nullif(btrim(v_entry->>'docketEntryNum'), '')
    );

    if v_docket_number is null then
      continue;
    end if;

    v_filed_at := null;
    begin
      v_filed_at := coalesce(
        nullif(v_entry->>'dateFiled', '')::timestamptz,
        nullif(v_entry->>'filed_at', '')::timestamptz,
        nullif(v_entry->>'filingDate', '')::timestamptz
      );
    exception
      when others then
        v_filed_at := null;
    end;

    v_description := coalesce(
      nullif(btrim(v_entry->>'description'), ''),
      nullif(btrim(v_entry->>'text'), ''),
      nullif(btrim(v_entry->>'docketText'), '')
    );

    v_title := coalesce(
      nullif(btrim(v_entry->>'title'), ''),
      nullif(left(v_description, 500), '')
    );

    v_document_url := coalesce(
      nullif(btrim(v_entry->>'documentUrl'), ''),
      nullif(btrim(v_entry->>'document_url'), ''),
      nullif(btrim(v_entry->'links'->>'document'), ''),
      nullif(btrim(v_entry->'links'->'document'->>'href'), '')
    );

    insert into public.docket_entries (
      bankruptcy_id,
      docket_number,
      filed_at,
      title,
      description,
      document_url,
      source_type,
      raw_payload
    )
    values (
      p_bankruptcy_id,
      v_docket_number,
      v_filed_at,
      v_title,
      v_description,
      v_document_url,
      'pacer',
      v_entry
    )
    on conflict (bankruptcy_id, docket_number)
    where docket_number is not null and btrim(docket_number) <> ''
    do update set
      filed_at = excluded.filed_at,
      title = excluded.title,
      description = excluded.description,
      document_url = coalesce(excluded.document_url, public.docket_entries.document_url),
      source_type = excluded.source_type,
      raw_payload = excluded.raw_payload;

    v_count := v_count + 1;
  end loop;

  update public.bankruptcies
  set last_docket_check_at = now(), updated_at = now()
  where id = p_bankruptcy_id;

  update public.bankruptcy_case_status
  set
    docket_last_checked_at = now(),
    updated_at = now()
  where bankruptcy_id = p_bankruptcy_id;

  return v_count;
end;
$$;

notify pgrst, 'reload schema';
