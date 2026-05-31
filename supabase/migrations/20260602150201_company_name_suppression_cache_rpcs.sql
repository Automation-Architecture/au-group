-- Recovery migration: applied to live DB out-of-repo on 2026-06-02.
-- Captures helper RPCs that depend on tables introduced in 20260602150100:
--   au_group_schedule_f_keyword_hit, au_group_is_suppressed_creditor_name,
--   au_group_normalize_company_name, au_group_company_lookup_cache_key,
--   au_group_company_lookup_prepare, au_group_get_zoominfo_company_cache,
--   au_group_config_bool, au_group_build_lookup_context,
--   au_group_active_target_states, au_group_resolve_court_and_target_state,
--   au_group_classify_company_tier, au_group_list_contact_titles,
--   au_group_list_tier_contact_titles, au_group_set_creditor_company_tier.
--
-- All functions use CREATE OR REPLACE — safe to replay.

-- ---------------------------------------------------------------------------
-- 1. au_group_schedule_f_keyword_hit
-- ---------------------------------------------------------------------------
create or replace function public.au_group_schedule_f_keyword_hit(p_text text)
returns boolean
language sql
stable security definer
set search_path to public
as $$
  select exists (
    select 1
    from public.au_group_schedule_f_keywords k
    where k.active is true
      and coalesce(trim(p_text), '') ilike '%' || k.pattern || '%'
  );
$$;

grant execute on function public.au_group_schedule_f_keyword_hit(text)
  to service_role;
revoke execute on function public.au_group_schedule_f_keyword_hit(text)
  from public;

-- ---------------------------------------------------------------------------
-- 2. au_group_is_suppressed_creditor_name
-- ---------------------------------------------------------------------------
create or replace function public.au_group_is_suppressed_creditor_name(p_name text)
returns boolean
language sql
stable security definer
set search_path to public
as $$
  select exists (
    select 1
    from public.au_group_suppression_lenders l
    where l.active is true
      and coalesce(trim(p_name), '') ilike '%' || l.pattern || '%'
  )
  or exists (
    select 1
    from public.au_group_suppression_keywords k
    where k.active is true
      and coalesce(trim(p_name), '') ilike '%' || k.pattern || '%'
  );
$$;

grant execute on function public.au_group_is_suppressed_creditor_name(text)
  to service_role;
revoke execute on function public.au_group_is_suppressed_creditor_name(text)
  from public;

-- ---------------------------------------------------------------------------
-- 3. au_group_normalize_company_name
--    Applies au_group_company_name_rules in priority order.
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_company_name(p_name text)
returns text
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v text;
  r record;
begin
  v := left(coalesce(trim(p_name), ''), 500);
  if v = '' then
    return '';
  end if;
  for r in
    select rule_type, pattern, replacement
    from public.au_group_company_name_rules
    where enabled = true
    order by priority asc, id asc
  loop
    if r.rule_type = 'suffix_strip' then
      v := regexp_replace(v, r.pattern, coalesce(r.replacement, ''), 'gi');
    elsif r.rule_type = 'alias' then
      if upper(v) = upper(r.pattern) then
        v := coalesce(nullif(trim(r.replacement), ''), v);
      end if;
    elsif r.rule_type = 'token_replace' then
      v := regexp_replace(v, r.pattern, coalesce(r.replacement, ''), 'gi');
    end if;
  end loop;
  v := upper(regexp_replace(v, '[^\w\s]', ' ', 'g'));
  v := trim(regexp_replace(v, '\s+', ' ', 'g'));
  return v;
end;
$$;

grant execute on function public.au_group_normalize_company_name(text)
  to service_role;
revoke execute on function public.au_group_normalize_company_name(text)
  from public;

-- ---------------------------------------------------------------------------
-- 4. au_group_company_lookup_cache_key (depends on normalize_company_name)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_company_lookup_cache_key(
  p_name    text,
  p_address text default null
)
returns text
language sql
stable
set search_path to public
as $$
  select md5(
    coalesce(public.au_group_normalize_company_name(p_name), '')
    || '|'
    || coalesce(
      upper(
        trim(
          regexp_replace(coalesce(p_address, ''), '\s+', ' ', 'g')
        )
      ),
      ''
    )
  );
$$;

grant execute on function public.au_group_company_lookup_cache_key(text, text)
  to service_role;
revoke execute on function public.au_group_company_lookup_cache_key(text, text)
  from public;

-- ---------------------------------------------------------------------------
-- 5. au_group_company_lookup_prepare (depends on normalize_company_name + cache_key)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_company_lookup_prepare(
  p_name    text,
  p_address text default null
)
returns jsonb
language sql
stable security definer
set search_path to public
as $$
  select jsonb_build_object(
    'normalized_name', public.au_group_normalize_company_name(p_name),
    'cache_key', public.au_group_company_lookup_cache_key(p_name, p_address),
    'lookup_name', coalesce(trim(p_name), ''),
    'lookup_address', p_address,
    'addr_norm', upper(
      trim(regexp_replace(coalesce(p_address, ''), '\s+', ' ', 'g'))
    )
  );
