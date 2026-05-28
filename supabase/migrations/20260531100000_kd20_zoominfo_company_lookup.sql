-- KD-20 / FR-4.1: ZoomInfo company lookup cache + match metadata on creditors.

-- ---------------------------------------------------------------------------
-- Normalize company name for lookup/cache keys (KD-24 expands rules later).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_company_name(p_name text)
returns text
language sql
immutable
as $$
  select trim(
    regexp_replace(
      regexp_replace(
        upper(
          regexp_replace(
            coalesce(trim(p_name), ''),
            '\s+(incorporated|inc|corp|corporation|llc|l\.l\.c\.|ltd|limited|co|company)\.?\s*$',
            '',
            'gi'
          )
        ),
        '[^\w\s]',
        ' ',
        'g'
      ),
      '\s+',
      ' ',
      'g'
    )
  );
$$;

comment on function public.au_group_normalize_company_name is
  'KD-20/KD-24: strip suffixes and punctuation for ZoomInfo lookup cache keys.';

-- ---------------------------------------------------------------------------
-- Creditor-level ZoomInfo company match fields (distinct from parser confidence_score).
-- ---------------------------------------------------------------------------
alter table public.creditors
  add column if not exists zoominfo_match_confidence numeric(5, 4),
  add column if not exists zoominfo_match_status text,
  add column if not exists zoominfo_firmographics jsonb,
  add column if not exists zoominfo_enriched_at timestamptz;

comment on column public.creditors.zoominfo_match_confidence is
  'ZoomInfo company-match confidence (0–1); not parser/OCR confidence_score.';
comment on column public.creditors.zoominfo_match_status is
  'matched | no_match | ambiguous | error | rate_limited | cached | dry_run';
comment on column public.creditors.zoominfo_firmographics is
  'Firmographics from ZoomInfo: revenue, employee_count, industry, headquarters.';
comment on column public.creditors.zoominfo_enriched_at is
  'When ZoomInfo company lookup last succeeded or was served from cache.';

