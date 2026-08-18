


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


-- KD-74: extensions live in the `extensions` schema on the live DB; a `--schema public`
-- dump omits them, so the public objects that reference them (e.g. the gin_trgm_ops index
-- on creditors.name) fail to replay. Re-create them here (idempotent). supabase_vault is
-- platform-managed and intentionally excluded.
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE TYPE "public"."au_group_chapter_type" AS ENUM (
    '11',
    '7',
    '11-Subchapter-V'
);


ALTER TYPE "public"."au_group_chapter_type" OWNER TO "postgres";


CREATE TYPE "public"."au_group_filing_type" AS ENUM (
    'FORM_201',
    'CREDITOR_MATRIX',
    'SCHEDULE',
    'SOFA',
    'UNKNOWN'
);


ALTER TYPE "public"."au_group_filing_type" OWNER TO "postgres";


CREATE TYPE "public"."au_group_job_status" AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'manual_review_required'
);


ALTER TYPE "public"."au_group_job_status" OWNER TO "postgres";


CREATE TYPE "public"."au_group_job_type" AS ENUM (
    'pacer_poll',
    'document_parse',
    'zoom_info_enrich',
    'salesforce_push',
    'document_intelligence'
);


ALTER TYPE "public"."au_group_job_type" OWNER TO "postgres";


CREATE TYPE "public"."au_group_parse_mode" AS ENUM (
    'structured',
    'ocr'
);


ALTER TYPE "public"."au_group_parse_mode" OWNER TO "postgres";


CREATE TYPE "public"."au_group_review_status" AS ENUM (
    'pending',
    'in_review',
    'resolved',
    'rejected'
);


ALTER TYPE "public"."au_group_review_status" OWNER TO "postgres";


CREATE TYPE "public"."au_group_schedule_f_status" AS ENUM (
    'monitoring',
    'detected',
    'pending_approval',
    'approved',
    'rejected',
    'processed'
);


ALTER TYPE "public"."au_group_schedule_f_status" OWNER TO "postgres";


CREATE TYPE "public"."bankruptcy_chapter" AS ENUM (
    '7',
    '11',
    '13',
    '15'
);


ALTER TYPE "public"."bankruptcy_chapter" OWNER TO "postgres";


CREATE TYPE "public"."processing_job_status" AS ENUM (
    'queued',
    'running',
    'completed',
    'failed',
    'retrying'
);


ALTER TYPE "public"."processing_job_status" OWNER TO "postgres";


CREATE TYPE "public"."schedule_f_status" AS ENUM (
    'pending',
    'monitoring',
    'detected',
    'downloaded',
    'parsed',
    'failed'
);


ALTER TYPE "public"."schedule_f_status" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_acquire_processing_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type", "p_stale_interval" interval DEFAULT '24:00:00'::interval) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_existing uuid;
  v_job_id uuid;
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  update public.processing_jobs
  set
    status = 'failed',
    error_message = coalesce(error_message, 'stale job auto-failed before acquire'),
    completed_at = now()
  where bankruptcy_id = p_bankruptcy_id
    and job_type = p_job_type
    and status = 'running'
    and coalesce(started_at, created_at) < now() - p_stale_interval;

  begin
    insert into public.processing_jobs (job_type, status, bankruptcy_id, started_at)
    values (p_job_type, 'running', p_bankruptcy_id, now())
    returning id into v_job_id;

    return jsonb_build_object(
      'acquired', true,
      'job_id', v_job_id,
      'reason', null
    );
  exception
    when unique_violation then
      select id
      into v_existing
      from public.processing_jobs
      where bankruptcy_id = p_bankruptcy_id
        and job_type = p_job_type
        and status = 'running'
      order by created_at desc
      limit 1;

      return jsonb_build_object(
        'acquired', false,
        'job_id', v_existing,
        'reason', 'job_already_running'
      );
  end;
end;
$$;


ALTER FUNCTION "public"."au_group_acquire_processing_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type", "p_stale_interval" interval) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_active_target_states"("p_states" "text"[] DEFAULT NULL::"text"[]) RETURNS SETOF character
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_active_target_states"("p_states" "text"[]) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_audit_config_change"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  insert into public.au_group_config_audit (config_table, action, row_key, old_data, new_data)
  values (
    tg_table_name,
    tg_op,
    coalesce(new.state, old.state)::text,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end
  );
  return coalesce(new, old);
end;
$$;


ALTER FUNCTION "public"."au_group_audit_config_change"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_build_lookup_context"("p_row" "jsonb", "p_ctx" "jsonb") RETURNS "jsonb"
    LANGUAGE "sql" IMMUTABLE
    AS $$
  select coalesce(p_row, '{}'::jsonb)
    || coalesce(p_ctx, '{}'::jsonb)
    || jsonb_build_object(
      'lookup_name', btrim(coalesce(p_row->>'creditor_name', p_row->>'name', '')),
      'lookup_address', coalesce(p_row->>'address', p_row->>'creditor_address'),
      'dry_run', coalesce((p_row->>'dry_run')::boolean, false)
        or coalesce((p_ctx->>'dry_run')::boolean, false)
    );
$$;


ALTER FUNCTION "public"."au_group_build_lookup_context"("p_row" "jsonb", "p_ctx" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_check_repeat_exposure"("p_creditor_id" "uuid", "p_threshold" integer DEFAULT 4, "p_window_months" integer DEFAULT 18) RETURNS TABLE("is_repeat" boolean, "filing_count" integer, "total_claim_amount" numeric, "suggested_message" "text")
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $_$
declare
  v_count integer;
  v_total numeric(15, 2);
  v_cutoff date;
begin
  v_cutoff := (current_date - (p_window_months || ' months')::interval)::date;
  select count(*)::integer, coalesce(sum(c.claim_amount), 0)
  into v_count, v_total
  from public.bankruptcy_creditors bc
  join public.creditors c on c.id = bc.creditor_id
  join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.creditor_id = p_creditor_id and b.filing_date >= v_cutoff;
  return query select v_count >= p_threshold, v_count, v_total,
    format('Repeat exposure: %s filings since %s totaling $%s — use alternate messaging', v_count, v_cutoff, to_char(v_total, 'FM999,999,999.00'));
end;
$_$;


ALTER FUNCTION "public"."au_group_check_repeat_exposure"("p_creditor_id" "uuid", "p_threshold" integer, "p_window_months" integer) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."processing_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "job_type" "public"."au_group_job_type" NOT NULL,
    "status" "public"."processing_job_status" NOT NULL,
    "bankruptcy_id" "uuid",
    "retry_count" integer DEFAULT 0 NOT NULL,
    "error_message" "text",
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "worker_name" "text",
    "job_payload" "jsonb"
);


ALTER TABLE "public"."processing_jobs" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") RETURNS "public"."processing_jobs"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_job     public.processing_jobs;
  v_id      uuid;
  v_skipped uuid[] := '{}';
begin
  loop
    select id
    into   v_id
    from   public.processing_jobs
    where  status   = 'queued'::processing_job_status
      and  job_type = p_job_type
      and  id != all(v_skipped)
    order  by created_at
    limit  1
    for    update skip locked;

    if v_id is null then
      return null;
    end if;

    begin
      update public.processing_jobs
      set    status     = 'running'::processing_job_status,
             started_at = now()
      where  id = v_id
      returning * into v_job;

      return v_job;
    exception
      when unique_violation then
        v_skipped := array_append(v_skipped, v_id);
    end;
  end loop;
end;
$$;


ALTER FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_classify_company_tier"("p_revenue" numeric, "p_employees" integer) RETURNS TABLE("tier" smallint, "tier_name" "text", "min_revenue" numeric, "min_employees" integer, "matched_on" "text")
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$ declare v_row record; begin if p_revenue is null and p_employees is null then return query select t.tier, t.label, t.min_revenue, t.min_employees, 'default_null_firmographics'::text from public.au_group_company_tiers t where t.tier = 3 and t.active is true; return; end if; for v_row in select t.tier, t.label, t.min_revenue, t.min_employees from public.au_group_company_tiers t where t.active is true order by t.tier asc loop if (p_revenue is not null and p_revenue >= v_row.min_revenue) or (p_employees is not null and p_employees >= v_row.min_employees) then return query select v_row.tier, v_row.label, v_row.min_revenue, v_row.min_employees, case when p_revenue is not null and p_revenue >= v_row.min_revenue and p_employees is not null and p_employees >= v_row.min_employees then 'revenue_and_employees' when p_revenue is not null and p_revenue >= v_row.min_revenue then 'revenue' else 'employees' end; return; end if; end loop; return query select t.tier, t.label, t.min_revenue, t.min_employees, 'fallback_smb'::text from public.au_group_company_tiers t where t.tier = 3 and t.active is true; end; $$;


ALTER FUNCTION "public"."au_group_classify_company_tier"("p_revenue" numeric, "p_employees" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_company_lookup_cache_key"("p_name" "text", "p_address" "text" DEFAULT NULL::"text") RETURNS "text"
    LANGUAGE "sql" STABLE
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_company_lookup_cache_key"("p_name" "text", "p_address" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_company_lookup_cache_key"("p_name" "text", "p_address" "text") IS 'KD-20/KD-24: md5(normalized_name|address). STABLE: cache keys change when au_group_company_name_rules are edited.';



CREATE OR REPLACE FUNCTION "public"."au_group_company_lookup_prepare"("p_name" "text", "p_address" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_company_lookup_prepare"("p_name" "text", "p_address" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_company_lookup_prepare"("p_name" "text", "p_address" "text") IS 'KD-24/SYS-03: normalized_name + cache_key from DB rules (no duplicate n8n regex).';



CREATE OR REPLACE FUNCTION "public"."au_group_config_bool"("p_key" "text", "p_default" boolean) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select coalesce(
    (
      select case lower(trim(c.config_value))
        when 'true' then true
        when '1' then true
        when 'yes' then true
        else false
      end
      from public.au_group_runtime_config c
      where c.config_key = p_key
      limit 1
    ),
    p_default
  );
$$;


ALTER FUNCTION "public"."au_group_config_bool"("p_key" "text", "p_default" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_config_int"("p_key" "text", "p_default" integer) RETURNS integer
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select coalesce(
    nullif(trim(public.au_group_get_runtime_config(p_key)), '')::integer,
    p_default
  );
$$;


ALTER FUNCTION "public"."au_group_config_int"("p_key" "text", "p_default" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_config_text"("p_key" "text", "p_default" "text") RETURNS "text"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select coalesce(
    nullif(trim(public.au_group_get_runtime_config(p_key)), ''),
    p_default
  );
$$;


ALTER FUNCTION "public"."au_group_config_text"("p_key" "text", "p_default" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_count_company_creditors"("p_bankruptcy_id" "uuid") RETURNS bigint
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select count(*)::bigint
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name)
    and not public.au_group_is_suppressed_creditor_name(c.name);
$$;


ALTER FUNCTION "public"."au_group_count_company_creditors"("p_bankruptcy_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_creditor_pipeline_status"("p_creditor_id" "uuid") RETURNS "text"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_creditor_pipeline_status"("p_creditor_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone DEFAULT NULL::timestamp with time zone) RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $_$
  with v_since as (
    select coalesce(
      p_since,
      now() - (public.au_group_config_int('daily_report_window_hours', 24) || ' hours')::interval
    ) as since
  ),
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
$_$;


ALTER FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) IS 'KD-60/WP-03a: one row per (creditor, bankruptcy) for the daily Slack report, grouped by debtor.';



CREATE OR REPLACE FUNCTION "public"."au_group_daily_creditor_report_rows"("p_since" timestamp with time zone DEFAULT NULL::timestamp with time zone) RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $_$
  with v_since as (
    select coalesce(
      p_since,
      now() - (public.au_group_config_int('daily_report_window_hours', 24) || ' hours')::interval
    ) as since
  ),
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
    select distinct on (c.id)
      coalesce(nullif(trim(c.original_name), ''), c.name)::text as creditor,
      coalesce(nullif(trim(c.normalized_name), ''), c.name)::text as company_name,
      public.au_group_parse_creditor_city(c.address) as city,
      public.au_group_parse_creditor_state(c.address, b.state) as state,
      case when c.claim_amount is null then ''
        else to_char(c.claim_amount, 'FM$999,999,999,990.00') end as claim,
      public.au_group_creditor_pipeline_status(c.id) as status,
      public.au_group_zoominfo_company_url(c.zoominfo_company_id) as zoominfo_url
    from public.creditors c
    left join lateral (
      select bk.state from creditor_bankruptcy cb
      inner join public.bankruptcies bk on bk.id = cb.bankruptcy_id
      where cb.creditor_id = c.id
      order by bk.created_at desc nulls last limit 1
    ) b on true
    cross join v_since vs
    where c.is_company is true
      and not public.au_group_is_junk_creditor_name(c.name)
      and (c.created_at >= vs.since or exists (
        select 1 from creditor_bankruptcy cb2
        inner join public.bankruptcies b2 on b2.id = cb2.bankruptcy_id
        where cb2.creditor_id = c.id and b2.created_at >= vs.since))
    order by c.id, c.created_at desc
  )
  select jsonb_build_object(
    'since', (select since from v_since),
    'row_count', (select count(*)::int from row_data),
    'rows', coalesce((select jsonb_agg(to_jsonb(rd)) from row_data rd), '[]'::jsonb)
  );
$_$;


ALTER FUNCTION "public"."au_group_daily_creditor_report_rows"("p_since" timestamp with time zone) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_daily_pipeline_summary"("p_since" timestamp with time zone DEFAULT ("now"() - '24:00:00'::interval)) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_result jsonb;
begin
  select jsonb_build_object(
    'since', p_since,
    'new_bankruptcies', (select count(*) from public.bankruptcies where created_at >= p_since),
    'new_creditors', (select count(*) from public.creditors where created_at >= p_since),
    'zoom_contacts_added', (select count(*) from public.zoom_info_contacts where created_at >= p_since),
    'salesforce_accounts_synced', (select count(*) from public.salesforce_accounts where last_sync_at >= p_since),
    'pacer_poll_completed', (select count(*) from public.processing_jobs where job_type = 'pacer_poll' and status = 'completed' and completed_at >= p_since),
    'pacer_poll_failed', (select count(*) from public.processing_jobs where job_type = 'pacer_poll' and status = 'failed' and completed_at >= p_since),
    'manual_review_pending', (select count(*) from public.manual_review_queue),
    'schedule_f_monitoring', (select count(*) from public.schedule_f_queue where status = 'monitoring'),
    'schedule_f_pending_approval', (select count(*) from public.schedule_f_queue where status = 'pending_approval'),
    'outreach_ready_cases', (select count(*) from public.bankruptcy_case_status where outreach_ready = true),
    'pipeline_executions_failed', (select count(*) from public.pipeline_executions where status = 'failed' and created_at >= p_since)
  ) into v_result;
  return v_result;
end;
$$;


ALTER FUNCTION "public"."au_group_daily_pipeline_summary"("p_since" timestamp with time zone) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_diff_pacer_favorites"("p_favorites" "jsonb", "p_bankruptcy_ids" "uuid"[] DEFAULT NULL::"uuid"[]) RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  with fav as (
    select coalesce(f->>'case_number', f->>'caseNumber') as case_number
    from jsonb_array_elements(coalesce(p_favorites, '[]'::jsonb)) f
  ),
  pending as (
    select q.id, b.case_number, q.status
    from public.schedule_f_queue q
    inner join public.bankruptcies b on b.id = q.bankruptcy_id
    where q.status = 'pending_approval'
      and (p_bankruptcy_ids is null or q.bankruptcy_id = any (p_bankruptcy_ids))
  )
  select jsonb_build_object(
    'new_favorites', coalesce((
      select jsonb_agg(jsonb_build_object('case_number', f.case_number))
      from fav f
      where not exists (
        select 1
        from public.schedule_f_queue q
        inner join public.bankruptcies b on b.id = q.bankruptcy_id
        where b.case_number = f.case_number
      )
    ), '[]'::jsonb),
    'pending_approval', coalesce((
      select jsonb_agg(jsonb_build_object('id', p.id, 'case_number', p.case_number, 'status', p.status))
      from pending p
    ), '[]'::jsonb)
  );
