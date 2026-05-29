-- KD-24 follow-up: cache_key was IMMUTABLE in KD-20 but normalize became STABLE/table-driven in KD-24.

create or replace function public.au_group_company_lookup_cache_key(
  p_name text,
  p_address text default null
)
returns text
language sql
stable
set search_path = public
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

comment on function public.au_group_company_lookup_cache_key is
  'KD-20/KD-24: md5(normalized_name|address). STABLE: cache keys change when au_group_company_name_rules are edited.';

grant execute on function public.au_group_company_lookup_cache_key (text, text) to service_role;
revoke execute on function public.au_group_company_lookup_cache_key (text, text) from public;
