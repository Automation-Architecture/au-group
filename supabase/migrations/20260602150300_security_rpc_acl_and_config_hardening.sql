-- Security hardening: CRITICAL upsert RPC ACL, KD-24 ACL re-assert, config RLS deny, regex limits.

-- ---------------------------------------------------------------------------
-- CRITICAL: upsert_document_parse_result must be service_role only (not anon/authenticated).
-- ---------------------------------------------------------------------------
revoke execute on function public.au_group_upsert_document_parse_result (
  uuid,
  uuid,
  integer,
  text,
  text,
  boolean,
  text,
  text,
  text,
  jsonb,
  text
) from public, anon, authenticated;

grant execute on function public.au_group_upsert_document_parse_result (
  uuid,
  uuid,
  integer,
  text,
  text,
  boolean,
  text,
  text,
  text,
  jsonb,
  text
) to service_role;

-- ---------------------------------------------------------------------------
-- KD-24 / KD-20: re-assert ACL after CREATE OR REPLACE on volatility migration.
-- ---------------------------------------------------------------------------
grant execute on function public.au_group_normalize_company_name (text) to service_role;
revoke execute on function public.au_group_normalize_company_name (text) from public;

grant execute on function public.au_group_company_lookup_cache_key (text, text) to service_role;
revoke execute on function public.au_group_company_lookup_cache_key (text, text) from public;

grant execute on function public.au_group_company_lookup_prepare (text, text) to service_role;
revoke execute on function public.au_group_company_lookup_prepare (text, text) from public;

-- ---------------------------------------------------------------------------
-- Config helpers (may have been granted before inline revokes existed).
-- ---------------------------------------------------------------------------
grant execute on function public.au_group_config_text (text, text) to service_role;
revoke execute on function public.au_group_config_text (text, text) from public;

grant execute on function public.au_group_config_int (text, integer) to service_role;
revoke execute on function public.au_group_config_int (text, integer) from public;

grant execute on function public.au_group_get_zoominfo_company_cache (text) to service_role;
revoke execute on function public.au_group_get_zoominfo_company_cache (text) from public;

grant execute on function public.au_group_upsert_zoominfo_company_cache (
  text, text, text, numeric, jsonb, jsonb, integer
) to service_role;
revoke execute on function public.au_group_upsert_zoominfo_company_cache (
  text, text, text, numeric, jsonb, jsonb, integer
) from public;

-- ---------------------------------------------------------------------------
-- RLS: explicit deny for anon/authenticated on Keith-editable config tables.
-- ---------------------------------------------------------------------------
drop policy if exists au_group_runtime_config_deny_public on public.au_group_runtime_config;
create policy au_group_runtime_config_deny_public
  on public.au_group_runtime_config
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists au_group_company_name_rules_deny_public on public.au_group_company_name_rules;
create policy au_group_company_name_rules_deny_public
  on public.au_group_company_name_rules
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists au_group_schedule_f_keywords_deny_public on public.au_group_schedule_f_keywords;
create policy au_group_schedule_f_keywords_deny_public
  on public.au_group_schedule_f_keywords
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists au_group_court_mappings_deny_public on public.au_group_court_mappings;
create policy au_group_court_mappings_deny_public
  on public.au_group_court_mappings
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

-- ---------------------------------------------------------------------------
-- KD-24: cap rule pattern length and input size (ReDoS mitigation).
-- ---------------------------------------------------------------------------
alter table public.au_group_company_name_rules
  drop constraint if exists au_group_company_name_rules_pattern_len;

alter table public.au_group_company_name_rules
  add constraint au_group_company_name_rules_pattern_len
  check (char_length(pattern) <= 200);

create or replace function public.au_group_normalize_company_name(p_name text)
returns text
language plpgsql
stable
security definer
set search_path = public
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

grant execute on function public.au_group_normalize_company_name (text) to service_role;
revoke execute on function public.au_group_normalize_company_name (text) from public;
