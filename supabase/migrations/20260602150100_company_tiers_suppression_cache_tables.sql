-- Recovery migration: applied to live DB out-of-repo on 2026-06-02.
-- Captures: au_group_company_tiers, au_group_company_name_rules, au_group_schedule_f_keywords,
-- au_group_suppression_keywords, au_group_suppression_lenders, au_group_zoominfo_company_cache,
-- au_group_enrich_loop_staging, au_group_tier_contact_titles tables, their indexes/triggers,
-- and the active_monitored_cases view.
--
-- All DDL is idempotent — safe to replay on fresh databases.

-- ---------------------------------------------------------------------------
-- 1. au_group_company_tiers  (reference table for tier classification)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_company_tiers (
  tier         smallint primary key,
  label        text not null,
  min_revenue  numeric,
  min_employees integer,
  active       boolean not null default true,
  notes        text,
  updated_at   timestamptz not null default now(),
  constraint au_group_company_tiers_tier_check check (tier >= 1 and tier <= 3)
);

create or replace trigger au_group_company_tiers_set_updated_at
  before update on public.au_group_company_tiers
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 2. au_group_company_name_rules  (normalization rules driving normalize_company_name)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_company_name_rules (
  id          uuid primary key default gen_random_uuid(),
  rule_type   text not null,
  pattern     text not null,
  replacement text not null default '',
  priority    integer not null default 100,
  enabled     boolean not null default true,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint au_group_company_name_rules_rule_type_check
    check (rule_type = any (array['suffix_strip'::text, 'alias'::text, 'token_replace'::text])),
  constraint au_group_company_name_rules_pattern_len
    check (char_length(pattern) <= 200)
);

create index if not exists idx_au_group_company_name_rules_priority
  on public.au_group_company_name_rules (enabled, priority, id);

create or replace trigger au_group_company_name_rules_set_updated_at
  before update on public.au_group_company_name_rules
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 3. au_group_schedule_f_keywords  (keyword patterns used by schedule_f_keyword_hit)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_schedule_f_keywords (
  id         bigserial primary key,
  pattern    text not null,
  active     boolean not null default true,
  notes      text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 4. au_group_suppression_keywords  (keyword-based creditor suppression)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_suppression_keywords (
  id         bigserial primary key,
  pattern    text not null,
  active     boolean not null default true,
  notes      text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 5. au_group_suppression_lenders  (lender-name-based creditor suppression)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_suppression_lenders (
  id         bigserial primary key,
  pattern    text not null,
  active     boolean not null default true,
  notes      text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 6. au_group_zoominfo_company_cache  (TTL cache for ZoomInfo company lookups)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_zoominfo_company_cache (
  cache_key         text primary key,
  company_id        text not null,
  normalized_name   text,
  match_confidence  numeric,
  firmographics     jsonb not null default '{}'::jsonb,
  raw_response      jsonb,
  expires_at        timestamptz not null,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_au_group_zoominfo_company_cache_expires
  on public.au_group_zoominfo_company_cache (expires_at);

create or replace trigger au_group_zoominfo_company_cache_set_updated_at
  before update on public.au_group_zoominfo_company_cache
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 7. au_group_enrich_loop_staging  (per-job creditor enrichment accumulator)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_enrich_loop_staging (
  job_id      uuid not null,
  creditor_id uuid not null,
  result      jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (job_id, creditor_id)
);

create index if not exists idx_au_group_enrich_loop_staging_job
  on public.au_group_enrich_loop_staging (job_id);

-- ---------------------------------------------------------------------------
-- 8. au_group_tier_contact_titles  (per-tier ZoomInfo contact title patterns)
-- ---------------------------------------------------------------------------
create table if not exists public.au_group_tier_contact_titles (
  id            bigserial primary key,
  tier          smallint not null references public.au_group_company_tiers (tier) on delete cascade,
  title_pattern text not null,
  sort_order    smallint not null default 0,
  active        boolean not null default true,
  created_at    timestamptz not null default now(),
  constraint idx_au_group_tier_contact_titles_tier_pattern unique (tier, title_pattern)
);

create index if not exists idx_au_group_tier_contact_titles_tier
  on public.au_group_tier_contact_titles (tier, sort_order)
  where active is true;

-- The live DB has two indexes with overlapping names — capture both.
create unique index if not exists uq_au_group_tier_contact_titles_tier_title
  on public.au_group_tier_contact_titles (tier, title_pattern);

-- ---------------------------------------------------------------------------
-- 9. active_monitored_cases view
-- ---------------------------------------------------------------------------
create or replace view public.active_monitored_cases as
  select
    id,
    case_number,
    debtor_name,
    court_id,
    chapter_type,
    filing_date,
    monitoring_enabled,
    lead_score,
    lead_priority
  from public.bankruptcies
  where monitoring_enabled = true;
