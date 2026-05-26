-- SYS-09 audit fixes: runtime config (no static labels/URLs/thresholds), lateral bankruptcy
-- state for address parsing, pending-enrichment status, zoominfo company id RPC, orphan junk cleanup.

-- Config helpers (defaults when key missing)
create or replace function public.au_group_config_text(p_key text, p_default text)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    nullif(trim(public.au_group_get_runtime_config(p_key)), ''),
    p_default
  );
$$;

create or replace function public.au_group_config_int(p_key text, p_default integer)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    nullif(trim(public.au_group_get_runtime_config(p_key)), '')::integer,
    p_default
  );
$$;

grant execute on function public.au_group_config_text (text, text) to service_role;
grant execute on function public.au_group_config_int (text, integer) to service_role;
revoke execute on function public.au_group_config_text (text, text) from public;
revoke execute on function public.au_group_config_int (text, integer) from public;

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('daily_report_window_hours', '24', 'Default lookback when p_since omitted on daily sheet RPC'),
  ('daily_report_status_new', 'New', 'Sheet status: creditor parsed, not yet enriched'),
  ('daily_report_status_pending_enrichment', 'Pending Enrichment', 'Sheet status: zoom_info_enrich job pending/running'),
  ('daily_report_status_enriched', 'ZoomInfo Enriched', 'Sheet status: zoom_info_contacts exist'),
  ('daily_report_status_sf_synced', 'Salesforce Synced', 'Sheet status: salesforce_accounts row exists'),
  ('daily_report_status_enrich_failed', 'Enrichment Failed', 'Sheet status: zoom_info_enrich job failed'),
  ('zoominfo_company_url_template', 'https://app.zoominfo.com/#/company/{id}/overview', 'Replace {id} with zoominfo company id'),
  ('creditor_name_min_length', '3', 'Junk filter: min name length (match parser Settings default)'),
  ('creditor_line_number_max_digits', '3', 'Junk filter: max digits for line-number false positives')
on conflict (config_key) do nothing;

-- Junk filter: read thresholds from runtime config (regex lists stay in function body)
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
  v_min_length := public.au_group_config_int('creditor_name_min_length', 3);
  v_max_line_digits := public.au_group_config_int('creditor_line_number_max_digits', 3);

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

create or replace function public.au_group_zoominfo_company_url(p_company_id text)
returns text
language sql
stable
set search_path = public
as $$
  select case
    when p_company_id is null or trim(p_company_id) = '' then ''
    else replace(
      public.au_group_config_text(
        'zoominfo_company_url_template',
        'https://app.zoominfo.com/#/company/{id}/overview'
      ),
      '{id}',
      trim(p_company_id)
    )
  end;
$$;

