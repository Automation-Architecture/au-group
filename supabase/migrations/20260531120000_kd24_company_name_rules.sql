-- KD-24 / FR-4.5: Configurable company name normalization (NFR-7.1).
-- Runs after 20260531100000_kd20_zoominfo_company_lookup.sql.

create table if not exists public.au_group_company_name_rules (
  id uuid primary key default gen_random_uuid(),
  rule_type text not null check (rule_type in ('suffix_strip', 'alias', 'token_replace')),
  pattern text not null,
  replacement text not null default '',
  priority integer not null default 100,
  enabled boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_au_group_company_name_rules_priority
  on public.au_group_company_name_rules (enabled, priority, id);

drop trigger if exists au_group_company_name_rules_set_updated_at
  on public.au_group_company_name_rules;
create trigger au_group_company_name_rules_set_updated_at
  before update on public.au_group_company_name_rules
  for each row execute function public.set_updated_at();

alter table public.au_group_company_name_rules enable row level security;

comment on table public.au_group_company_name_rules is
  'KD-24: editable normalization rules (suffix strip, alias, token replace) without code deploy.';

insert into public.au_group_company_name_rules (
  rule_type, pattern, replacement, priority, enabled, notes
)
select
  'suffix_strip',
  '\s+(incorporated|inc|corp|corporation|llc|l\.l\.c\.|ltd|limited|co|company)\.?\s*$',
  '',
  10,
  true,
  'KD-24 seed: strip trailing legal entity suffixes'
where not exists (
  select 1
  from public.au_group_company_name_rules r
  where r.rule_type = 'suffix_strip' and r.priority = 10
);

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
  v := coalesce(trim(p_name), '');
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

comment on function public.au_group_normalize_company_name is
  'KD-24: normalize company names using au_group_company_name_rules; used for cache keys and creditors.normalized_name.';

grant execute on function public.au_group_normalize_company_name (text) to service_role;
revoke execute on function public.au_group_normalize_company_name (text) from public;

-- Depends on au_group_company_name_rules via normalize; must not be IMMUTABLE (planner constant-folding).
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

create or replace function public.au_group_company_lookup_prepare(
  p_name text,
  p_address text default null
)
returns jsonb
language sql
stable
security definer
set search_path = public
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

comment on function public.au_group_company_lookup_prepare is
  'KD-24/SYS-03: normalized_name + cache_key from DB rules (no duplicate n8n regex).';

grant execute on function public.au_group_company_lookup_prepare (text, text) to service_role;
revoke execute on function public.au_group_company_lookup_prepare (text, text) from public;

update public.creditors c
set normalized_name = public.au_group_normalize_company_name(c.name)
where c.normalized_name is null
  and c.name is not null
  and trim(c.name) <> '';
