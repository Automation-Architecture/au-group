-- WP-03a: Grouped daily-report RPC (KD-60)
--
-- Adds au_group_daily_creditor_report_grouped — one row per (creditor, bankruptcy)
-- instead of the flat function's DISTINCT ON (c.id), which collapses a creditor
-- that appears in two debtors into one row.  The existing flat function is not
-- modified (backward-compatible).
--
-- Also carries the replay-safe body for au_group_creditor_pipeline_status so
-- this migration is self-contained on a fresh database: the local migration at
-- 20260529140000 predates the queued/running/retrying enrichment-pending check,
-- which exists on the live DB via an out-of-repo migration (PR #40).
--
-- CI replay dependency: creditors.company_tier (PR #40) and processing_job_status
-- (PR #39) must both be present.  Stack this PR on #39 + #40 before merging.

-- ---------------------------------------------------------------------------
-- 1. au_group_creditor_pipeline_status (replay-safe version)
--
-- Re-asserts the body from 20260529160000 so this migration is self-contained
-- when stacked after #39 + #40 but before that migration is replayed in order.
-- On the live DB and on any replay that already ran 20260529160000 this is a
-- no-op replace (CREATE OR REPLACE).
-- ---------------------------------------------------------------------------
create or replace function public.au_group_creditor_pipeline_status(p_creditor_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_sf       text;
  v_enriched text;
  v_pending  text;
  v_failed   text;
  v_new      text;
begin
  v_sf       := public.au_group_config_text('daily_report_status_sf_synced',          'Salesforce Synced');
  v_enriched := public.au_group_config_text('daily_report_status_enriched',           'ZoomInfo Enriched');
  v_pending  := public.au_group_config_text('daily_report_status_pending_enrichment', 'Pending Enrichment');
  v_failed   := public.au_group_config_text('daily_report_status_enrich_failed',      'Enrichment Failed');
  v_new      := public.au_group_config_text('daily_report_status_new',                'New');

  if exists (
    select 1 from public.salesforce_accounts sa where sa.creditor_id = p_creditor_id
  ) then return v_sf; end if;

  if exists (
    select 1 from public.zoom_info_contacts z where z.creditor_id = p_creditor_id
  ) then return v_enriched; end if;

  -- New code-native queue: zoom_info_enrich jobs in queued/running/retrying state.
  if exists (
    select 1 from public.processing_jobs pj
    where pj.job_type::text = 'zoom_info_enrich'
      and pj.status::text   in ('queued', 'running', 'retrying')
      and pj.bankruptcy_id  in (
        select bc.bankruptcy_id from public.bankruptcy_creditors bc
        where bc.creditor_id = p_creditor_id
        union
        select c.source_bankruptcy_id from public.creditors c
        where c.id = p_creditor_id and c.source_bankruptcy_id is not null
      )
  ) then return v_pending; end if;

  if exists (
    select 1 from public.processing_jobs pj
    where pj.job_type::text = 'zoom_info_enrich'
      and pj.status::text   = 'failed'
      and pj.bankruptcy_id  in (
        select bc.bankruptcy_id from public.bankruptcy_creditors bc
        where bc.creditor_id = p_creditor_id
        union
        select c.source_bankruptcy_id from public.creditors c
        where c.id = p_creditor_id and c.source_bankruptcy_id is not null
      )
  ) then return v_failed; end if;

  return v_new;
end;
$$;

revoke execute on function public.au_group_creditor_pipeline_status(uuid) from public;

-- ---------------------------------------------------------------------------
-- 2. au_group_daily_creditor_report_grouped
--
-- Returns one JSON object per (creditor, bankruptcy) pair.  A creditor linked
-- to two debtors yields two rows with distinct debtor_name / case_number.
--
-- Response envelope:
--   { since, debtor_count, creditor_count, rows: [ { debtor_name, case_number,
--     filing_date, creditor, city, state, claim, status, tier, zoominfo_url } ] }
--
-- tier is sourced from creditors.company_tier (smallint 1–3: 1=Enterprise,
-- 2=Mid-Market, 3=SMB; NULL when not yet enriched).
-- Downstream report.py renders NULL tier as an em dash.
-- ---------------------------------------------------------------------------
create or replace function public.au_group_daily_creditor_report_grouped(
  p_since timestamptz default null
)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with v_since as (
    select coalesce(
      p_since,
      now() - (public.au_group_config_int('daily_report_window_hours', 24) || ' hours')::interval
    ) as since
  ),
  -- Union of direct bankruptcy_creditors links and source_bankruptcy_id links.
  creditor_bankruptcy as (
    select c.id as creditor_id, bc.bankruptcy_id
    from public.creditors c
    inner join public.bankruptcy_creditors bc on bc.creditor_id = c.id
    union
    select c.id, c.source_bankruptcy_id
    from public.creditors c
    where c.source_bankruptcy_id is not null
  ),
  row_data as (
    select
      c.id                                                          as creditor_id,
      cb.bankruptcy_id,
      b.debtor_name,
      b.case_number,
      b.filing_date,
      coalesce(nullif(trim(c.original_name), ''), c.name)::text    as creditor,
      public.au_group_parse_creditor_city(c.address)               as city,
      public.au_group_parse_creditor_state(c.address, b.state)     as state,
      case
        when c.claim_amount is null then ''
        else to_char(c.claim_amount, 'FM$999,999,999,990.00')
      end                                                           as claim,
      public.au_group_creditor_pipeline_status(c.id)               as status,
      c.company_tier                                                as tier,
      public.au_group_zoominfo_company_url(c.zoominfo_company_id)  as zoominfo_url
    from public.creditors c
    inner join creditor_bankruptcy cb on cb.creditor_id = c.id
    inner join public.bankruptcies  b  on b.id = cb.bankruptcy_id
    cross join v_since vs
    where c.is_company is true
      and not public.au_group_is_junk_creditor_name(c.name)
      and (c.created_at >= vs.since or b.created_at >= vs.since)
  )
  select jsonb_build_object(
    'since',          (select since          from v_since),
    'debtor_count',   (select count(distinct bankruptcy_id)::int from row_data),
    'creditor_count', (select count(distinct creditor_id)::int   from row_data),
    'rows', coalesce(
      (
        select jsonb_agg(
          jsonb_build_object(
            'debtor_name',  rd.debtor_name,
            'case_number',  rd.case_number,
            'filing_date',  rd.filing_date,
            'creditor',     rd.creditor,
            'city',         rd.city,
            'state',        rd.state,
            'claim',        rd.claim,
            'status',       rd.status,
            'tier',         rd.tier,
            'zoominfo_url', rd.zoominfo_url
          )
          order by rd.debtor_name, rd.creditor
        )
        from row_data rd
      ),
      '[]'::jsonb
    )
  );
$$;

grant execute on function public.au_group_daily_creditor_report_grouped(timestamptz)
  to service_role;
revoke execute on function public.au_group_daily_creditor_report_grouped(timestamptz)
  from public;

comment on function public.au_group_daily_creditor_report_grouped is
  'KD-60/WP-03a: one row per (creditor, bankruptcy) for the daily Slack report, grouped by debtor.';