$$;


ALTER FUNCTION "public"."au_group_diff_pacer_favorites"("p_favorites" "jsonb", "p_bankruptcy_ids" "uuid"[]) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_job_id uuid;
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  if exists (
    select 1
    from   public.processing_jobs
    where  bankruptcy_id = p_bankruptcy_id
      and  job_type      = p_job_type
      and  status        in (
             'queued'::processing_job_status,
             'running'::processing_job_status
           )
  ) then
    return jsonb_build_object('enqueued', false);
  end if;

  begin
    insert into public.processing_jobs (job_type, status, bankruptcy_id)
    values (p_job_type, 'queued'::processing_job_status, p_bankruptcy_id)
    returning id into v_job_id;

    return jsonb_build_object('enqueued', true, 'job_id', v_job_id);
  exception
    when unique_violation then
      return jsonb_build_object('enqueued', false);
  end;
end;
$$;


ALTER FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_enrich_loop_finalize"("p_job_id" "uuid", "p_bankruptcy_id" "uuid" DEFAULT NULL::"uuid", "p_pipeline_execution_id" "uuid" DEFAULT NULL::"uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_all jsonb;
  v_matched text[] := array['matched', 'cached', 'dry_run'];
begin
  select coalesce(jsonb_agg(s.result order by s.creditor_id), '[]'::jsonb)
  into v_all
  from public.au_group_enrich_loop_staging s
  where s.job_id = p_job_id;

  delete from public.au_group_enrich_loop_staging where job_id = p_job_id;

  return jsonb_build_object(
    'bankruptcy_id', p_bankruptcy_id,
    'enrich_job_id', p_job_id,
    'pipeline_execution_id', p_pipeline_execution_id,
    'enrichment_summary', jsonb_build_object(
      'creditors_processed', jsonb_array_length(v_all),
      'zoominfo_company_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where coalesce(e->>'zoominfo_company_id', '') <> ''
           or (e->>'zoominfo_status') = any (v_matched)
      ),
      'zoominfo_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'matched'
      ),
      'cache_hits', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where (e->>'cache_hit')::boolean is true
      ),
      'no_match', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'no_match'
      ),
      'ambiguous', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'ambiguous'
      ),
      'no_contact_found', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' in ('no_contact_found', 'no_match')
          and coalesce((e->>'contacts_saved')::integer, 0) = 0
      ),
      'rate_limited', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'rate_limited'
      ),
      'contacts_saved', (
        select coalesce(sum((e->>'contacts_saved')::integer), 0)::integer
        from jsonb_array_elements(v_all) e
      ),
      'skipped_individual', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'skipped_individual'
      ),
      'errors', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'error'
      )
    )
  );
end;
$$;