$$;

grant execute on function public.au_group_company_lookup_prepare(text, text)
  to service_role;
revoke execute on function public.au_group_company_lookup_prepare(text, text)
  from public;

-- ---------------------------------------------------------------------------
-- 6. au_group_get_zoominfo_company_cache (depends on zoominfo_company_cache table)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_get_zoominfo_company_cache(p_cache_key text)
returns table(
  cache_key        text,
  company_id       text,
  normalized_name  text,
  match_confidence numeric,
  firmographics    jsonb,
  cache_hit        boolean
)
language sql
stable security definer
set search_path to public
as $$
  select c.cache_key, c.company_id, c.normalized_name, c.match_confidence, c.firmographics, true
  from public.au_group_zoominfo_company_cache c
  where c.cache_key = p_cache_key and c.expires_at > now();
$$;

grant execute on function public.au_group_get_zoominfo_company_cache(text)
  to service_role;
revoke execute on function public.au_group_get_zoominfo_company_cache(text)
  from public;

-- ---------------------------------------------------------------------------
-- 7. au_group_config_bool (depends on au_group_runtime_config)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_config_bool(p_key text, p_default boolean)
returns boolean
language sql
stable security definer
set search_path to public
as $$
  select coalesce(
    (
      select case lower(trim(c.config_value))
        when 'true' then true
        when '1'    then true
        when 'yes'  then true
        else false
      end
      from public.au_group_runtime_config c
      where c.config_key = p_key
      limit 1
    ),
    p_default
  );
$$;

grant execute on function public.au_group_config_bool(text, boolean)
  to service_role;
revoke execute on function public.au_group_config_bool(text, boolean)
  from public;

-- ---------------------------------------------------------------------------
-- 8. au_group_build_lookup_context (immutable helper, no table deps)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_build_lookup_context(p_row jsonb, p_ctx jsonb)
returns jsonb
language sql
immutable
as $$
  select coalesce(p_row, '{}'::jsonb)
    || coalesce(p_ctx, '{}'::jsonb)
    || jsonb_build_object(
      'lookup_name', btrim(coalesce(p_row->>'creditor_name', p_row->>'name', '')),
      'lookup_address', coalesce(p_row->>'address', p_row->>'creditor_address'),
      'dry_run', coalesce((p_row->>'dry_run')::boolean, false)
        or coalesce((p_ctx->>'dry_run')::boolean, false)
    );
$$;

grant execute on function public.au_group_build_lookup_context(jsonb, jsonb)
  to service_role;
revoke execute on function public.au_group_build_lookup_context(jsonb, jsonb)
  from public;

-- ---------------------------------------------------------------------------
-- 9. au_group_active_target_states (depends on au_group_target_states table)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_active_target_states(
  p_states text[] default null
)
returns setof char(2)
language sql
stable security definer
set search_path to public
as $$
  select distinct upper(left(trim(s), 2))::char(2)
  from unnest(
    case
      when p_states is not null and coalesce(array_length(p_states, 1), 0) > 0 then
        p_states
      else
        coalesce(
          (select array_agg(t.state::text) from public.au_group_target_states t where t.active),
          array[]::text[]
        )
    end
  ) as u(s)
  where length(trim(s)) >= 2;
$$;

grant execute on function public.au_group_active_target_states(text[])
  to service_role;
revoke execute on function public.au_group_active_target_states(text[])
  from public;

-- ---------------------------------------------------------------------------
-- 10. au_group_resolve_court_and_target_state
-- ---------------------------------------------------------------------------
create or replace function public.au_group_resolve_court_and_target_state(p_court_id text)
returns table(
  bankruptcy_state char(2),
  court_district   character varying,
  is_target_state  boolean,
  skip_reason      text
)
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_court_id varchar;
  v_state    char(2);
  v_district varchar;
  v_active   boolean;
begin
  v_court_id := lower(trim(coalesce(p_court_id, '')));
  if v_court_id = '' then
    return query
    select null::char(2), null::varchar, false, 'missing_court_id'::text;
    return;
  end if;

  select m.state, m.court_district
  into v_state, v_district
  from public.au_group_court_mappings m
  where m.active is true
    and m.court_id = v_court_id;

  if v_state is null then
    return query
    select null::char(2), v_court_id::varchar, false, 'unknown_court'::text;
    return;
  end if;

  select public.au_group_is_target_state(v_state) into v_active;

  return query
  select v_state, v_district, coalesce(v_active, false), null::text;
end;
$$;