create or replace function public.au_group_creditor_pipeline_status(p_creditor_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_sf text;
  v_enriched text;
  v_pending text;
  v_failed text;
  v_new text;
begin
  v_sf := public.au_group_config_text('daily_report_status_sf_synced', 'Salesforce Synced');
  v_enriched := public.au_group_config_text('daily_report_status_enriched', 'ZoomInfo Enriched');
  v_pending := public.au_group_config_text('daily_report_status_pending_enrichment', 'Pending Enrichment');
  v_failed := public.au_group_config_text('daily_report_status_enrich_failed', 'Enrichment Failed');
  v_new := public.au_group_config_text('daily_report_status_new', 'New');

  if exists (
    select 1 from public.salesforce_accounts sa where sa.creditor_id = p_creditor_id
  ) then
    return v_sf;
  end if;

  if exists (
    select 1 from public.zoom_info_contacts z where z.creditor_id = p_creditor_id
  ) then
    return v_enriched;
  end if;

  if exists (
    select 1
    from public.processing_jobs pj
    where pj.job_type::text = 'zoom_info_enrich'
      and pj.status::text in ('queued', 'running', 'retrying')
      and pj.bankruptcy_id in (
        select bc.bankruptcy_id
        from public.bankruptcy_creditors bc
        where bc.creditor_id = p_creditor_id
        union
        select c.source_bankruptcy_id
        from public.creditors c
        where c.id = p_creditor_id
          and c.source_bankruptcy_id is not null
      )
  ) then
    return v_pending;
  end if;

  if exists (
    select 1
    from public.processing_jobs pj
    where pj.job_type::text = 'zoom_info_enrich'
      and pj.status::text = 'failed'
      and pj.bankruptcy_id in (
        select bc.bankruptcy_id
        from public.bankruptcy_creditors bc
        where bc.creditor_id = p_creditor_id
        union
        select c.source_bankruptcy_id
        from public.creditors c
        where c.id = p_creditor_id
          and c.source_bankruptcy_id is not null
      )
  ) then
    return v_failed;
  end if;

  return v_new;
end;
$$;

create or replace function public.au_group_set_creditor_zoominfo_company_id(
  p_creditor_id uuid,
  p_company_id text
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_creditor_id is null then
    return false;
  end if;
  if p_company_id is null or trim(p_company_id) = '' then
    return false;
  end if;

  update public.creditors c
  set
    zoominfo_company_id = trim(p_company_id),
    updated_at = now()
  where c.id = p_creditor_id;

  return found;
end;
$$;

comment on function public.au_group_set_creditor_zoominfo_company_id is
  'SYS-03: persist ZoomInfo company id on creditors for daily sheet URL column';

grant execute on function public.au_group_set_creditor_zoominfo_company_id (uuid, text) to service_role;
revoke execute on function public.au_group_set_creditor_zoominfo_company_id (uuid, text) from public;

drop function if exists public.au_group_daily_creditor_report_rows(timestamptz);

create or replace function public.au_group_daily_creditor_report_rows(
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
      c.id as creditor_id,
      c.name::text as creditor,
      public.au_group_parse_creditor_city(c.address) as city,
      public.au_group_parse_creditor_state(c.address, b.state) as state,
      case
        when c.claim_amount is null then ''
        else to_char(c.claim_amount, 'FM$999,999,999,990.00')
      end as claim,
      public.au_group_creditor_pipeline_status(c.id) as status,
      public.au_group_zoominfo_company_url(c.zoominfo_company_id) as zoominfo_url
    from public.creditors c
    left join lateral (
      select bk.state
      from creditor_bankruptcy cb
      inner join public.bankruptcies bk on bk.id = cb.bankruptcy_id
      where cb.creditor_id = c.id
      order by bk.created_at desc nulls last
      limit 1
    ) b on true
    cross join v_since vs
    where c.is_company is true
      and not public.au_group_is_junk_creditor_name(c.name)
      and (
        c.created_at >= vs.since
        or exists (
          select 1
          from creditor_bankruptcy cb2
          inner join public.bankruptcies b2 on b2.id = cb2.bankruptcy_id
          where cb2.creditor_id = c.id
            and b2.created_at >= vs.since
        )
      )
    order by c.id, c.created_at desc
  )
  select jsonb_build_object(
    'since', (select since from v_since),
    'row_count', (select count(*)::int from row_data),
    'rows', coalesce((select jsonb_agg(to_jsonb(rd) - 'creditor_id') from row_data rd), '[]'::jsonb)
  );
$$;

comment on function public.au_group_daily_creditor_report_rows is
  'SYS-09: daily sheet rows {since, row_count, rows}; config-driven status/URL/window';

grant execute on function public.au_group_daily_creditor_report_rows (timestamptz) to service_role;
revoke execute on function public.au_group_daily_creditor_report_rows (timestamptz) from public;

-- Orphan junk cleanup (pre-fix parse artifacts; keeps linked/SF/enriched rows)
delete from public.creditors c
where public.au_group_is_junk_creditor_name(c.name)
  and not exists (select 1 from public.bankruptcy_creditors bc where bc.creditor_id = c.id)
  and not exists (select 1 from public.zoom_info_contacts z where z.creditor_id = c.id)
  and not exists (select 1 from public.salesforce_accounts sa where sa.creditor_id = c.id)
  and c.source_bankruptcy_id is null;