-- ---------------------------------------------------------------------------
-- Cross-filing company lookup cache (NFR-8.2; 7-day TTL default).
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_zoominfo_company_cache (
  cache_key text primary key,
  company_id text not null,
  normalized_name text,
  match_confidence numeric(5, 4),
  firmographics jsonb not null default '{}'::jsonb,
  raw_response jsonb,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_au_group_zoominfo_company_cache_expires
  on public.au_group_zoominfo_company_cache (expires_at);

drop trigger if exists au_group_zoominfo_company_cache_set_updated_at
  on public.au_group_zoominfo_company_cache;
create trigger au_group_zoominfo_company_cache_set_updated_at
  before update on public.au_group_zoominfo_company_cache
  for each row execute function public.set_updated_at();

alter table public.au_group_zoominfo_company_cache enable row level security;

comment on table public.au_group_zoominfo_company_cache is
  'KD-20: ZoomInfo company lookup cache keyed by normalized name+address hash.';

-- ---------------------------------------------------------------------------
-- Cache key = md5(normalized_name | normalized_address fragment)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_company_lookup_cache_key(
  p_name text,
  p_address text default null
)
returns text
language sql
immutable
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

grant execute on function public.au_group_company_lookup_cache_key (text, text) to service_role;
revoke execute on function public.au_group_company_lookup_cache_key (text, text) from public;

-- ---------------------------------------------------------------------------
-- Cache read (miss returns zero rows).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_get_zoominfo_company_cache(p_cache_key text)
returns table (
  cache_key text,
  company_id text,
  normalized_name text,
  match_confidence numeric,
  firmographics jsonb,
  cache_hit boolean
)
language sql
stable
security definer
set search_path = public
as $$
  select
    c.cache_key,
    c.company_id,
    c.normalized_name,
    c.match_confidence,
    c.firmographics,
    true as cache_hit
  from public.au_group_zoominfo_company_cache c
  where c.cache_key = p_cache_key
    and c.expires_at > now();
$$;

comment on function public.au_group_get_zoominfo_company_cache is
  'KD-20: return cached ZoomInfo company row when not expired; empty set on miss.';

grant execute on function public.au_group_get_zoominfo_company_cache (text) to service_role;
revoke execute on function public.au_group_get_zoominfo_company_cache (text) from public;

-- ---------------------------------------------------------------------------
-- Cache write / refresh TTL.
-- ---------------------------------------------------------------------------
create or replace function public.au_group_upsert_zoominfo_company_cache(
  p_cache_key text,
  p_company_id text,
  p_normalized_name text default null,
  p_match_confidence numeric default null,
  p_firmographics jsonb default '{}'::jsonb,
  p_raw_response jsonb default null,
  p_ttl_days integer default 7
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_cache_key is null or trim(p_cache_key) = '' then
    return false;
  end if;
  if p_company_id is null or trim(p_company_id) = '' then
    return false;
  end if;

  insert into public.au_group_zoominfo_company_cache (
    cache_key,
    company_id,
    normalized_name,
    match_confidence,
    firmographics,
    raw_response,
    expires_at
  )
  values (
    trim(p_cache_key),
    trim(p_company_id),
    nullif(trim(p_normalized_name), ''),
    p_match_confidence,
    coalesce(p_firmographics, '{}'::jsonb),
    p_raw_response,
    now() + make_interval(days => greatest(coalesce(p_ttl_days, 7), 1))
  )
  on conflict (cache_key) do update set
    company_id = excluded.company_id,
    normalized_name = excluded.normalized_name,
    match_confidence = excluded.match_confidence,
    firmographics = excluded.firmographics,
    raw_response = excluded.raw_response,
    expires_at = excluded.expires_at,
    updated_at = now();

  return true;
end;
$$;

comment on function public.au_group_upsert_zoominfo_company_cache is
  'KD-20: store ZoomInfo company lookup result for cross-filing reuse.';

grant execute on function public.au_group_upsert_zoominfo_company_cache (
  text, text, text, numeric, jsonb, jsonb, integer
) to service_role;
revoke execute on function public.au_group_upsert_zoominfo_company_cache (
  text, text, text, numeric, jsonb, jsonb, integer
) from public;

-- ---------------------------------------------------------------------------
-- Persist company match on creditor (extends KD-20 set_zoominfo_company_id).
-- ---------------------------------------------------------------------------
drop function if exists public.au_group_set_creditor_zoominfo_company_id(uuid, text);

create or replace function public.au_group_set_creditor_zoominfo_company_id(
  p_creditor_id uuid,
  p_company_id text,
  p_match_confidence numeric default null,
  p_normalized_name text default null,
  p_match_status text default 'matched',
  p_firmographics jsonb default null
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_creditor_id is null then
    return false;
  end if;

  update public.creditors c
  set
    zoominfo_company_id = case
      when p_company_id is null or trim(p_company_id) = '' then c.zoominfo_company_id
      else trim(p_company_id)
    end,
    normalized_name = coalesce(nullif(trim(p_normalized_name), ''), c.normalized_name),
    zoominfo_match_confidence = coalesce(p_match_confidence, c.zoominfo_match_confidence),
    zoominfo_match_status = coalesce(nullif(trim(p_match_status), ''), c.zoominfo_match_status),
    zoominfo_firmographics = coalesce(p_firmographics, c.zoominfo_firmographics),
    zoominfo_enriched_at = case
      when p_match_status in ('matched', 'cached', 'dry_run') then now()
      else c.zoominfo_enriched_at
    end,
    updated_at = now()
  where c.id = p_creditor_id;

  return found;
end;
$$;

comment on function public.au_group_set_creditor_zoominfo_company_id is
  'KD-20/SYS-03: persist ZoomInfo company id, match metadata, and firmographics on creditors.';

grant execute on function public.au_group_set_creditor_zoominfo_company_id (
  uuid, text, numeric, text, text, jsonb
) to service_role;
revoke execute on function public.au_group_set_creditor_zoominfo_company_id (
  uuid, text, numeric, text, text, jsonb
) from public;