ALTER FUNCTION "public"."au_group_enrich_loop_finalize"("p_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_pipeline_execution_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_enrich_loop_push"("p_job_id" "uuid", "p_creditor_id" "uuid", "p_result" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_job_id is null or p_creditor_id is null then
    raise exception 'job_id and creditor_id required' using errcode = 'P0001';
  end if;

  insert into public.au_group_enrich_loop_staging (job_id, creditor_id, result, updated_at)
  values (p_job_id, p_creditor_id, coalesce(p_result, '{}'::jsonb), now())
  on conflict (job_id, creditor_id) do update
    set result = public.au_group_enrich_loop_staging.result || excluded.result,
        updated_at = now();

  return jsonb_build_object('ok', true, 'job_id', p_job_id, 'creditor_id', p_creditor_id);
end;
$$;


ALTER FUNCTION "public"."au_group_enrich_loop_push"("p_job_id" "uuid", "p_creditor_id" "uuid", "p_result" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_evaluate_outreach_gates"("p_creditor_id" "uuid", "p_suppress" boolean DEFAULT false, "p_dnc" boolean DEFAULT false, "p_active_engagement" boolean DEFAULT false, "p_repeat_threshold" integer DEFAULT NULL::integer, "p_repeat_window_months" integer DEFAULT NULL::integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_repeat record;
  v_threshold integer;
  v_window integer;
  v_repeat_exposure boolean := false;
  v_outreach_eligible boolean;
  v_reason text := 'ok';
begin
  v_threshold := coalesce(
    p_repeat_threshold,
    public.au_group_config_int('repeat_exposure_threshold', 4)
  );
  v_window := coalesce(
    p_repeat_window_months,
    public.au_group_config_int('repeat_exposure_window_months', 18)
  );

  if p_creditor_id is not null then
    select *
    into v_repeat
    from public.au_group_check_repeat_exposure(
      p_creditor_id,
      v_threshold,
      v_window
    )
    limit 1;
    v_repeat_exposure := coalesce(v_repeat.is_repeat, false);
  else
    v_repeat := null;
    v_repeat_exposure := false;
  end if;

  if p_suppress or p_dnc then
    v_outreach_eligible := false;
    v_reason := case when p_dnc then 'dnc' else 'suppressed' end;
  elsif p_active_engagement then
    v_outreach_eligible := false;
    v_reason := 'active_engagement';
  elsif v_repeat_exposure then
    v_outreach_eligible := false;
    v_reason := 'repeat_exposure';
  else
    v_outreach_eligible := true;
    v_reason := 'ok';
  end if;

  return jsonb_build_object(
    'creditor_id', p_creditor_id,
    'suppress', p_suppress,
    'dnc', p_dnc,
    'active_engagement', p_active_engagement,
    'repeat_exposure', v_repeat_exposure,
    'outreach_eligible', v_outreach_eligible,
    'gate_reason', v_reason,
    'repeat_filing_count',
      case when p_creditor_id is not null then v_repeat.filing_count else null end,
    'suggested_message',
      case when p_creditor_id is not null then v_repeat.suggested_message else null end
  );
end;
$$;


ALTER FUNCTION "public"."au_group_evaluate_outreach_gates"("p_creditor_id" "uuid", "p_suppress" boolean, "p_dnc" boolean, "p_active_engagement" boolean, "p_repeat_threshold" integer, "p_repeat_window_months" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_expand_import_rows"("p_body" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_rows jsonb;
begin
  v_rows := coalesce(p_body->'rows', p_body->'body'->'rows');
  if v_rows is null or jsonb_typeof(v_rows) <> 'array' or jsonb_array_length(v_rows) = 0 then
    raise exception 'body.rows[] required' using errcode = 'P0001';
  end if;
  return jsonb_build_object('items', v_rows);
end;
$$;


ALTER FUNCTION "public"."au_group_expand_import_rows"("p_body" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_fail_stale_processing_jobs"("p_max_age" interval DEFAULT '24:00:00'::interval) RETURNS integer
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare
  updated integer;
begin
  update public.processing_jobs
  set
    status = 'failed',
    error_message = coalesce(error_message, 'stale job auto-failed'),
    completed_at = now()
  where status in ('queued', 'running')
    and created_at < now() - p_max_age
    and completed_at is null;

  get diagnostics updated = row_count;
  return updated;
end;
$$;


ALTER FUNCTION "public"."au_group_fail_stale_processing_jobs"("p_max_age" interval) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_finalize_document_job"("p_job_id" "uuid", "p_pipeline_execution_id" "uuid" DEFAULT NULL::"uuid", "p_schedule_f_queue_id" "uuid" DEFAULT NULL::"uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_rows jsonb;
  v_expected integer;
  v_any_failed boolean;
  v_any_review boolean;
  v_first jsonb;
  v_bankruptcy_id uuid;
begin
  if p_job_id is null then
    raise exception 'p_job_id is required' using errcode = 'P0001';
  end if;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'bankruptcy_id', r.bankruptcy_id,
      'processing_job_id', r.processing_job_id,
      'pipeline_execution_id', p_pipeline_execution_id,
      'schedule_f_queue_id', p_schedule_f_queue_id,
      'doc_index', r.doc_index,
      'doc_key', r.doc_key,
      's3_key', r.s3_key,
      'document_url', r.document_url,
      'document_id', r.document_id,
      'parser_status', r.parser_status,
      'manual_review_required', r.manual_review_required,
      'parser_result', r.parser_result,
      'parse_error', r.parse_error
    ) order by r.doc_index
  ), '[]'::jsonb)
  into v_rows
  from public.document_parse_results r
  where r.processing_job_id = p_job_id;

  if jsonb_array_length(v_rows) = 0 then
    raise exception 'no document_parse_results for job %', p_job_id using errcode = 'P0001';
  end if;

  v_first := v_rows->0;
  v_bankruptcy_id := (v_first->>'bankruptcy_id')::uuid;
  v_any_failed := exists (
    select 1 from jsonb_array_elements(v_rows) e
    where e->>'parser_status' = 'failed'
  );
  v_any_review := exists (
    select 1 from jsonb_array_elements(v_rows) e
    where (e->>'manual_review_required')::boolean is true
  );

  return jsonb_build_object(
    'bankruptcy_id', v_bankruptcy_id,
    'processing_job_id', p_job_id,
    'pipeline_execution_id', p_pipeline_execution_id,
    'schedule_f_queue_id', p_schedule_f_queue_id,
    'parser_results', v_rows,
    'any_failed', v_any_failed,
    'any_manual_review', v_any_review,
    'document_count', jsonb_array_length(v_rows)
  );
end;
$$;


ALTER FUNCTION "public"."au_group_finalize_document_job"("p_job_id" "uuid", "p_pipeline_execution_id" "uuid", "p_schedule_f_queue_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_get_runtime_config"("p_key" "text") RETURNS "text"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select c.config_value
  from public.au_group_runtime_config c
  where c.config_key = trim(coalesce(p_key, ''));
$$;


ALTER FUNCTION "public"."au_group_get_runtime_config"("p_key" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_get_zoominfo_company_cache"("p_cache_key" "text") RETURNS TABLE("cache_key" "text", "company_id" "text", "normalized_name" "text", "match_confidence" numeric, "firmographics" "jsonb", "cache_hit" boolean)
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select c.cache_key, c.company_id, c.normalized_name, c.match_confidence, c.firmographics, true
  from public.au_group_zoominfo_company_cache c
  where c.cache_key = p_cache_key and c.expires_at > now();
$$;


ALTER FUNCTION "public"."au_group_get_zoominfo_company_cache"("p_cache_key" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_is_junk_creditor_name"("p_name" "text") RETURNS boolean
    LANGUAGE "plpgsql" STABLE STRICT
    SET "search_path" TO 'public'
    AS $_$
declare
  v_display_name text;
  v_name text;
  v_min_length integer;
  v_max_line_digits integer;
begin
  v_min_length := public.au_group_config_int('creditor_name_min_length', 3);
  v_max_line_digits := public.au_group_config_int('creditor_line_number_max_digits', 3);
  v_display_name := trim(p_name);
  if v_display_name = '' then return true; end if;
  v_name := lower(v_display_name);
  if length(v_display_name) < v_min_length then return true; end if;
  if v_name in ('contact', 'contacts', 'name', 'address', 'amount', 'claim', 'creditor', 'creditors', 'total') then return true; end if;
  if v_display_name ~* '^(list of creditors|creditor matrix|creditors holding|official form 204|20 largest unsecured|name of creditor|creditor\s*name)' then return true; end if;
  if v_display_name ~* '(mailing address|email address|name of creditor|including zip|zip code|nature of claim|account number|official form|form\s*204|list of creditors|creditor matrix|claim amount)' then return true; end if;
  if v_display_name ~ ('^\d{1,' || v_max_line_digits || '}$') then return true; end if;
  return false;
end;
$_$;


ALTER FUNCTION "public"."au_group_is_junk_creditor_name"("p_name" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_is_junk_creditor_name"("p_name" "text") IS 'Form 204 label / line-number junk filter — used by merge + SYS-04 read RPCs';



CREATE OR REPLACE FUNCTION "public"."au_group_is_suppressed_creditor_name"("p_name" "text") RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_is_suppressed_creditor_name"("p_name" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_is_target_state"("p_state" "text", "p_states" "text"[] DEFAULT NULL::"text"[]) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select exists (
    select 1
    from public.au_group_active_target_states(p_states) active
    where active = upper(left(trim(coalesce(p_state, '')), 2))::char(2)
  );
$$;


ALTER FUNCTION "public"."au_group_is_target_state"("p_state" "text", "p_states" "text"[]) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_jsonb_midpoint_count"("range" "jsonb") RETURNS integer
    LANGUAGE "sql" IMMUTABLE
    AS $$
  select case
    when range is null then null
    when (range->>'min') is not null and (range->>'max') is not null then
      (((range->>'min')::integer + (range->>'max')::integer) / 2)
    when (range->>'min') is not null then (range->>'min')::integer
    when (range->>'max') is not null then (range->>'max')::integer
    else null
  end;
$$;


ALTER FUNCTION "public"."au_group_jsonb_midpoint_count"("range" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_jsonb_midpoint_usd"("range" "jsonb") RETURNS numeric
    LANGUAGE "sql" IMMUTABLE
    AS $$
  select case
    when range is null then null
    when (range->>'min_usd') is not null and (range->>'max_usd') is not null then
      ((range->>'min_usd')::numeric + (range->>'max_usd')::numeric) / 2
    when (range->>'min_usd') is not null then (range->>'min_usd')::numeric
    when (range->>'max_usd') is not null then (range->>'max_usd')::numeric
    else null
  end;
$$;


ALTER FUNCTION "public"."au_group_jsonb_midpoint_usd"("range" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_link_document_bankruptcy"("p_document_id" "uuid", "p_bankruptcy_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$ declare v_doc public.documents%rowtype; begin update public.documents set bankruptcy_id = p_bankruptcy_id, updated_at = now() where id = p_document_id returning * into v_doc; if v_doc.id is null then raise exception 'document not found: %', p_document_id using errcode = 'P0002'; end if; update public.form201_extractions set bankruptcy_id = p_bankruptcy_id where document_id = p_document_id; update public.creditor_matrix_extractions set bankruptcy_id = p_bankruptcy_id where document_id = p_document_id; update public.manual_review_queue set bankruptcy_id = p_bankruptcy_id where document_id = p_document_id and bankruptcy_id is null; return jsonb_build_object('document_id', v_doc.id, 'bankruptcy_id', p_bankruptcy_id, 's3_key', v_doc.s3_key, 'filing_type', v_doc.filing_type); end; $$;


ALTER FUNCTION "public"."au_group_link_document_bankruptcy"("p_document_id" "uuid", "p_bankruptcy_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_list_company_creditors"("p_bankruptcy_id" "uuid") RETURNS TABLE("creditor_id" "uuid", "creditor_name" "text", "normalized_name" "text", "creditor_address" "text", "claim_amount" numeric, "creditor_state" character)
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select
    c.id,
    c.name,
    coalesce(
      nullif(trim(c.normalized_name), ''),
      public.au_group_normalize_company_name(c.name)
    ) as normalized_name,
    c.address,
    c.claim_amount,
    public.au_group_parse_creditor_state(c.address, b.state)
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  inner join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name)
    and not public.au_group_is_suppressed_creditor_name(c.name);
$$;


ALTER FUNCTION "public"."au_group_list_company_creditors"("p_bankruptcy_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_list_contact_titles"("p_tier" smallint, "p_include_fallback" boolean DEFAULT true) RETURNS "text"[]
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_list_contact_titles"("p_tier" smallint, "p_include_fallback" boolean) OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bankruptcies" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "case_number" character varying(50) NOT NULL,
    "debtor_name" character varying(255) NOT NULL,
    "filing_date" "date" NOT NULL,
    "court_district" character varying(100) NOT NULL,
    "estimated_assets" numeric(15,2),
    "estimated_liabilities" numeric(15,2),
    "estimated_creditor_count" integer,
    "chapter_type" "public"."bankruptcy_chapter" NOT NULL,
    "state" character varying(2) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "is_business" boolean DEFAULT true,
    "monitoring_enabled" boolean DEFAULT true,
    "source_type" "text" DEFAULT 'rss'::"text",
    "rss_guid" "text",
    "last_docket_check_at" timestamp with time zone,
    "court_id" "text",
    "lead_score" integer DEFAULT 0,
    "lead_priority" "text",
    "sales_ready" boolean DEFAULT false,
    "city" "text",
    "industry_code" "text",
    "estimated_assets_range" "jsonb",
    "estimated_liabilities_range" "jsonb",
    "estimated_creditor_count_range" "jsonb",
    "extraction_confidence_score" numeric(5,4),
    "manual_review_required" boolean DEFAULT false NOT NULL,
    "forms_downloaded_at" timestamp with time zone
);


ALTER TABLE "public"."bankruptcies" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_list_pacer_poll_candidates"() RETURNS SETOF "public"."bankruptcies"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select b.*
  from public.bankruptcies b
  where b.case_number is not null
    and trim(b.case_number) <> ''
    and b.chapter_type::text in ('11', '11-Subchapter-V')
    and public.au_group_is_target_state(b.state)
  order by b.last_docket_check_at nulls first, b.created_at asc;
$$;


ALTER FUNCTION "public"."au_group_list_pacer_poll_candidates"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_list_pacer_poll_candidates"() IS 'SYS-01B (FR-1.1): all Ch.11 cases in active target states with valid case_number; no row cap.';



CREATE OR REPLACE FUNCTION "public"."au_group_list_pacer_poll_candidates"("p_limit" integer DEFAULT NULL::integer, "p_states" "text"[] DEFAULT NULL::"text"[]) RETURNS SETOF "public"."bankruptcies"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_limit int;
  v_config text;
begin
  v_limit := p_limit;
  if v_limit is null then
    select public.au_group_get_runtime_config('sys01b_max_cases_per_run') into v_config;
    if v_config is not null and trim(v_config) <> '' then
      v_limit := trim(v_config)::int;
    end if;
  end if;

  if v_limit is null or v_limit < 1 then
    raise exception 'au_group_list_pacer_poll_candidates: set p_limit or au_group_runtime_config.sys01b_max_cases_per_run';
  end if;

  return query
  select b.*
  from public.bankruptcies b
  where b.case_number is not null
    and trim(b.case_number) <> ''
    and b.state in (select active from public.au_group_active_target_states(p_states) active)
  order by b.last_docket_check_at nulls first, b.created_at asc
  limit v_limit;
end;
$$;


ALTER FUNCTION "public"."au_group_list_pacer_poll_candidates"("p_limit" integer, "p_states" "text"[]) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_list_target_states"() RETURNS SETOF character
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select t.state
  from public.au_group_target_states t
  where t.active is true
  order by t.state;
$$;


ALTER FUNCTION "public"."au_group_list_target_states"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_list_target_states"() IS 'KD-14: active target states for PACER intake and poll filtering';



CREATE OR REPLACE FUNCTION "public"."au_group_list_tier_contact_titles"("p_tier" integer) RETURNS TABLE("title" "text", "sort_order" integer)
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select t.title_pattern as title, t.sort_order::integer
  from public.au_group_tier_contact_titles t
  where t.tier = p_tier and p_tier between 1 and 3 and t.active is true
  order by t.sort_order asc, t.title_pattern asc;
$$;


ALTER FUNCTION "public"."au_group_list_tier_contact_titles"("p_tier" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_merge_creditor_matrix"("p_bankruptcy_id" "uuid", "p_creditors" "jsonb", "p_confidence_score" numeric DEFAULT NULL::numeric) RETURNS integer
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $_$
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
$_$;


ALTER FUNCTION "public"."au_group_merge_creditor_matrix"("p_bankruptcy_id" "uuid", "p_creditors" "jsonb", "p_confidence_score" numeric) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_normalize_company_name"("p_name" "text") RETURNS "text"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."au_group_normalize_company_name"("p_name" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_normalize_company_name"("p_name" "text") IS 'KD-24: normalize company names using au_group_company_name_rules; used for cache keys and creditors.normalized_name.';



CREATE OR REPLACE FUNCTION "public"."au_group_normalize_rss_item"("p_item" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_item jsonb := coalesce(p_item, '{}'::jsonb);
  v_title text;
  v_content text;
  v_link text;
  v_clean text;
  v_case text;
  v_debtor text;
  v_chapter text;
  v_court text;
  v_guid text;
  v_doc_url text;
  v_signal integer;
  v_qualified boolean;
  v_is_business boolean;
  v_is_person boolean;
  v_excluded boolean;
  c_max_html constant integer := 32768;
  c_max_clean constant integer := 12000;
begin
  v_title := btrim(regexp_replace(coalesce(v_item->>'title', ''), '\s+', ' ', 'g'));
  v_content := left(
    coalesce(
      v_item->>'content',
      v_item->>'contentSnippet',
      v_item->>'description',
      ''
    ),
    c_max_html
  );
  v_link := coalesce(v_item->>'link', '');
  v_clean := left(
    btrim(regexp_replace(regexp_replace(v_content, '<[^>]+>', ' ', 'g'), '\s+', ' ', 'g')),
    c_max_clean
  );

  v_case := (regexp_match(v_title, '(\d{2}-\d{4,6}(?:-[a-z0-9]+)*)', 'i'))[1];

  v_chapter := coalesce(
    (regexp_match(v_clean, 'chapter[:\s]+(\d+)', 'i'))[1],
    (regexp_match(v_clean, 'chapter\s+(\d+)', 'i'))[1]
  );
  v_court := (regexp_match(v_link, 'ecf\.([a-z]+)\.uscourts\.gov', 'i'))[1];
  v_guid := coalesce(v_item->>'guid', v_item->>'id', v_link);

  v_doc_url := (regexp_match(v_content, 'href=[''\"]([^''\"]*doc1[^''\"]+)[''\"]', 'i'))[1];
  if v_doc_url is null then
    v_doc_url := (regexp_match(v_content, 'https://ecf\.[^''\" ]+/doc1/[^''\" ]+', 'i'))[1];
  end if;

  v_debtor := btrim(regexp_replace(
    case when v_case is not null then regexp_replace(v_title, v_case, '', 'i') else v_title end,
    '\s+', ' ', 'g'
  ));
  v_is_business := v_debtor ~* '(llc|inc|corp|corporation|ltd|lp|holdings|company|co\.|group|enterprises)';
  v_is_person := v_debtor ~ '^[A-Z][a-z]+ [A-Z][a-z]+' and not v_is_business;
  v_excluded := v_clean ~* '(certificate of credit counseling|certificate of mailing|personal financial management|proof of claim|meeting of creditors|\[schedules\]|chapter 13 plan|notice of hearing)';

  v_signal := 0;
  if v_clean ~* 'voluntary petition' then v_signal := v_signal + 40; end if;
  if v_clean ~* 'petition filed' then v_signal := v_signal + 30; end if;
  if v_clean ~* 'chapter\s*11' then v_signal := v_signal + 20; end if;
  if public.au_group_schedule_f_keyword_hit(v_clean) then v_signal := v_signal + 15; end if;

  v_qualified := v_signal >= 40
    and not v_is_person
    and v_case is not null
    and v_guid is not null
    and not v_excluded;

  return jsonb_build_object(
    'case_number', v_case,
    'debtor_name', nullif(v_debtor, ''),
    'chapter', v_chapter,
    'court_id', v_court,
    'filing_date', left(coalesce(v_item->>'isoDate', v_item->>'pubDate', ''), 10),
    'rss_guid', v_guid,
    'document_url', v_doc_url,
    'unique_key', coalesce(v_court, '') || ':' || coalesce(v_case, '') || ':' || coalesce(v_guid, ''),
    'signal_score', case when v_excluded then 0 else v_signal end,
    'is_business', v_is_business,
    'is_likely_person', v_is_person,
    'is_excluded_event', v_excluded,
    'is_qualified', v_qualified,
    'raw_content', left(v_clean, 4000)
  );
end;
$$;


ALTER FUNCTION "public"."au_group_normalize_rss_item"("p_item" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_normalize_rss_items"("p_items" "jsonb") RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select jsonb_build_object(
    'items',
    coalesce(
      jsonb_agg(public.au_group_normalize_rss_item(elem) order by ord),
      '[]'::jsonb
    )
  )
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) with ordinality as t(elem, ord);
$$;


ALTER FUNCTION "public"."au_group_normalize_rss_items"("p_items" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_normalize_zoominfo_company_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer DEFAULT NULL::integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_ctx jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body jsonb;
  v_data jsonb;
  v_candidates jsonb;
  v_state_hint text;
  v_top jsonb;
  v_second jsonb;
  v_top_score numeric;
  v_second_score numeric;
  v_attrs jsonb;
  v_company_id text;
  v_revenue numeric;
  v_employees numeric;
  v_industry text;
  v_hq text;
  i integer;
  v_item jsonb;
  v_attrs_i jsonb;
  v_hq_i text;
  v_conf numeric;
  v_geo numeric;
  v_score numeric;
  v_best jsonb;
  v_best_score numeric := -1;
  v_second_best_score numeric := -1;
  v_err text;
begin
  if p_status_code = 429 then
    return v_ctx || jsonb_build_object('statusCode', 429);
  end if;

  v_body := coalesce(p_body, '{}'::jsonb);
  v_err := coalesce(v_body->>'error', v_body->>'message');
  if v_err is not null and v_err <> '' then
    return v_ctx || jsonb_build_object(
      'zoominfo_status', 'error',
      'zoominfo_match_status', 'error',
      'zoominfo_error', left(v_err, 500),
      'zoominfo_company_id', null,
      'match_confidence', null,
      'cache_hit', false
    );
  end if;

  v_data := coalesce(v_body->'data', v_body->'results', v_body);
  if jsonb_typeof(v_data) = 'array' then
    v_candidates := v_data;
  elsif v_data is null or v_data = 'null'::jsonb then
    v_candidates := '[]'::jsonb;
  else
    v_candidates := jsonb_build_array(v_data);
  end if;

  if jsonb_array_length(v_candidates) = 0 then
    return v_ctx || jsonb_build_object(
      'zoominfo_status', 'no_match',
      'zoominfo_match_status', 'no_match',
      'zoominfo_company_id', null,
      'match_confidence', null,
      'cache_hit', false,
      'skipped_reason', 'no_match'
    );
  end if;

  v_state_hint := upper(left(coalesce(v_ctx->>'creditor_state', ''), 2));

  for i in 0 .. jsonb_array_length(v_candidates) - 1 loop
    v_item := v_candidates->i;
    v_attrs_i := coalesce(v_item->'attributes', v_item);
    v_hq_i := upper(coalesce(
      v_attrs_i->>'headquarters',
      v_attrs_i->>'headquartersState',
      v_attrs_i->>'state',
      ''
    ));
    v_conf := coalesce(
      nullif(v_attrs_i->>'matchScore', '')::numeric,
      nullif(v_attrs_i->>'confidence', '')::numeric,
      nullif(v_attrs_i->>'score', '')::numeric,
      0.5
    );
    v_geo := 0;
    if v_state_hint <> '' and position(v_state_hint in v_hq_i) > 0 then
      v_geo := 1;
    end if;
    v_score := v_conf + v_geo * 0.5;

    if v_score > v_best_score then
      v_second_best_score := v_best_score;
      v_best_score := v_score;
      v_best := jsonb_build_object('item', v_item, 'attrs', v_attrs_i, 'score', v_score);
    elsif v_score > v_second_best_score then
      v_second_best_score := v_score;
    end if;
  end loop;

  if v_second_best_score >= 0 and abs(v_best_score - v_second_best_score) < 0.05 then
    return v_ctx || jsonb_build_object(
      'zoominfo_status', 'ambiguous',
      'zoominfo_match_status', 'ambiguous',
      'zoominfo_company_id', null,
      'match_confidence', v_best_score,
      'cache_hit', false,
      'skipped_reason', 'ambiguous_match'
    );
  end if;

  v_attrs := v_best->'attrs';
  v_item := v_best->'item';
  v_revenue := coalesce(
    nullif(v_attrs->>'revenue', '')::numeric,
    nullif(v_attrs->>'annualRevenue', '')::numeric
  );
  v_employees := coalesce(
    nullif(v_attrs->>'employeeCount', '')::numeric,
    nullif(v_attrs->>'employees', '')::numeric
  );
  v_industry := coalesce(v_attrs->>'industry', v_attrs->>'primaryIndustry');
  v_company_id := coalesce(v_item->>'id', v_attrs->>'companyId');
  v_hq := coalesce(v_attrs->>'headquarters', v_attrs->>'headquartersState');

  return v_ctx || jsonb_build_object(
    'zoominfo_status', 'matched',
    'zoominfo_match_status', 'matched',
    'zoominfo_company_id', v_company_id,
    'match_confidence', v_best_score,
    'normalized_name', coalesce(v_attrs->>'name', v_attrs->>'companyName', v_ctx->>'normalized_name'),
    'company_revenue', v_revenue,
    'company_employee_count', v_employees,
    'company_industry', v_industry,
    'company_headquarters', v_hq,
    'zoominfo_firmographics', jsonb_build_object(
      'revenue', v_revenue,
      'employee_count', v_employees,
      'industry', v_industry,
      'headquarters', v_hq
    ),
    'cache_hit', false,
    'raw_zoominfo', v_body
  );
end;
$$;


ALTER FUNCTION "public"."au_group_normalize_zoominfo_company_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_normalize_zoominfo_contact_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer DEFAULT NULL::integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_base jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body jsonb := coalesce(p_body, '{}'::jsonb);
  v_data jsonb;
  v_raw jsonb;
  v_contacts jsonb := '[]'::jsonb;
  i integer;
  v_item jsonb;
  v_attrs jsonb;
  v_first text;
  v_last text;
  v_full text;
  v_eng numeric;
  v_sorted jsonb;
begin
  if p_status_code = 429 then
    return v_base || jsonb_build_object('statusCode', 429, 'contacts_saved', 0);
  end if;

  if coalesce(v_body->>'error', v_body->>'message') is not null then
    return v_base || jsonb_build_object(
      'contacts_saved', 0,
      'contact_search_error', left(coalesce(v_body->>'error', v_body->>'message'), 300)
    );
  end if;

  v_data := coalesce(v_body->'data', v_body->'results', v_body);
  if jsonb_typeof(v_data) = 'array' then
    v_raw := v_data;
  elsif v_data is null then
    v_raw := '[]'::jsonb;
  else
    v_raw := jsonb_build_array(v_data);
  end if;

  for i in 0 .. jsonb_array_length(v_raw) - 1 loop
    v_item := v_raw->i;
    v_attrs := coalesce(v_item->'attributes', v_item);
    v_first := coalesce(v_attrs->>'firstName', v_attrs->>'first_name', '');
    v_last := coalesce(v_attrs->>'lastName', v_attrs->>'last_name', '');
    v_full := coalesce(
      v_attrs->>'fullName',
      v_attrs->>'name',
      nullif(btrim(v_first || ' ' || v_last), ''),
      'Unknown'
    );
    if v_full is null or v_full = 'Unknown' then
      continue;
    end if;
    v_eng := coalesce(
      nullif(v_attrs->>'engagementScore', '')::numeric,
      nullif(v_attrs->>'contactAccuracyScore', '')::numeric,
      nullif(v_attrs->>'score', '')::numeric,
      0
    );
    v_contacts := v_contacts || jsonb_build_array(jsonb_build_object(
      'full_name', v_full,
      'title', coalesce(v_attrs->>'jobTitle', v_attrs->>'title', v_attrs->>'primaryTitle'),
      'email', coalesce(v_attrs->>'email', v_attrs->>'emailAddress'),
      'phone', coalesce(v_attrs->>'phone', v_attrs->>'directPhone', v_attrs->>'mobilePhone'),
      'engagement_score', v_eng,
      'company_revenue', v_base->'company_revenue',
      'company_employee_count', v_base->'company_employee_count',
      'company_industry', v_base->'company_industry'
    ));
  end loop;

  select coalesce(jsonb_agg(e order by (e->>'engagement_score')::numeric desc nulls last), '[]'::jsonb)
  into v_sorted
  from (
    select e from jsonb_array_elements(v_contacts) e limit 3
  ) sub;

  return v_base || jsonb_build_object(
    'contacts_payload', v_sorted,
    'contacts_saved', jsonb_array_length(v_sorted),
    'zoominfo_status', case
      when jsonb_array_length(v_sorted) > 0 then v_base->>'zoominfo_status'
      when v_base->>'zoominfo_status' = 'matched' then 'no_contact_found'
      else v_base->>'zoominfo_status'
    end
  );
end;
$$;


ALTER FUNCTION "public"."au_group_normalize_zoominfo_contact_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_parse_creditor_city"("p_address" "text") RETURNS "text"
    LANGUAGE "sql" IMMUTABLE
    AS $_$
  select nullif(
    trim(
      coalesce(
        substring(
          coalesce(p_address, '')
          from ',\s*([^,]+)\s*,\s*[A-Z]{2}\s*(?:\d{5}(?:-\d{4})?)?\s*$'
        ),
        substring(
          coalesce(p_address, '')
          from '^\s*\d+[^,]*,\s*([^,]+)\s*,\s*[A-Z]{2}'
        )
      )
    ),
    ''
  );
$_$;


ALTER FUNCTION "public"."au_group_parse_creditor_city"("p_address" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."au_group_parse_creditor_city"("p_address" "text") IS 'Parse city from US-style creditor mailing address (best-effort).';



CREATE OR REPLACE FUNCTION "public"."au_group_parse_creditor_state"("p_address" "text", "p_fallback_state" character) RETURNS character
    LANGUAGE "sql" IMMUTABLE
    AS $_$
  select upper(
    coalesce(
      nullif(
        substring(
          coalesce(p_address, '')
          from '(?:,\s*|\s+)([A-Z]{2})\s*(?:\d{5}(?:-\d{4})?)?\s*$'
        ),
        ''
      ),
      nullif(
        substring(coalesce(p_address, '') from '\s([A-Z]{2})\s*$'),
        ''
      ),
      nullif(trim(p_fallback_state), '')
    )
  )::char(2);
$_$;


ALTER FUNCTION "public"."au_group_parse_creditor_state"("p_address" "text", "p_fallback_state" character) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_pick_document_parse_handoff"("p_bankruptcy_id" "uuid") RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select jsonb_build_object(
    'bankruptcy_id', p_bankruptcy_id,
    'document_url', (
      select de.document_url
      from public.docket_entries de
      where de.bankruptcy_id = p_bankruptcy_id
        and nullif(btrim(de.document_url), '') is not null
      order by de.filed_at desc nulls last, de.created_at desc
      limit 1
    ),
    'schedule_f_queue_id', (
      select sfq.id::text
      from public.schedule_f_queue sfq
      where sfq.bankruptcy_id = p_bankruptcy_id
      order by sfq.created_at desc
      limit 1
    )
  );
$$;


ALTER FUNCTION "public"."au_group_pick_document_parse_handoff"("p_bankruptcy_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_resolve_court_and_target_state"("p_court_id" "text") RETURNS TABLE("bankruptcy_state" character, "court_district" character varying, "is_target_state" boolean, "skip_reason" "text")
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_court_id varchar;
  v_state char(2);
  v_district varchar;
  v_active boolean;
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


ALTER FUNCTION "public"."au_group_resolve_court_and_target_state"("p_court_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_resolve_court_mapping"("p_court_id" "text") RETURNS TABLE("court_id" character varying, "state" character, "court_district" character varying)
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_court_id varchar;
begin
  v_court_id := lower(trim(coalesce(p_court_id, '')));
  if v_court_id = '' then
    return;
  end if;

  return query
  select m.court_id, m.state, m.court_district
  from public.au_group_court_mappings m
  where m.active is true
    and m.court_id = v_court_id;
end;
$$;


ALTER FUNCTION "public"."au_group_resolve_court_mapping"("p_court_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_resolve_manual_review"("p_review_id" "uuid", "p_resolved_by" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare
  v_row public.manual_review_queue%rowtype;
  v_pending integer;
begin
  update public.manual_review_queue
  set
    status = 'resolved',
    assigned_to = coalesce(nullif(trim(p_resolved_by), ''), assigned_to),
    updated_at = now()
  where id = p_review_id
    and status in ('pending', 'in_review')
  returning * into v_row;

  if v_row.id is null then
    select * into v_row
    from public.manual_review_queue
    where id = p_review_id;

    if v_row.id is null then
      raise exception 'manual_review_queue row not found: %', p_review_id
        using errcode = 'P0002';
    end if;

    if v_row.status <> 'resolved' then
      raise exception 'manual review item is not resolvable (status=%)', v_row.status
        using errcode = 'P0001';
    end if;
  end if;

  if v_row.bankruptcy_id is not null then
    select count(*)::integer
    into v_pending
    from public.manual_review_queue q
    where q.bankruptcy_id = v_row.bankruptcy_id
      and q.status in ('pending', 'in_review');

    if v_pending = 0 then
      update public.bankruptcies
      set manual_review_required = false, updated_at = now()
      where id = v_row.bankruptcy_id;
    end if;
  end if;

  return jsonb_build_object(
    'review_id', v_row.id,
    'document_id', v_row.document_id,
    'bankruptcy_id', v_row.bankruptcy_id,
    'status', v_row.status,
    'bankruptcy_manual_review_required', (
      select b.manual_review_required
      from public.bankruptcies b
      where b.id = v_row.bankruptcy_id
    )
  );
end;
$$;


ALTER FUNCTION "public"."au_group_resolve_manual_review"("p_review_id" "uuid", "p_resolved_by" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_resolve_territory_rep"("p_state" "text") RETURNS TABLE("state" character, "rep_name" character varying, "salesforce_user_id" character varying)
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_state char(2);
begin
  v_state := upper(left(trim(coalesce(p_state, '')), 2));
  if v_state = '' then
    return;
  end if;

  return query
  select t.state, t.rep_name, t.salesforce_user_id
  from public.au_group_territory_assignments t
  where t.state = v_state;

  if not found then
    return query
    select v_state, 'rep_default'::varchar, '005PLACEHOLDER99'::varchar;
  end if;
end;
$$;


ALTER FUNCTION "public"."au_group_resolve_territory_rep"("p_state" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_safe_numeric"("p_text" "text") RETURNS numeric
    LANGUAGE "plpgsql" IMMUTABLE
    SET "search_path" TO 'public'
    AS $_$
declare
  cleaned text;
begin
  cleaned := nullif(
    regexp_replace(coalesce(p_text, ''), '[^0-9.]', '', 'g'),
    ''
  );
  if cleaned is null or cleaned !~ '^\d+(\.\d+)?$' then
    return null;
  end if;
  return cleaned::numeric;
exception
  when invalid_text_representation then
    return null;
end;
$_$;


ALTER FUNCTION "public"."au_group_safe_numeric"("p_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_schedule_f_keyword_hit"("p_text" "text") RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  select exists (
    select 1
    from public.au_group_schedule_f_keywords k
    where k.active is true
      and coalesce(trim(p_text), '') ilike '%' || k.pattern || '%'
  );
$$;


ALTER FUNCTION "public"."au_group_schedule_f_keyword_hit"("p_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_set_creditor_company_tier"("p_creditor_id" "uuid", "p_tier" smallint, "p_bankruptcy_id" "uuid" DEFAULT NULL::"uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_creditor_id is null then return false; end if;
  if p_tier is null or p_tier < 1 or p_tier > 3 then return false; end if;
  if p_bankruptcy_id is not null then
    update public.creditors c
    set company_tier = p_tier, company_tier_assigned_at = now(), updated_at = now()
    where c.id = p_creditor_id
      and (
        exists (select 1 from public.bankruptcy_creditors bc where bc.creditor_id = c.id and bc.bankruptcy_id = p_bankruptcy_id)
        or c.source_bankruptcy_id = p_bankruptcy_id
      );
    return found;
  end if;
  update public.creditors c
  set company_tier = p_tier, company_tier_assigned_at = now(), updated_at = now()
  where c.id = p_creditor_id;
  return found;
end;
$$;


ALTER FUNCTION "public"."au_group_set_creditor_company_tier"("p_creditor_id" "uuid", "p_tier" smallint, "p_bankruptcy_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_set_creditor_zoominfo_company_id"("p_creditor_id" "uuid", "p_company_id" "text", "p_match_confidence" numeric DEFAULT NULL::numeric, "p_normalized_name" "text" DEFAULT NULL::"text", "p_match_status" "text" DEFAULT 'matched'::"text", "p_firmographics" "jsonb" DEFAULT NULL::"jsonb") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_creditor_id is null then return false; end if;
  update public.creditors c set
    zoominfo_company_id = case when p_company_id is null or trim(p_company_id) = '' then c.zoominfo_company_id else trim(p_company_id) end,
    normalized_name = coalesce(nullif(trim(p_normalized_name), ''), c.normalized_name),
    zoominfo_match_confidence = coalesce(p_match_confidence, c.zoominfo_match_confidence),
    zoominfo_match_status = coalesce(nullif(trim(p_match_status), ''), c.zoominfo_match_status),
    zoominfo_firmographics = coalesce(p_firmographics, c.zoominfo_firmographics),
    zoominfo_enriched_at = case when p_match_status in ('matched', 'cached', 'dry_run') then now() else c.zoominfo_enriched_at end,
    updated_at = now()
  where c.id = p_creditor_id;
  return found;
end;
$$;


ALTER FUNCTION "public"."au_group_set_creditor_zoominfo_company_id"("p_creditor_id" "uuid", "p_company_id" "text", "p_match_confidence" numeric, "p_normalized_name" "text", "p_match_status" "text", "p_firmographics" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_bankruptcy"("p_case_number" character varying, "p_debtor_name" character varying, "p_filing_date" "date", "p_court_district" character varying, "p_chapter_type" "public"."au_group_chapter_type", "p_state" character varying, "p_estimated_assets" numeric DEFAULT NULL::numeric, "p_estimated_liabilities" numeric DEFAULT NULL::numeric, "p_estimated_creditor_count" integer DEFAULT NULL::integer) RETURNS "uuid"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare
  v_id uuid;
begin
  insert into public.bankruptcies (
    case_number,
    debtor_name,
    filing_date,
    court_district,
    chapter_type,
    state,
    estimated_assets,
    estimated_liabilities,
    estimated_creditor_count
  )
  values (
    p_case_number,
    p_debtor_name,
    p_filing_date,
    p_court_district,
    p_chapter_type,
    p_state,
    p_estimated_assets,
    p_estimated_liabilities,
    p_estimated_creditor_count
  )
  on conflict (case_number) do update set
    debtor_name = excluded.debtor_name,
    filing_date = excluded.filing_date,
    court_district = excluded.court_district,
    chapter_type = excluded.chapter_type,
    state = excluded.state,
    estimated_assets = excluded.estimated_assets,
    estimated_liabilities = excluded.estimated_liabilities,
    estimated_creditor_count = excluded.estimated_creditor_count,
    updated_at = now()
  returning id into v_id;

  return v_id;
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_bankruptcy"("p_case_number" character varying, "p_debtor_name" character varying, "p_filing_date" "date", "p_court_district" character varying, "p_chapter_type" "public"."au_group_chapter_type", "p_state" character varying, "p_estimated_assets" numeric, "p_estimated_liabilities" numeric, "p_estimated_creditor_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_bankruptcy_from_form201"("p_bankruptcy_id" "uuid", "p_debtor_name" "text" DEFAULT NULL::"text", "p_city" "text" DEFAULT NULL::"text", "p_state" "text" DEFAULT NULL::"text", "p_court_district" "text" DEFAULT NULL::"text", "p_industry_code" "text" DEFAULT NULL::"text", "p_estimated_assets" "jsonb" DEFAULT NULL::"jsonb", "p_estimated_liabilities" "jsonb" DEFAULT NULL::"jsonb", "p_estimated_creditor_count" "jsonb" DEFAULT NULL::"jsonb", "p_confidence_score" numeric DEFAULT NULL::numeric, "p_manual_review_required" boolean DEFAULT NULL::boolean) RETURNS "uuid"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
begin
  update public.bankruptcies
  set
    debtor_name = coalesce(p_debtor_name, debtor_name),
    city = coalesce(p_city, city),
    state = coalesce(p_state, state),
    court_district = coalesce(p_court_district, court_district),
    industry_code = coalesce(p_industry_code, industry_code),
    estimated_assets_range = coalesce(p_estimated_assets, estimated_assets_range),
    estimated_liabilities_range = coalesce(p_estimated_liabilities, estimated_liabilities_range),
    estimated_creditor_count_range = coalesce(
      p_estimated_creditor_count,
      estimated_creditor_count_range
    ),
    estimated_assets = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_assets),
      estimated_assets
    ),
    estimated_liabilities = coalesce(
      public.au_group_jsonb_midpoint_usd(p_estimated_liabilities),
      estimated_liabilities
    ),
    estimated_creditor_count = coalesce(
      public.au_group_jsonb_midpoint_count(p_estimated_creditor_count),
      estimated_creditor_count
    ),
    extraction_confidence_score = coalesce(
      p_confidence_score,
      extraction_confidence_score
    ),
    manual_review_required = coalesce(manual_review_required, false)
      or coalesce(p_manual_review_required, false),
    updated_at = now()
  where id = p_bankruptcy_id;

  return p_bankruptcy_id;
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_bankruptcy_from_form201"("p_bankruptcy_id" "uuid", "p_debtor_name" "text", "p_city" "text", "p_state" "text", "p_court_district" "text", "p_industry_code" "text", "p_estimated_assets" "jsonb", "p_estimated_liabilities" "jsonb", "p_estimated_creditor_count" "jsonb", "p_confidence_score" numeric, "p_manual_review_required" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_case_status"("p_bankruptcy_id" "uuid", "p_has_creditor_matrix" boolean DEFAULT NULL::boolean, "p_has_schedule_f" boolean DEFAULT NULL::boolean, "p_has_asset_schedule" boolean DEFAULT NULL::boolean, "p_enrichment_completed" boolean DEFAULT NULL::boolean, "p_outreach_ready" boolean DEFAULT NULL::boolean, "p_lifecycle_stage" "text" DEFAULT NULL::"text") RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;

  insert into public.bankruptcy_case_status (
    bankruptcy_id,
    has_creditor_matrix,
    has_schedule_f,
    has_asset_schedule,
    enrichment_completed,
    outreach_ready,
    lifecycle_stage,
    updated_at
  )
  values (
    p_bankruptcy_id,
    coalesce(p_has_creditor_matrix, false),
    coalesce(p_has_schedule_f, false),
    coalesce(p_has_asset_schedule, false),
    coalesce(p_enrichment_completed, false),
    coalesce(p_outreach_ready, false),
    coalesce(p_lifecycle_stage, 'new'),
    now()
  )
  on conflict (bankruptcy_id) do update
  set
    has_creditor_matrix = coalesce(p_has_creditor_matrix, bankruptcy_case_status.has_creditor_matrix),
    has_schedule_f = coalesce(p_has_schedule_f, bankruptcy_case_status.has_schedule_f),
    has_asset_schedule = coalesce(p_has_asset_schedule, bankruptcy_case_status.has_asset_schedule),
    enrichment_completed = coalesce(
      p_enrichment_completed,
      bankruptcy_case_status.enrichment_completed
    ),
    outreach_ready = coalesce(p_outreach_ready, bankruptcy_case_status.outreach_ready),
    lifecycle_stage = coalesce(p_lifecycle_stage, bankruptcy_case_status.lifecycle_stage),
    updated_at = now();

  return p_bankruptcy_id;
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_case_status"("p_bankruptcy_id" "uuid", "p_has_creditor_matrix" boolean, "p_has_schedule_f" boolean, "p_has_asset_schedule" boolean, "p_enrichment_completed" boolean, "p_outreach_ready" boolean, "p_lifecycle_stage" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_docket_entries"("p_bankruptcy_id" "uuid", "p_entries" "jsonb") RETURNS integer
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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
    update public.bankruptcies set last_docket_check_at = now(), updated_at = now() where id = p_bankruptcy_id;
    return 0;
  end if;
  for v_outer in select value from jsonb_array_elements(p_entries) as t(value) loop
    if jsonb_typeof(v_outer) = 'array' then v_flat := v_flat || v_outer;
    elsif jsonb_typeof(v_outer) = 'object' then v_flat := v_flat || jsonb_build_array(v_outer);
    end if;
  end loop;
  for v_entry in select value from jsonb_array_elements(v_flat) as t(value) loop
    if jsonb_typeof(v_entry) <> 'object' then continue; end if;
    v_docket_number := coalesce(
      nullif(btrim(v_entry->>'docketEntryNumber'), ''),
      nullif(btrim(v_entry->>'docket_number'), ''),
      nullif(btrim(v_entry->>'docketNumber'), ''),
      nullif(btrim(v_entry->>'entryNumber'), ''),
      nullif(btrim(v_entry->>'docketEntryNum'), ''));
    if v_docket_number is null then continue; end if;
    v_filed_at := null;
    begin
      v_filed_at := coalesce(
        nullif(v_entry->>'dateFiled', '')::timestamptz,
        nullif(v_entry->>'filed_at', '')::timestamptz,
        nullif(v_entry->>'filingDate', '')::timestamptz);
    exception when others then v_filed_at := null; end;
    v_description := coalesce(nullif(btrim(v_entry->>'description'), ''), nullif(btrim(v_entry->>'text'), ''), nullif(btrim(v_entry->>'docketText'), ''));
    v_title := coalesce(nullif(btrim(v_entry->>'title'), ''), nullif(left(v_description, 500), ''));
    v_document_url := coalesce(nullif(btrim(v_entry->>'documentUrl'), ''), nullif(btrim(v_entry->>'document_url'), ''), nullif(btrim(v_entry->'links'->>'document'), ''), nullif(btrim(v_entry->'links'->'document'->>'href'), ''));
    insert into public.docket_entries (bankruptcy_id, docket_number, filed_at, title, description, document_url, source_type, raw_payload)
    values (p_bankruptcy_id, v_docket_number, v_filed_at, v_title, v_description, v_document_url, 'pacer', v_entry)
    on conflict (bankruptcy_id, docket_number) where docket_number is not null and btrim(docket_number) <> ''
    do update set filed_at = excluded.filed_at, title = excluded.title, description = excluded.description,
      document_url = coalesce(excluded.document_url, public.docket_entries.document_url),
      source_type = excluded.source_type, raw_payload = excluded.raw_payload;
    v_count := v_count + 1;
  end loop;
  update public.bankruptcies set last_docket_check_at = now(), updated_at = now() where id = p_bankruptcy_id;
  update public.bankruptcy_case_status set docket_last_checked_at = now(), updated_at = now() where bankruptcy_id = p_bankruptcy_id;
  return v_count;
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_docket_entries"("p_bankruptcy_id" "uuid", "p_entries" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_document_parse_result"("p_processing_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_doc_index" integer, "p_doc_key" "text", "p_parser_status" "text", "p_manual_review_required" boolean DEFAULT false, "p_s3_key" "text" DEFAULT NULL::"text", "p_document_url" "text" DEFAULT NULL::"text", "p_document_id" "text" DEFAULT NULL::"text", "p_parser_result" "jsonb" DEFAULT NULL::"jsonb", "p_parse_error" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_row public.document_parse_results;
begin
  if p_processing_job_id is null then
    raise exception 'p_processing_job_id is required' using errcode = 'P0001';
  end if;
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;
  if p_doc_key is null or btrim(p_doc_key) = '' then
    raise exception 'p_doc_key is required' using errcode = 'P0001';
  end if;

  insert into public.document_parse_results (
    processing_job_id, bankruptcy_id, doc_index, doc_key, s3_key,
    document_url, document_id, parser_status, manual_review_required,
    parser_result, parse_error, updated_at
  )
  values (
    p_processing_job_id, p_bankruptcy_id, p_doc_index, p_doc_key, p_s3_key,
    p_document_url, p_document_id, p_parser_status,
    coalesce(p_manual_review_required, false), p_parser_result, p_parse_error, now()
  )
  on conflict (processing_job_id, doc_index)
  do update set
    bankruptcy_id = excluded.bankruptcy_id,
    doc_key = excluded.doc_key,
    s3_key = excluded.s3_key,
    document_url = excluded.document_url,
    document_id = excluded.document_id,
    parser_status = excluded.parser_status,
    manual_review_required = excluded.manual_review_required,
    parser_result = excluded.parser_result,
    parse_error = excluded.parse_error,
    updated_at = now()
  returning * into v_row;

  return to_jsonb(v_row);
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_document_parse_result"("p_processing_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_doc_index" integer, "p_doc_key" "text", "p_parser_status" "text", "p_manual_review_required" boolean, "p_s3_key" "text", "p_document_url" "text", "p_document_id" "text", "p_parser_result" "jsonb", "p_parse_error" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_salesforce_account"("p_creditor_id" "uuid", "p_salesforce_account_id" character varying, "p_territory_rep" character varying DEFAULT NULL::character varying) RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_creditor_id is null then
    raise exception 'p_creditor_id is required';
  end if;
  if p_salesforce_account_id is null or length(trim(p_salesforce_account_id)) = 0 then
    raise exception 'p_salesforce_account_id is required';
  end if;

  insert into public.salesforce_accounts (
    creditor_id,
    salesforce_account_id,
    territory_rep,
    last_sync_at
  )
  values (
    p_creditor_id,
    trim(p_salesforce_account_id),
    p_territory_rep,
    now()
  )
  on conflict (creditor_id) do update
  set
    salesforce_account_id = excluded.salesforce_account_id,
    territory_rep = coalesce(excluded.territory_rep, salesforce_accounts.territory_rep),
    last_sync_at = now();
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_salesforce_account"("p_creditor_id" "uuid", "p_salesforce_account_id" character varying, "p_territory_rep" character varying) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_zoom_info_contacts"("p_creditor_id" "uuid", "p_contacts" "jsonb", "p_company_revenue" numeric DEFAULT NULL::numeric, "p_company_employee_count" integer DEFAULT NULL::integer, "p_company_industry" "text" DEFAULT NULL::"text") RETURNS integer
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_elem jsonb;
  v_count integer := 0;
  v_saved integer := 0;
begin
  if p_creditor_id is null then
    return 0;
  end if;

  delete from public.zoom_info_contacts where creditor_id = p_creditor_id;

  if p_contacts is null or jsonb_typeof(p_contacts) <> 'array' then
    return 0;
  end if;

  for v_elem in
    select value
    from jsonb_array_elements(p_contacts) as value
    order by coalesce((value->>'engagement_score')::integer, 0) desc
    limit 3
  loop
    v_count := v_count + 1;
    insert into public.zoom_info_contacts (
      creditor_id,
      full_name,
      title,
      email,
      phone,
      company_revenue,
      company_employee_count,
      company_industry,
      engagement_score
    )
    values (
      p_creditor_id,
      coalesce(nullif(trim(v_elem->>'full_name'), ''), 'Unknown'),
      nullif(trim(v_elem->>'title'), ''),
      nullif(trim(v_elem->>'email'), ''),
      nullif(trim(v_elem->>'phone'), ''),
      coalesce((v_elem->>'company_revenue')::numeric, p_company_revenue),
      coalesce((v_elem->>'company_employee_count')::integer, p_company_employee_count),
      coalesce(nullif(trim(v_elem->>'company_industry'), ''), p_company_industry),
      coalesce((v_elem->>'engagement_score')::integer, 0)
    );
    v_saved := v_saved + 1;
  end loop;

  return v_saved;
end;
$$;


ALTER FUNCTION "public"."au_group_upsert_zoom_info_contacts"("p_creditor_id" "uuid", "p_contacts" "jsonb", "p_company_revenue" numeric, "p_company_employee_count" integer, "p_company_industry" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_upsert_zoominfo_company_cache"("p_cache_key" "text", "p_company_id" "text", "p_normalized_name" "text" DEFAULT NULL::"text", "p_match_confidence" numeric DEFAULT NULL::numeric, "p_firmographics" "jsonb" DEFAULT '{}'::"jsonb", "p_raw_response" "jsonb" DEFAULT NULL::"jsonb", "p_ttl_days" integer DEFAULT 7) RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
begin
  if p_cache_key is null or trim(p_cache_key) = '' then return false; end if;
  if p_company_id is null or trim(p_company_id) = '' then return false; end if;
  insert into public.au_group_zoominfo_company_cache (
    cache_key, company_id, normalized_name, match_confidence, firmographics, raw_response, expires_at
  ) values (
    trim(p_cache_key), trim(p_company_id), nullif(trim(p_normalized_name), ''),
    p_match_confidence, coalesce(p_firmographics, '{}'::jsonb), p_raw_response,
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


ALTER FUNCTION "public"."au_group_upsert_zoominfo_company_cache"("p_cache_key" "text", "p_company_id" "text", "p_normalized_name" "text", "p_match_confidence" numeric, "p_firmographics" "jsonb", "p_raw_response" "jsonb", "p_ttl_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."au_group_zoominfo_company_url"("p_company_id" "text") RETURNS "text"
    LANGUAGE "sql" STABLE
    SET "search_path" TO 'public'
    AS $$
  select case
    when p_company_id is null or trim(p_company_id) = '' then ''
    else replace(
      public.au_group_config_text('zoominfo_company_url_template', 'https://app.zoominfo.com/#/company/{id}/overview'),
      '{id}',
      trim(p_company_id)
    )
  end;
$$;


ALTER FUNCTION "public"."au_group_zoominfo_company_url"("p_company_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_updated_at_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_updated_at_column"() OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."active_monitored_cases" AS
 SELECT "id",
    "case_number",
    "debtor_name",
    "court_id",
    "chapter_type",
    "filing_date",
    "monitoring_enabled",
    "lead_score",
    "lead_priority"
   FROM "public"."bankruptcies"
  WHERE ("monitoring_enabled" = true);


ALTER VIEW "public"."active_monitored_cases" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_company_name_rules" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "rule_type" "text" NOT NULL,
    "pattern" "text" NOT NULL,
    "replacement" "text" DEFAULT ''::"text" NOT NULL,
    "priority" integer DEFAULT 100 NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "au_group_company_name_rules_pattern_len" CHECK (("char_length"("pattern") <= 200)),
    CONSTRAINT "au_group_company_name_rules_rule_type_check" CHECK (("rule_type" = ANY (ARRAY['suffix_strip'::"text", 'alias'::"text", 'token_replace'::"text"])))
);


ALTER TABLE "public"."au_group_company_name_rules" OWNER TO "postgres";


COMMENT ON TABLE "public"."au_group_company_name_rules" IS 'KD-24: editable normalization rules (suffix strip, alias, token replace) without code deploy.';



CREATE TABLE IF NOT EXISTS "public"."au_group_company_tiers" (
    "tier" smallint NOT NULL,
    "label" "text" NOT NULL,
    "min_revenue" numeric(15,2),
    "min_employees" integer,
    "active" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "au_group_company_tiers_tier_check" CHECK ((("tier" >= 1) AND ("tier" <= 3)))
);


ALTER TABLE "public"."au_group_company_tiers" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_config_audit" (
    "id" bigint NOT NULL,
    "config_table" "text" NOT NULL,
    "action" "text" NOT NULL,
    "row_key" "text",
    "old_data" "jsonb",
    "new_data" "jsonb",
    "changed_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_config_audit" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."au_group_config_audit_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."au_group_config_audit_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."au_group_config_audit_id_seq" OWNED BY "public"."au_group_config_audit"."id";



CREATE TABLE IF NOT EXISTS "public"."au_group_court_mappings" (
    "court_id" character varying(32) NOT NULL,
    "state" character(2) NOT NULL,
    "court_district" character varying(100) NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_court_mappings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_enrich_loop_staging" (
    "job_id" "uuid" NOT NULL,
    "creditor_id" "uuid" NOT NULL,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_enrich_loop_staging" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_runtime_config" (
    "config_key" "text" NOT NULL,
    "config_value" "text" NOT NULL,
    "notes" "text",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_runtime_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_schedule_f_keywords" (
    "id" bigint NOT NULL,
    "pattern" "text" NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_schedule_f_keywords" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."au_group_schedule_f_keywords_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."au_group_schedule_f_keywords_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."au_group_schedule_f_keywords_id_seq" OWNED BY "public"."au_group_schedule_f_keywords"."id";



CREATE TABLE IF NOT EXISTS "public"."au_group_suppression_keywords" (
    "id" bigint NOT NULL,
    "pattern" "text" NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_suppression_keywords" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."au_group_suppression_keywords_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."au_group_suppression_keywords_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."au_group_suppression_keywords_id_seq" OWNED BY "public"."au_group_suppression_keywords"."id";



CREATE TABLE IF NOT EXISTS "public"."au_group_suppression_lenders" (
    "id" bigint NOT NULL,
    "pattern" "text" NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_suppression_lenders" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."au_group_suppression_lenders_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."au_group_suppression_lenders_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."au_group_suppression_lenders_id_seq" OWNED BY "public"."au_group_suppression_lenders"."id";



CREATE TABLE IF NOT EXISTS "public"."au_group_target_states" (
    "state" character(2) NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_target_states" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_territory_assignments" (
    "state" character(2) NOT NULL,
    "rep_name" character varying(100) NOT NULL,
    "salesforce_user_id" character varying(18) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_territory_assignments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."au_group_tier_contact_titles" (
    "id" bigint NOT NULL,
    "tier" smallint NOT NULL,
    "title_pattern" "text" NOT NULL,
    "sort_order" smallint DEFAULT 0 NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_tier_contact_titles" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."au_group_tier_contact_titles_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."au_group_tier_contact_titles_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."au_group_tier_contact_titles_id_seq" OWNED BY "public"."au_group_tier_contact_titles"."id";



CREATE TABLE IF NOT EXISTS "public"."au_group_zoominfo_company_cache" (
    "cache_key" "text" NOT NULL,
    "company_id" "text" NOT NULL,
    "normalized_name" "text",
    "match_confidence" numeric(5,4),
    "firmographics" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "raw_response" "jsonb",
    "expires_at" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."au_group_zoominfo_company_cache" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bankruptcy_case_status" (
    "bankruptcy_id" "uuid" NOT NULL,
    "lifecycle_stage" "text" DEFAULT 'new'::"text" NOT NULL,
    "docket_last_checked_at" timestamp with time zone,
    "latest_docket_number" integer,
    "has_schedule_f" boolean DEFAULT false,
    "has_creditor_matrix" boolean DEFAULT false,
    "has_asset_schedule" boolean DEFAULT false,
    "outreach_ready" boolean DEFAULT false,
    "enrichment_completed" boolean DEFAULT false,
    "priority_score" numeric DEFAULT 0,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."bankruptcy_case_status" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bankruptcy_creditors" (
    "bankruptcy_id" "uuid" NOT NULL,
    "creditor_id" "uuid" NOT NULL
);


ALTER TABLE "public"."bankruptcy_creditors" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bankruptcy_rss_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "unique_key" "text" NOT NULL,
    "case_number" "text" NOT NULL,
    "court_id" "text" NOT NULL,
    "rss_guid" "text",
    "event_number" "text",
    "event_type" "text",
    "raw_payload" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "bankruptcy_id" "uuid",
    "processed" boolean DEFAULT false,
    "qualified" boolean DEFAULT false
);


ALTER TABLE "public"."bankruptcy_rss_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."creditor_matrix_extractions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid",
    "document_id" "uuid",
    "creditor_count" integer DEFAULT 0 NOT NULL,
    "confidence_score" numeric(5,4),
    "manual_review_required" boolean DEFAULT false NOT NULL,
    "parser_version" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."creditor_matrix_extractions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."creditor_matrix_rows" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "extraction_id" "uuid" NOT NULL,
    "creditor_name" "text" NOT NULL,
    "address" "text",
    "claim_amount" numeric(15,2),
    "entity_type" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "source_line_numbers" integer[] DEFAULT '{}'::integer[] NOT NULL
);


ALTER TABLE "public"."creditor_matrix_rows" OWNER TO "postgres";


COMMENT ON COLUMN "public"."creditor_matrix_rows"."source_line_numbers" IS 'KD-40: source line numbers from extraction (staging audit)';



CREATE TABLE IF NOT EXISTS "public"."creditors" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" character varying(500) NOT NULL,
    "address" "text",
    "claim_amount" numeric(15,2),
    "claim_date" "date",
    "nature_of_claim" character varying(255),
    "is_company" boolean DEFAULT true NOT NULL,
    "is_contingent" boolean DEFAULT false NOT NULL,
    "is_unliquidated" boolean DEFAULT false NOT NULL,
    "is_disputed" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "normalized_name" "text",
    "source_bankruptcy_id" "uuid",
    "original_name" "text",
    "confidence_score" numeric(5,4),
    "zoominfo_company_id" "text",
    "dedup_audit" "jsonb",
    "zoominfo_match_confidence" numeric(5,4),
    "zoominfo_match_status" "text",
    "zoominfo_firmographics" "jsonb",
    "zoominfo_enriched_at" timestamp with time zone,
    "company_tier" smallint,
    "company_tier_assigned_at" timestamp with time zone,
    CONSTRAINT "creditors_company_tier_check" CHECK ((("company_tier" >= 1) AND ("company_tier" <= 3)))
);


ALTER TABLE "public"."creditors" OWNER TO "postgres";


COMMENT ON COLUMN "public"."creditors"."normalized_name" IS 'Canonical company name from enrichment; daily report uses this for company_name when set.';



COMMENT ON COLUMN "public"."creditors"."source_bankruptcy_id" IS 'Bankruptcy case where this creditor was first extracted; used when bankruptcy_creditors is empty.';



COMMENT ON COLUMN "public"."creditors"."original_name" IS 'Raw creditor name as extracted from source document before normalization.';



COMMENT ON COLUMN "public"."creditors"."confidence_score" IS 'Per-creditor extraction confidence (0–1), when available from parser/OCR.';



COMMENT ON COLUMN "public"."creditors"."zoominfo_company_id" IS 'ZoomInfo company id from SYS-03 enrichment; used for daily report profile URL.';



COMMENT ON COLUMN "public"."creditors"."dedup_audit" IS 'KD-40: fuzzy dedup audit (merged_names, source_line_numbers, dedup_group_id)';



COMMENT ON COLUMN "public"."creditors"."company_tier" IS 'FR-4.2 ZoomInfo tier: 1=Enterprise, 2=Mid-Market, 3=SMB. NULL until SYS-03 enrichment runs.';



CREATE TABLE IF NOT EXISTS "public"."docket_entries" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid" NOT NULL,
    "docket_number" "text",
    "filed_at" timestamp with time zone,
    "title" "text",
    "description" "text",
    "document_url" "text",
    "source_type" "text" DEFAULT 'rss'::"text",
    "raw_payload" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."docket_entries" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."document_parse_results" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "processing_job_id" "uuid" NOT NULL,
    "bankruptcy_id" "uuid" NOT NULL,
    "doc_index" integer NOT NULL,
    "doc_key" "text" NOT NULL,
    "s3_key" "text",
    "document_url" "text",
    "document_id" "text",
    "parser_status" "text" NOT NULL,
    "manual_review_required" boolean DEFAULT false NOT NULL,
    "parser_result" "jsonb",
    "parse_error" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."document_parse_results" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."documents" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid",
    "s3_key" "text" NOT NULL,
    "content_sha256" "text" NOT NULL,
    "page_count" integer DEFAULT 0 NOT NULL,
    "filing_type" "public"."au_group_filing_type" DEFAULT 'UNKNOWN'::"public"."au_group_filing_type" NOT NULL,
    "parse_mode" "public"."au_group_parse_mode" DEFAULT 'structured'::"public"."au_group_parse_mode" NOT NULL,
    "ocr_used" boolean DEFAULT false NOT NULL,
    "parser_version" "text" NOT NULL,
    "raw_extraction" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."documents" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."form201_extractions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid",
    "document_id" "uuid",
    "debtor_name" "text",
    "city" "text",
    "state" "text",
    "court_district" "text",
    "industry_code" "text",
    "estimated_assets" "jsonb",
    "estimated_liabilities" "jsonb",
    "estimated_creditor_count" "jsonb",
    "confidence_score" numeric(5,4),
    "manual_review_required" boolean DEFAULT false NOT NULL,
    "raw_extraction" "jsonb",
    "parser_version" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."form201_extractions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."manual_review_queue" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid",
    "document_id" "uuid",
    "review_reason" "text" NOT NULL,
    "status" "public"."au_group_review_status" DEFAULT 'pending'::"public"."au_group_review_status" NOT NULL,
    "assigned_to" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."manual_review_queue" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."pipeline_executions" (
    "id" bigint NOT NULL,
    "n8n_workflow_id" "text",
    "n8n_execution_id" "text",
    "processing_job_id" "uuid",
    "bankruptcy_id" "uuid",
    "status" "text" DEFAULT 'started'::"text" NOT NULL,
    "error_message" "text",
    "payload" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "completed_at" timestamp with time zone,
    "duration_ms" integer,
    "node_name" "text"
);


ALTER TABLE "public"."pipeline_executions" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."pipeline_executions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."pipeline_executions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."pipeline_executions_id_seq" OWNED BY "public"."pipeline_executions"."id";



CREATE TABLE IF NOT EXISTS "public"."salesforce_accounts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "creditor_id" "uuid" NOT NULL,
    "salesforce_account_id" character varying(18) NOT NULL,
    "territory_rep" character varying(100),
    "last_sync_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "sf_recency_status" character varying(60)
);


ALTER TABLE "public"."salesforce_accounts" OWNER TO "postgres";


COMMENT ON COLUMN "public"."salesforce_accounts"."sf_recency_status" IS 'FR-5.5 Salesforce-recency flag: "New Salesforce account" or "Existing activity in Salesforce". Persisted at SF-push time so the daily report does not require a live SF call.';



CREATE TABLE IF NOT EXISTS "public"."schedule_f_queue" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "bankruptcy_id" "uuid" NOT NULL,
    "status" "text" NOT NULL,
    "docket_entry_number" character varying(50),
    "page_count" integer,
    "estimated_cost" numeric(6,2),
    "last_scanned_at" timestamp with time zone,
    "detected_at" timestamp with time zone,
    "approved_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "next_scan_at" timestamp with time zone,
    "monitoring_status" "text" DEFAULT 'active'::"text",
    "schedule_f_detected" boolean DEFAULT false,
    "scan_attempts" integer DEFAULT 0,
    "priority" integer DEFAULT 5,
    "last_error" "text",
    "pacer_document_url" "text",
    "ai_processed" boolean DEFAULT false,
    "ai_summary" "jsonb",
    "pacer_favorite_added_at" timestamp with time zone,
    "rejected_at" timestamp with time zone
);


ALTER TABLE "public"."schedule_f_queue" OWNER TO "postgres";


COMMENT ON COLUMN "public"."schedule_f_queue"."approved_at" IS 'When SYS-07 diff confirmed still favorited and download approved';



COMMENT ON COLUMN "public"."schedule_f_queue"."next_scan_at" IS 'SYS-06: earliest time to include case in weekly docket scan batch';



COMMENT ON COLUMN "public"."schedule_f_queue"."ai_summary" IS 'SYS-06: detection metadata (companion docket, amended flag, truncation)';



COMMENT ON COLUMN "public"."schedule_f_queue"."pacer_favorite_added_at" IS 'When SYS-06 added this docket to PACER Case Locator reports/favorites';



COMMENT ON COLUMN "public"."schedule_f_queue"."rejected_at" IS 'When Keith unfavorited or SYS-07 diff marked rejected';



CREATE TABLE IF NOT EXISTS "public"."zoom_info_contacts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "creditor_id" "uuid" NOT NULL,
    "full_name" character varying(255) NOT NULL,
    "title" character varying(255),
    "email" character varying(255),
    "phone" character varying(50),
    "company_revenue" numeric(15,2),
    "company_employee_count" integer,
    "company_industry" character varying(255),
    "engagement_score" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."zoom_info_contacts" OWNER TO "postgres";


ALTER TABLE ONLY "public"."au_group_config_audit" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."au_group_config_audit_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."au_group_schedule_f_keywords" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."au_group_schedule_f_keywords_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."au_group_suppression_keywords" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."au_group_suppression_keywords_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."au_group_suppression_lenders" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."au_group_suppression_lenders_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."au_group_tier_contact_titles" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."au_group_tier_contact_titles_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."pipeline_executions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."pipeline_executions_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."au_group_company_name_rules"
    ADD CONSTRAINT "au_group_company_name_rules_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_company_tiers"
    ADD CONSTRAINT "au_group_company_tiers_pkey" PRIMARY KEY ("tier");



ALTER TABLE ONLY "public"."au_group_config_audit"
    ADD CONSTRAINT "au_group_config_audit_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_court_mappings"
    ADD CONSTRAINT "au_group_court_mappings_pkey" PRIMARY KEY ("court_id");



ALTER TABLE ONLY "public"."au_group_enrich_loop_staging"
    ADD CONSTRAINT "au_group_enrich_loop_staging_pkey" PRIMARY KEY ("job_id", "creditor_id");



ALTER TABLE ONLY "public"."au_group_runtime_config"
    ADD CONSTRAINT "au_group_runtime_config_pkey" PRIMARY KEY ("config_key");



ALTER TABLE ONLY "public"."au_group_schedule_f_keywords"
    ADD CONSTRAINT "au_group_schedule_f_keywords_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_suppression_keywords"
    ADD CONSTRAINT "au_group_suppression_keywords_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_suppression_lenders"
    ADD CONSTRAINT "au_group_suppression_lenders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_target_states"
    ADD CONSTRAINT "au_group_target_states_pkey" PRIMARY KEY ("state");



ALTER TABLE ONLY "public"."au_group_territory_assignments"
    ADD CONSTRAINT "au_group_territory_assignments_pkey" PRIMARY KEY ("state");



ALTER TABLE ONLY "public"."au_group_tier_contact_titles"
    ADD CONSTRAINT "au_group_tier_contact_titles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."au_group_zoominfo_company_cache"
    ADD CONSTRAINT "au_group_zoominfo_company_cache_pkey" PRIMARY KEY ("cache_key");



ALTER TABLE ONLY "public"."bankruptcies"
    ADD CONSTRAINT "bankruptcies_case_number_key" UNIQUE ("case_number");



ALTER TABLE ONLY "public"."bankruptcies"
    ADD CONSTRAINT "bankruptcies_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."bankruptcy_case_status"
    ADD CONSTRAINT "bankruptcy_case_status_pkey" PRIMARY KEY ("bankruptcy_id");



ALTER TABLE ONLY "public"."bankruptcy_creditors"
    ADD CONSTRAINT "bankruptcy_creditors_pkey" PRIMARY KEY ("bankruptcy_id", "creditor_id");



ALTER TABLE ONLY "public"."bankruptcy_rss_events"
    ADD CONSTRAINT "bankruptcy_rss_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."bankruptcy_rss_events"
    ADD CONSTRAINT "bankruptcy_rss_events_unique_key_key" UNIQUE ("unique_key");



ALTER TABLE ONLY "public"."creditor_matrix_extractions"
    ADD CONSTRAINT "creditor_matrix_extractions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."creditor_matrix_rows"
    ADD CONSTRAINT "creditor_matrix_rows_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."creditors"
    ADD CONSTRAINT "creditors_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."docket_entries"
    ADD CONSTRAINT "docket_entries_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."document_parse_results"
    ADD CONSTRAINT "document_parse_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."document_parse_results"
    ADD CONSTRAINT "document_parse_results_processing_job_id_doc_index_key" UNIQUE ("processing_job_id", "doc_index");



ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_content_sha256_parser_version_key" UNIQUE ("content_sha256", "parser_version");



ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."form201_extractions"
    ADD CONSTRAINT "form201_extractions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."manual_review_queue"
    ADD CONSTRAINT "manual_review_queue_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pipeline_executions"
    ADD CONSTRAINT "pipeline_executions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."processing_jobs"
    ADD CONSTRAINT "processing_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."salesforce_accounts"
    ADD CONSTRAINT "salesforce_accounts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."salesforce_accounts"
    ADD CONSTRAINT "salesforce_accounts_salesforce_account_id_key" UNIQUE ("salesforce_account_id");



ALTER TABLE ONLY "public"."schedule_f_queue"
    ADD CONSTRAINT "schedule_f_queue_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."zoom_info_contacts"
    ADD CONSTRAINT "zoom_info_contacts_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_au_group_company_name_rules_priority" ON "public"."au_group_company_name_rules" USING "btree" ("enabled", "priority", "id");



CREATE INDEX "idx_au_group_enrich_loop_staging_job" ON "public"."au_group_enrich_loop_staging" USING "btree" ("job_id");



CREATE INDEX "idx_au_group_tier_contact_titles_tier" ON "public"."au_group_tier_contact_titles" USING "btree" ("tier", "sort_order") WHERE ("active" IS TRUE);



CREATE UNIQUE INDEX "idx_au_group_tier_contact_titles_tier_pattern" ON "public"."au_group_tier_contact_titles" USING "btree" ("tier", "title_pattern");



CREATE INDEX "idx_au_group_zoominfo_company_cache_expires" ON "public"."au_group_zoominfo_company_cache" USING "btree" ("expires_at");



CREATE INDEX "idx_bankruptcies_case_number" ON "public"."bankruptcies" USING "btree" ("case_number");



CREATE INDEX "idx_bankruptcies_court_id" ON "public"."bankruptcies" USING "btree" ("court_id");



CREATE INDEX "idx_bankruptcies_filing_date" ON "public"."bankruptcies" USING "btree" ("filing_date");



CREATE INDEX "idx_bankruptcies_forms_downloaded_at" ON "public"."bankruptcies" USING "btree" ("forms_downloaded_at");



CREATE INDEX "idx_bankruptcies_monitoring" ON "public"."bankruptcies" USING "btree" ("monitoring_enabled");



CREATE INDEX "idx_bankruptcies_state" ON "public"."bankruptcies" USING "btree" ("state");



CREATE INDEX "idx_creditor_matrix_rows_extraction_id" ON "public"."creditor_matrix_rows" USING "btree" ("extraction_id");



CREATE INDEX "idx_creditors_name_gin" ON "public"."creditors" USING "gin" ("name" "extensions"."gin_trgm_ops");



CREATE INDEX "idx_creditors_normalized_name" ON "public"."creditors" USING "btree" ("normalized_name");



CREATE UNIQUE INDEX "idx_creditors_normalized_name_address" ON "public"."creditors" USING "btree" ("lower"(TRIM(BOTH FROM "name")), "lower"(TRIM(BOTH FROM COALESCE("address", ''::"text"))));



CREATE INDEX "idx_creditors_source_bankruptcy_id" ON "public"."creditors" USING "btree" ("source_bankruptcy_id") WHERE ("source_bankruptcy_id" IS NOT NULL);



CREATE INDEX "idx_docket_entries_bankruptcy" ON "public"."docket_entries" USING "btree" ("bankruptcy_id");



CREATE UNIQUE INDEX "idx_docket_entries_bankruptcy_docket_number_unique" ON "public"."docket_entries" USING "btree" ("bankruptcy_id", "docket_number") WHERE (("docket_number" IS NOT NULL) AND ("btrim"("docket_number") <> ''::"text"));



CREATE INDEX "idx_docket_entries_docket_number" ON "public"."docket_entries" USING "btree" ("docket_number");



CREATE INDEX "idx_document_parse_results_bankruptcy" ON "public"."document_parse_results" USING "btree" ("bankruptcy_id");



CREATE INDEX "idx_document_parse_results_job" ON "public"."document_parse_results" USING "btree" ("processing_job_id");



CREATE INDEX "idx_documents_bankruptcy_id" ON "public"."documents" USING "btree" ("bankruptcy_id");



CREATE INDEX "idx_documents_filing_type" ON "public"."documents" USING "btree" ("filing_type");



CREATE INDEX "idx_form201_extractions_bankruptcy_id" ON "public"."form201_extractions" USING "btree" ("bankruptcy_id");



CREATE INDEX "idx_manual_review_queue_status" ON "public"."manual_review_queue" USING "btree" ("status");



CREATE INDEX "idx_pipeline_executions_created_at" ON "public"."pipeline_executions" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_pipeline_executions_n8n_execution" ON "public"."pipeline_executions" USING "btree" ("n8n_execution_id") WHERE ("n8n_execution_id" IS NOT NULL);



CREATE INDEX "idx_pipeline_executions_status" ON "public"."pipeline_executions" USING "btree" ("status");



CREATE INDEX "idx_processing_jobs_bankruptcy" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id");



CREATE INDEX "idx_processing_jobs_bankruptcy_id" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id");



CREATE UNIQUE INDEX "idx_processing_jobs_one_queued_per_bankruptcy_type" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id", "job_type") WHERE ("status" = 'queued'::"public"."processing_job_status");



CREATE UNIQUE INDEX "idx_processing_jobs_one_running_doc_intel" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id", "job_type") WHERE (("status" = 'running'::"public"."processing_job_status") AND ("job_type" = 'document_intelligence'::"public"."au_group_job_type"));



CREATE UNIQUE INDEX "idx_processing_jobs_one_running_document_parse" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id") WHERE (("status" = 'running'::"public"."processing_job_status") AND ("job_type" = 'document_parse'::"public"."au_group_job_type"));



CREATE UNIQUE INDEX "idx_processing_jobs_one_running_pacer_poll" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id") WHERE (("status" = 'running'::"public"."processing_job_status") AND ("job_type" = 'pacer_poll'::"public"."au_group_job_type"));



CREATE UNIQUE INDEX "idx_processing_jobs_one_running_salesforce_push" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id") WHERE (("status" = 'running'::"public"."processing_job_status") AND ("job_type" = 'salesforce_push'::"public"."au_group_job_type"));



CREATE UNIQUE INDEX "idx_processing_jobs_one_running_zoom_info_enrich" ON "public"."processing_jobs" USING "btree" ("bankruptcy_id") WHERE (("status" = 'running'::"public"."processing_job_status") AND ("job_type" = 'zoom_info_enrich'::"public"."au_group_job_type"));



CREATE INDEX "idx_processing_jobs_status" ON "public"."processing_jobs" USING "btree" ("status");



CREATE UNIQUE INDEX "idx_rss_event_dedupe" ON "public"."bankruptcy_rss_events" USING "btree" ("case_number", "court_id", "event_number");



CREATE INDEX "idx_rss_events_bankruptcy_id" ON "public"."bankruptcy_rss_events" USING "btree" ("bankruptcy_id");



CREATE INDEX "idx_rss_events_unprocessed" ON "public"."bankruptcy_rss_events" USING "btree" ("created_at") WHERE ("processed" IS NOT TRUE);



CREATE INDEX "idx_salesforce_accounts_creditor_id" ON "public"."salesforce_accounts" USING "btree" ("creditor_id");



CREATE UNIQUE INDEX "idx_salesforce_accounts_creditor_id_unique" ON "public"."salesforce_accounts" USING "btree" ("creditor_id");



CREATE INDEX "idx_schedule_f_queue_monitoring" ON "public"."schedule_f_queue" USING "btree" ("monitoring_status");



CREATE INDEX "idx_schedule_f_queue_monitoring_active" ON "public"."schedule_f_queue" USING "btree" ("status", "monitoring_status") WHERE ("monitoring_status" = 'active'::"text");



CREATE INDEX "idx_schedule_f_queue_next_scan" ON "public"."schedule_f_queue" USING "btree" ("next_scan_at");



CREATE INDEX "idx_schedule_f_queue_status" ON "public"."schedule_f_queue" USING "btree" ("status");



CREATE INDEX "idx_zoom_info_contacts_creditor_id" ON "public"."zoom_info_contacts" USING "btree" ("creditor_id");



CREATE UNIQUE INDEX "uq_au_group_tier_contact_titles_tier_title" ON "public"."au_group_tier_contact_titles" USING "btree" ("tier", "title_pattern");



CREATE OR REPLACE TRIGGER "au_group_company_name_rules_set_updated_at" BEFORE UPDATE ON "public"."au_group_company_name_rules" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_company_tiers_set_updated_at" BEFORE UPDATE ON "public"."au_group_company_tiers" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_court_mappings_set_updated_at" BEFORE UPDATE ON "public"."au_group_court_mappings" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_runtime_config_set_updated_at" BEFORE UPDATE ON "public"."au_group_runtime_config" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_target_states_audit" AFTER INSERT OR DELETE OR UPDATE ON "public"."au_group_target_states" FOR EACH ROW EXECUTE FUNCTION "public"."au_group_audit_config_change"();



CREATE OR REPLACE TRIGGER "au_group_target_states_set_updated_at" BEFORE UPDATE ON "public"."au_group_target_states" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_territory_assignments_set_updated_at" BEFORE UPDATE ON "public"."au_group_territory_assignments" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "au_group_zoominfo_company_cache_set_updated_at" BEFORE UPDATE ON "public"."au_group_zoominfo_company_cache" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "bankruptcies_set_updated_at" BEFORE UPDATE ON "public"."bankruptcies" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "creditors_set_updated_at" BEFORE UPDATE ON "public"."creditors" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "documents_set_updated_at" BEFORE UPDATE ON "public"."documents" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "manual_review_queue_set_updated_at" BEFORE UPDATE ON "public"."manual_review_queue" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "update_bankruptcies_updated_at" BEFORE UPDATE ON "public"."bankruptcies" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_creditors_updated_at" BEFORE UPDATE ON "public"."creditors" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



ALTER TABLE ONLY "public"."au_group_tier_contact_titles"
    ADD CONSTRAINT "au_group_tier_contact_titles_tier_fkey" FOREIGN KEY ("tier") REFERENCES "public"."au_group_company_tiers"("tier") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."bankruptcy_case_status"
    ADD CONSTRAINT "bankruptcy_case_status_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."bankruptcy_creditors"
    ADD CONSTRAINT "bankruptcy_creditors_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."bankruptcy_creditors"
    ADD CONSTRAINT "bankruptcy_creditors_creditor_id_fkey" FOREIGN KEY ("creditor_id") REFERENCES "public"."creditors"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."bankruptcy_rss_events"
    ADD CONSTRAINT "bankruptcy_rss_events_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id");



ALTER TABLE ONLY "public"."creditor_matrix_extractions"
    ADD CONSTRAINT "creditor_matrix_extractions_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."creditor_matrix_extractions"
    ADD CONSTRAINT "creditor_matrix_extractions_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."creditor_matrix_rows"
    ADD CONSTRAINT "creditor_matrix_rows_extraction_id_fkey" FOREIGN KEY ("extraction_id") REFERENCES "public"."creditor_matrix_extractions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."creditors"
    ADD CONSTRAINT "creditors_source_bankruptcy_id_fkey" FOREIGN KEY ("source_bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."docket_entries"
    ADD CONSTRAINT "docket_entries_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."document_parse_results"
    ADD CONSTRAINT "document_parse_results_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."document_parse_results"
    ADD CONSTRAINT "document_parse_results_processing_job_id_fkey" FOREIGN KEY ("processing_job_id") REFERENCES "public"."processing_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."form201_extractions"
    ADD CONSTRAINT "form201_extractions_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."form201_extractions"
    ADD CONSTRAINT "form201_extractions_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."manual_review_queue"
    ADD CONSTRAINT "manual_review_queue_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."manual_review_queue"
    ADD CONSTRAINT "manual_review_queue_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."pipeline_executions"
    ADD CONSTRAINT "pipeline_executions_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."pipeline_executions"
    ADD CONSTRAINT "pipeline_executions_processing_job_id_fkey" FOREIGN KEY ("processing_job_id") REFERENCES "public"."processing_jobs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."processing_jobs"
    ADD CONSTRAINT "processing_jobs_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id");



ALTER TABLE ONLY "public"."salesforce_accounts"
    ADD CONSTRAINT "salesforce_accounts_creditor_id_fkey" FOREIGN KEY ("creditor_id") REFERENCES "public"."creditors"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."schedule_f_queue"
    ADD CONSTRAINT "schedule_f_queue_bankruptcy_id_fkey" FOREIGN KEY ("bankruptcy_id") REFERENCES "public"."bankruptcies"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."zoom_info_contacts"
    ADD CONSTRAINT "zoom_info_contacts_creditor_id_fkey" FOREIGN KEY ("creditor_id") REFERENCES "public"."creditors"("id") ON DELETE CASCADE;



ALTER TABLE "public"."au_group_company_name_rules" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_company_name_rules_deny_public" ON "public"."au_group_company_name_rules" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_company_tiers" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_company_tiers_deny_public" ON "public"."au_group_company_tiers" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_config_audit" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_config_audit_deny_public" ON "public"."au_group_config_audit" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_court_mappings" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_court_mappings_deny_public" ON "public"."au_group_court_mappings" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_enrich_loop_staging" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_enrich_loop_staging_deny_public" ON "public"."au_group_enrich_loop_staging" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_runtime_config" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_runtime_config_deny_public" ON "public"."au_group_runtime_config" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_schedule_f_keywords" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_schedule_f_keywords_deny_public" ON "public"."au_group_schedule_f_keywords" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_suppression_keywords" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."au_group_suppression_lenders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."au_group_target_states" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."au_group_territory_assignments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."au_group_tier_contact_titles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "au_group_tier_contact_titles_deny_public" ON "public"."au_group_tier_contact_titles" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."au_group_zoominfo_company_cache" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."bankruptcies" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."bankruptcy_case_status" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."bankruptcy_creditors" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."bankruptcy_rss_events" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "bankruptcy_rss_events_deny_public" ON "public"."bankruptcy_rss_events" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."creditor_matrix_extractions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "creditor_matrix_extractions_deny_public" ON "public"."creditor_matrix_extractions" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."creditor_matrix_rows" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "creditor_matrix_rows_deny_public" ON "public"."creditor_matrix_rows" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."creditors" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."docket_entries" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."document_parse_results" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "document_parse_results_deny_public" ON "public"."document_parse_results" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."documents" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "documents_deny_public" ON "public"."documents" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."form201_extractions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "form201_extractions_deny_public" ON "public"."form201_extractions" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."manual_review_queue" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "manual_review_queue_deny_public" ON "public"."manual_review_queue" AS RESTRICTIVE TO "authenticated", "anon" USING (false) WITH CHECK (false);



ALTER TABLE "public"."pipeline_executions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."processing_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."salesforce_accounts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."schedule_f_queue" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."zoom_info_contacts" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_acquire_processing_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type", "p_stale_interval" interval) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_acquire_processing_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type", "p_stale_interval" interval) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_active_target_states"("p_states" "text"[]) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_active_target_states"("p_states" "text"[]) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_audit_config_change"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_audit_config_change"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_build_lookup_context"("p_row" "jsonb", "p_ctx" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_build_lookup_context"("p_row" "jsonb", "p_ctx" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_check_repeat_exposure"("p_creditor_id" "uuid", "p_threshold" integer, "p_window_months" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_check_repeat_exposure"("p_creditor_id" "uuid", "p_threshold" integer, "p_window_months" integer) TO "service_role";



GRANT ALL ON TABLE "public"."processing_jobs" TO "anon";
GRANT ALL ON TABLE "public"."processing_jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."processing_jobs" TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") FROM PUBLIC;
REVOKE ALL ON FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") FROM "anon";
REVOKE ALL ON FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") FROM "authenticated";
GRANT ALL ON FUNCTION "public"."au_group_claim_job"("p_job_type" "public"."au_group_job_type") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_classify_company_tier"("p_revenue" numeric, "p_employees" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_classify_company_tier"("p_revenue" numeric, "p_employees" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_company_lookup_cache_key"("p_name" "text", "p_address" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_company_lookup_cache_key"("p_name" "text", "p_address" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_company_lookup_prepare"("p_name" "text", "p_address" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_company_lookup_prepare"("p_name" "text", "p_address" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_config_bool"("p_key" "text", "p_default" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_config_bool"("p_key" "text", "p_default" boolean) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_config_int"("p_key" "text", "p_default" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_config_int"("p_key" "text", "p_default" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_config_text"("p_key" "text", "p_default" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_config_text"("p_key" "text", "p_default" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_count_company_creditors"("p_bankruptcy_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_count_company_creditors"("p_bankruptcy_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_creditor_pipeline_status"("p_creditor_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_creditor_pipeline_status"("p_creditor_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) FROM PUBLIC;
REVOKE ALL ON FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) FROM "anon";
REVOKE ALL ON FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) FROM "authenticated";
GRANT ALL ON FUNCTION "public"."au_group_daily_creditor_report_grouped"("p_since" timestamp with time zone) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_daily_creditor_report_rows"("p_since" timestamp with time zone) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_daily_creditor_report_rows"("p_since" timestamp with time zone) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_daily_pipeline_summary"("p_since" timestamp with time zone) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_daily_pipeline_summary"("p_since" timestamp with time zone) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_diff_pacer_favorites"("p_favorites" "jsonb", "p_bankruptcy_ids" "uuid"[]) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_diff_pacer_favorites"("p_favorites" "jsonb", "p_bankruptcy_ids" "uuid"[]) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") FROM PUBLIC;
REVOKE ALL ON FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") FROM "anon";
REVOKE ALL ON FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") FROM "authenticated";
GRANT ALL ON FUNCTION "public"."au_group_enqueue_job"("p_bankruptcy_id" "uuid", "p_job_type" "public"."au_group_job_type") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_enrich_loop_finalize"("p_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_pipeline_execution_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_enrich_loop_finalize"("p_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_pipeline_execution_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_enrich_loop_push"("p_job_id" "uuid", "p_creditor_id" "uuid", "p_result" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_enrich_loop_push"("p_job_id" "uuid", "p_creditor_id" "uuid", "p_result" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_evaluate_outreach_gates"("p_creditor_id" "uuid", "p_suppress" boolean, "p_dnc" boolean, "p_active_engagement" boolean, "p_repeat_threshold" integer, "p_repeat_window_months" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_evaluate_outreach_gates"("p_creditor_id" "uuid", "p_suppress" boolean, "p_dnc" boolean, "p_active_engagement" boolean, "p_repeat_threshold" integer, "p_repeat_window_months" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_expand_import_rows"("p_body" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_expand_import_rows"("p_body" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_fail_stale_processing_jobs"("p_max_age" interval) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_fail_stale_processing_jobs"("p_max_age" interval) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_finalize_document_job"("p_job_id" "uuid", "p_pipeline_execution_id" "uuid", "p_schedule_f_queue_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_finalize_document_job"("p_job_id" "uuid", "p_pipeline_execution_id" "uuid", "p_schedule_f_queue_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_get_runtime_config"("p_key" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_get_runtime_config"("p_key" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_get_zoominfo_company_cache"("p_cache_key" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_get_zoominfo_company_cache"("p_cache_key" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_is_junk_creditor_name"("p_name" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_is_junk_creditor_name"("p_name" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_is_suppressed_creditor_name"("p_name" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_is_suppressed_creditor_name"("p_name" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_is_target_state"("p_state" "text", "p_states" "text"[]) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_is_target_state"("p_state" "text", "p_states" "text"[]) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_jsonb_midpoint_count"("range" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_jsonb_midpoint_count"("range" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_jsonb_midpoint_usd"("range" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_jsonb_midpoint_usd"("range" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_link_document_bankruptcy"("p_document_id" "uuid", "p_bankruptcy_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_link_document_bankruptcy"("p_document_id" "uuid", "p_bankruptcy_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_company_creditors"("p_bankruptcy_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_company_creditors"("p_bankruptcy_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_contact_titles"("p_tier" smallint, "p_include_fallback" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_contact_titles"("p_tier" smallint, "p_include_fallback" boolean) TO "service_role";



GRANT ALL ON TABLE "public"."bankruptcies" TO "anon";
GRANT ALL ON TABLE "public"."bankruptcies" TO "authenticated";
GRANT ALL ON TABLE "public"."bankruptcies" TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_pacer_poll_candidates"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_pacer_poll_candidates"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_pacer_poll_candidates"("p_limit" integer, "p_states" "text"[]) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_pacer_poll_candidates"("p_limit" integer, "p_states" "text"[]) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_target_states"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_target_states"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_list_tier_contact_titles"("p_tier" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_list_tier_contact_titles"("p_tier" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_merge_creditor_matrix"("p_bankruptcy_id" "uuid", "p_creditors" "jsonb", "p_confidence_score" numeric) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_merge_creditor_matrix"("p_bankruptcy_id" "uuid", "p_creditors" "jsonb", "p_confidence_score" numeric) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_normalize_company_name"("p_name" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_normalize_company_name"("p_name" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_normalize_rss_item"("p_item" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_normalize_rss_item"("p_item" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_normalize_rss_items"("p_items" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_normalize_rss_items"("p_items" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_normalize_zoominfo_company_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_normalize_zoominfo_company_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_normalize_zoominfo_contact_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_normalize_zoominfo_contact_response"("p_body" "jsonb", "p_ctx" "jsonb", "p_status_code" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_parse_creditor_city"("p_address" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_parse_creditor_city"("p_address" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_parse_creditor_state"("p_address" "text", "p_fallback_state" character) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_parse_creditor_state"("p_address" "text", "p_fallback_state" character) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_pick_document_parse_handoff"("p_bankruptcy_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_pick_document_parse_handoff"("p_bankruptcy_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_resolve_court_and_target_state"("p_court_id" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_resolve_court_and_target_state"("p_court_id" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_resolve_court_mapping"("p_court_id" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_resolve_court_mapping"("p_court_id" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_resolve_manual_review"("p_review_id" "uuid", "p_resolved_by" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_resolve_manual_review"("p_review_id" "uuid", "p_resolved_by" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_resolve_territory_rep"("p_state" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_resolve_territory_rep"("p_state" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_safe_numeric"("p_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_safe_numeric"("p_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_schedule_f_keyword_hit"("p_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_schedule_f_keyword_hit"("p_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_set_creditor_company_tier"("p_creditor_id" "uuid", "p_tier" smallint, "p_bankruptcy_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_set_creditor_company_tier"("p_creditor_id" "uuid", "p_tier" smallint, "p_bankruptcy_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_set_creditor_zoominfo_company_id"("p_creditor_id" "uuid", "p_company_id" "text", "p_match_confidence" numeric, "p_normalized_name" "text", "p_match_status" "text", "p_firmographics" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_set_creditor_zoominfo_company_id"("p_creditor_id" "uuid", "p_company_id" "text", "p_match_confidence" numeric, "p_normalized_name" "text", "p_match_status" "text", "p_firmographics" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_bankruptcy"("p_case_number" character varying, "p_debtor_name" character varying, "p_filing_date" "date", "p_court_district" character varying, "p_chapter_type" "public"."au_group_chapter_type", "p_state" character varying, "p_estimated_assets" numeric, "p_estimated_liabilities" numeric, "p_estimated_creditor_count" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_bankruptcy"("p_case_number" character varying, "p_debtor_name" character varying, "p_filing_date" "date", "p_court_district" character varying, "p_chapter_type" "public"."au_group_chapter_type", "p_state" character varying, "p_estimated_assets" numeric, "p_estimated_liabilities" numeric, "p_estimated_creditor_count" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_bankruptcy_from_form201"("p_bankruptcy_id" "uuid", "p_debtor_name" "text", "p_city" "text", "p_state" "text", "p_court_district" "text", "p_industry_code" "text", "p_estimated_assets" "jsonb", "p_estimated_liabilities" "jsonb", "p_estimated_creditor_count" "jsonb", "p_confidence_score" numeric, "p_manual_review_required" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_bankruptcy_from_form201"("p_bankruptcy_id" "uuid", "p_debtor_name" "text", "p_city" "text", "p_state" "text", "p_court_district" "text", "p_industry_code" "text", "p_estimated_assets" "jsonb", "p_estimated_liabilities" "jsonb", "p_estimated_creditor_count" "jsonb", "p_confidence_score" numeric, "p_manual_review_required" boolean) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_case_status"("p_bankruptcy_id" "uuid", "p_has_creditor_matrix" boolean, "p_has_schedule_f" boolean, "p_has_asset_schedule" boolean, "p_enrichment_completed" boolean, "p_outreach_ready" boolean, "p_lifecycle_stage" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_case_status"("p_bankruptcy_id" "uuid", "p_has_creditor_matrix" boolean, "p_has_schedule_f" boolean, "p_has_asset_schedule" boolean, "p_enrichment_completed" boolean, "p_outreach_ready" boolean, "p_lifecycle_stage" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_docket_entries"("p_bankruptcy_id" "uuid", "p_entries" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_docket_entries"("p_bankruptcy_id" "uuid", "p_entries" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_document_parse_result"("p_processing_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_doc_index" integer, "p_doc_key" "text", "p_parser_status" "text", "p_manual_review_required" boolean, "p_s3_key" "text", "p_document_url" "text", "p_document_id" "text", "p_parser_result" "jsonb", "p_parse_error" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_document_parse_result"("p_processing_job_id" "uuid", "p_bankruptcy_id" "uuid", "p_doc_index" integer, "p_doc_key" "text", "p_parser_status" "text", "p_manual_review_required" boolean, "p_s3_key" "text", "p_document_url" "text", "p_document_id" "text", "p_parser_result" "jsonb", "p_parse_error" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_salesforce_account"("p_creditor_id" "uuid", "p_salesforce_account_id" character varying, "p_territory_rep" character varying) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_salesforce_account"("p_creditor_id" "uuid", "p_salesforce_account_id" character varying, "p_territory_rep" character varying) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_zoom_info_contacts"("p_creditor_id" "uuid", "p_contacts" "jsonb", "p_company_revenue" numeric, "p_company_employee_count" integer, "p_company_industry" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_zoom_info_contacts"("p_creditor_id" "uuid", "p_contacts" "jsonb", "p_company_revenue" numeric, "p_company_employee_count" integer, "p_company_industry" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_upsert_zoominfo_company_cache"("p_cache_key" "text", "p_company_id" "text", "p_normalized_name" "text", "p_match_confidence" numeric, "p_firmographics" "jsonb", "p_raw_response" "jsonb", "p_ttl_days" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_upsert_zoominfo_company_cache"("p_cache_key" "text", "p_company_id" "text", "p_normalized_name" "text", "p_match_confidence" numeric, "p_firmographics" "jsonb", "p_raw_response" "jsonb", "p_ttl_days" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."au_group_zoominfo_company_url"("p_company_id" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."au_group_zoominfo_company_url"("p_company_id" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "service_role";



GRANT ALL ON TABLE "public"."active_monitored_cases" TO "anon";
GRANT ALL ON TABLE "public"."active_monitored_cases" TO "authenticated";
GRANT ALL ON TABLE "public"."active_monitored_cases" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_company_name_rules" TO "anon";
GRANT ALL ON TABLE "public"."au_group_company_name_rules" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_company_name_rules" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_company_tiers" TO "anon";
GRANT ALL ON TABLE "public"."au_group_company_tiers" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_company_tiers" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_config_audit" TO "anon";
GRANT ALL ON TABLE "public"."au_group_config_audit" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_config_audit" TO "service_role";



GRANT ALL ON SEQUENCE "public"."au_group_config_audit_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."au_group_config_audit_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."au_group_config_audit_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_court_mappings" TO "anon";
GRANT ALL ON TABLE "public"."au_group_court_mappings" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_court_mappings" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_enrich_loop_staging" TO "anon";
GRANT ALL ON TABLE "public"."au_group_enrich_loop_staging" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_enrich_loop_staging" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_runtime_config" TO "anon";
GRANT ALL ON TABLE "public"."au_group_runtime_config" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_runtime_config" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_schedule_f_keywords" TO "anon";
GRANT ALL ON TABLE "public"."au_group_schedule_f_keywords" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_schedule_f_keywords" TO "service_role";



GRANT ALL ON SEQUENCE "public"."au_group_schedule_f_keywords_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."au_group_schedule_f_keywords_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."au_group_schedule_f_keywords_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_suppression_keywords" TO "anon";
GRANT ALL ON TABLE "public"."au_group_suppression_keywords" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_suppression_keywords" TO "service_role";



GRANT ALL ON SEQUENCE "public"."au_group_suppression_keywords_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."au_group_suppression_keywords_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."au_group_suppression_keywords_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_suppression_lenders" TO "anon";
GRANT ALL ON TABLE "public"."au_group_suppression_lenders" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_suppression_lenders" TO "service_role";



GRANT ALL ON SEQUENCE "public"."au_group_suppression_lenders_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."au_group_suppression_lenders_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."au_group_suppression_lenders_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_target_states" TO "anon";
GRANT ALL ON TABLE "public"."au_group_target_states" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_target_states" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_territory_assignments" TO "anon";
GRANT ALL ON TABLE "public"."au_group_territory_assignments" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_territory_assignments" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_tier_contact_titles" TO "anon";
GRANT ALL ON TABLE "public"."au_group_tier_contact_titles" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_tier_contact_titles" TO "service_role";



GRANT ALL ON SEQUENCE "public"."au_group_tier_contact_titles_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."au_group_tier_contact_titles_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."au_group_tier_contact_titles_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."au_group_zoominfo_company_cache" TO "anon";
GRANT ALL ON TABLE "public"."au_group_zoominfo_company_cache" TO "authenticated";
GRANT ALL ON TABLE "public"."au_group_zoominfo_company_cache" TO "service_role";



GRANT ALL ON TABLE "public"."bankruptcy_case_status" TO "anon";
GRANT ALL ON TABLE "public"."bankruptcy_case_status" TO "authenticated";
GRANT ALL ON TABLE "public"."bankruptcy_case_status" TO "service_role";



GRANT ALL ON TABLE "public"."bankruptcy_creditors" TO "anon";
GRANT ALL ON TABLE "public"."bankruptcy_creditors" TO "authenticated";
GRANT ALL ON TABLE "public"."bankruptcy_creditors" TO "service_role";



GRANT ALL ON TABLE "public"."bankruptcy_rss_events" TO "anon";
GRANT ALL ON TABLE "public"."bankruptcy_rss_events" TO "authenticated";
GRANT ALL ON TABLE "public"."bankruptcy_rss_events" TO "service_role";



GRANT ALL ON TABLE "public"."creditor_matrix_extractions" TO "anon";
GRANT ALL ON TABLE "public"."creditor_matrix_extractions" TO "authenticated";
GRANT ALL ON TABLE "public"."creditor_matrix_extractions" TO "service_role";



GRANT ALL ON TABLE "public"."creditor_matrix_rows" TO "anon";
GRANT ALL ON TABLE "public"."creditor_matrix_rows" TO "authenticated";
GRANT ALL ON TABLE "public"."creditor_matrix_rows" TO "service_role";



GRANT ALL ON TABLE "public"."creditors" TO "anon";
GRANT ALL ON TABLE "public"."creditors" TO "authenticated";
GRANT ALL ON TABLE "public"."creditors" TO "service_role";



GRANT ALL ON TABLE "public"."docket_entries" TO "anon";
GRANT ALL ON TABLE "public"."docket_entries" TO "authenticated";
GRANT ALL ON TABLE "public"."docket_entries" TO "service_role";



GRANT ALL ON TABLE "public"."document_parse_results" TO "anon";
GRANT ALL ON TABLE "public"."document_parse_results" TO "authenticated";
GRANT ALL ON TABLE "public"."document_parse_results" TO "service_role";



GRANT ALL ON TABLE "public"."documents" TO "anon";
GRANT ALL ON TABLE "public"."documents" TO "authenticated";
GRANT ALL ON TABLE "public"."documents" TO "service_role";



GRANT ALL ON TABLE "public"."form201_extractions" TO "anon";
GRANT ALL ON TABLE "public"."form201_extractions" TO "authenticated";
GRANT ALL ON TABLE "public"."form201_extractions" TO "service_role";



GRANT ALL ON TABLE "public"."manual_review_queue" TO "anon";
GRANT ALL ON TABLE "public"."manual_review_queue" TO "authenticated";
GRANT ALL ON TABLE "public"."manual_review_queue" TO "service_role";



GRANT ALL ON TABLE "public"."pipeline_executions" TO "anon";
GRANT ALL ON TABLE "public"."pipeline_executions" TO "authenticated";
GRANT ALL ON TABLE "public"."pipeline_executions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."pipeline_executions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."pipeline_executions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."pipeline_executions_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."salesforce_accounts" TO "anon";
GRANT ALL ON TABLE "public"."salesforce_accounts" TO "authenticated";
GRANT ALL ON TABLE "public"."salesforce_accounts" TO "service_role";



GRANT ALL ON TABLE "public"."schedule_f_queue" TO "anon";
GRANT ALL ON TABLE "public"."schedule_f_queue" TO "authenticated";
GRANT ALL ON TABLE "public"."schedule_f_queue" TO "service_role";



GRANT ALL ON TABLE "public"."zoom_info_contacts" TO "anon";
GRANT ALL ON TABLE "public"."zoom_info_contacts" TO "authenticated";
GRANT ALL ON TABLE "public"."zoom_info_contacts" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







