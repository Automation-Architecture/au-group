-- Single source of truth for creditor junk-name rules (RPC layer).
-- Thresholds: au_group_runtime_config keys creditor_name_min_length,
-- creditor_line_number_max_digits (defaults 3). Parser mirrors via Settings env vars.

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('creditor_name_min_length', '3', 'Junk filter: min name length (parser Settings default)'),
  ('creditor_line_number_max_digits', '3', 'Junk filter: max digits for line-number false positives')
on conflict (config_key) do nothing;

create or replace function public.au_group_is_junk_creditor_name(p_name text)
returns boolean
language plpgsql
stable
strict
set search_path = public
as $$
declare
  v_display_name text;
  v_name text;
  v_min_length integer;
  v_max_line_digits integer;
begin
  v_min_length := coalesce(
    nullif(trim(public.au_group_get_runtime_config('creditor_name_min_length')), '')::integer,
    3
  );
  v_max_line_digits := coalesce(
    nullif(trim(public.au_group_get_runtime_config('creditor_line_number_max_digits')), '')::integer,
    3
  );
  v_display_name := trim(p_name);
  if v_display_name = '' then
    return true;
  end if;

  v_name := lower(v_display_name);

  if length(v_display_name) < v_min_length then
    return true;
  end if;

  if v_name in (
    'contact', 'contacts', 'name', 'address', 'amount', 'claim',
    'creditor', 'creditors', 'total'
  ) then
    return true;
  end if;

  if v_display_name ~* '^(list of creditors|creditor matrix|creditors holding|official form 204|20 largest unsecured|name of creditor|creditor\s*name)' then
    return true;
  end if;

  if v_display_name ~* '(mailing address|email address|name of creditor|including zip|zip code|nature of claim|account number|official form|form\s*204|list of creditors|creditor matrix|claim amount)' then
    return true;
  end if;

  if v_display_name ~ ('^\d{1,' || v_max_line_digits || '}$') then
    return true;
  end if;

  return false;
end;
$$;

comment on function public.au_group_is_junk_creditor_name is
  'Form 204 label / line-number junk filter — used by merge + SYS-04 read RPCs';

grant execute on function public.au_group_is_junk_creditor_name (text) to service_role;

-- merge: delegate junk check to shared function
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

create or replace function public.au_group_list_company_creditors(p_bankruptcy_id uuid)
returns table (
  creditor_id uuid,
  creditor_name text,
  creditor_address text,
  claim_amount numeric,
  creditor_state char(2)
)
language sql
stable
security definer
set search_path = public
as $$
  select
    c.id,
    c.name,
    c.address,
    c.claim_amount,
    public.au_group_parse_creditor_state(c.address, b.state)
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  inner join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name);
$$;

comment on function public.au_group_list_company_creditors is
  'SYS-04: company creditors with creditor_state; junk filter via au_group_is_junk_creditor_name';

grant execute on function public.au_group_list_company_creditors(uuid) to service_role;

create or replace function public.au_group_count_company_creditors(p_bankruptcy_id uuid)
returns bigint
language sql
stable
security definer
set search_path = public
as $$
  select count(*)::bigint
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name);
$$;

grant execute on function public.au_group_count_company_creditors(uuid) to service_role;