grant execute on function public.au_group_resolve_court_and_target_state(text)
  to service_role;
revoke execute on function public.au_group_resolve_court_and_target_state(text)
  from public;

-- ---------------------------------------------------------------------------
-- 11. au_group_classify_company_tier (depends on au_group_company_tiers)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_classify_company_tier(
  p_revenue   numeric,
  p_employees integer
)
returns table(
  tier          smallint,
  tier_name     text,
  min_revenue   numeric,
  min_employees integer,
  matched_on    text
)
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_row record;
begin
  if p_revenue is null and p_employees is null then
    return query
    select t.tier, t.label, t.min_revenue, t.min_employees,
           'default_null_firmographics'::text
    from public.au_group_company_tiers t
    where t.tier = 3 and t.active is true;
    return;
  end if;

  for v_row in
    select t.tier, t.label, t.min_revenue, t.min_employees
    from public.au_group_company_tiers t
    where t.active is true
    order by t.tier asc
  loop
    if (p_revenue    is not null and p_revenue    >= v_row.min_revenue)
    or (p_employees  is not null and p_employees  >= v_row.min_employees)
    then
      return query
      select v_row.tier, v_row.label, v_row.min_revenue, v_row.min_employees,
             case
               when p_revenue   is not null and p_revenue   >= v_row.min_revenue
                and p_employees is not null and p_employees >= v_row.min_employees
               then 'revenue_and_employees'
               when p_revenue is not null and p_revenue >= v_row.min_revenue
               then 'revenue'
               else 'employees'
             end;
      return;
    end if;
  end loop;

  return query
  select t.tier, t.label, t.min_revenue, t.min_employees, 'fallback_smb'::text
  from public.au_group_company_tiers t
  where t.tier = 3 and t.active is true;
end;
$$;

grant execute on function public.au_group_classify_company_tier(numeric, integer)
  to service_role;
revoke execute on function public.au_group_classify_company_tier(numeric, integer)
  from public;

-- ---------------------------------------------------------------------------
-- 12. au_group_list_contact_titles (depends on au_group_tier_contact_titles)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_list_contact_titles(
  p_tier             smallint,
  p_include_fallback boolean default true
)
returns text[]
language sql
stable security definer
set search_path to public
as $$
  select coalesce(
    array_agg(distinct t.title_pattern order by t.title_pattern),
    '{}'::text[]
  )
  from public.au_group_tier_contact_titles t
  where t.active is true
    and (
      t.tier = p_tier
      or (p_include_fallback and t.tier > p_tier)
    );
$$;

grant execute on function public.au_group_list_contact_titles(smallint, boolean)
  to service_role;
revoke execute on function public.au_group_list_contact_titles(smallint, boolean)
  from public;

-- ---------------------------------------------------------------------------
-- 13. au_group_list_tier_contact_titles (depends on au_group_tier_contact_titles)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_list_tier_contact_titles(p_tier integer)
returns table(title text, sort_order integer)
language sql
stable security definer
set search_path to public
as $$
  select t.title_pattern as title, t.sort_order::integer
  from public.au_group_tier_contact_titles t
  where t.tier = p_tier and p_tier between 1 and 3 and t.active is true
  order by t.sort_order asc, t.title_pattern asc;
$$;

grant execute on function public.au_group_list_tier_contact_titles(integer)
  to service_role;
revoke execute on function public.au_group_list_tier_contact_titles(integer)
  from public;

-- ---------------------------------------------------------------------------
-- 14. au_group_set_creditor_company_tier (depends on creditors.company_tier)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_set_creditor_company_tier(
  p_creditor_id   uuid,
  p_tier          smallint,
  p_bankruptcy_id uuid default null
)
returns boolean
language plpgsql
security definer
set search_path to public
as $$
begin
  if p_creditor_id is null then return false; end if;
  if p_tier is null or p_tier < 1 or p_tier > 3 then return false; end if;

  if p_bankruptcy_id is not null then
    update public.creditors c
    set company_tier             = p_tier,
        company_tier_assigned_at = now(),
        updated_at               = now()
    where c.id = p_creditor_id
      and (
        exists (
          select 1 from public.bankruptcy_creditors bc
          where bc.creditor_id = c.id and bc.bankruptcy_id = p_bankruptcy_id
        )
        or c.source_bankruptcy_id = p_bankruptcy_id
      );
    return found;
  end if;

  update public.creditors c
  set company_tier             = p_tier,
      company_tier_assigned_at = now(),
      updated_at               = now()
  where c.id = p_creditor_id;
  return found;
end;
$$;

grant execute on function public.au_group_set_creditor_company_tier(uuid, smallint, uuid)
  to service_role;
revoke execute on function public.au_group_set_creditor_company_tier(uuid, smallint, uuid)
  from public;
