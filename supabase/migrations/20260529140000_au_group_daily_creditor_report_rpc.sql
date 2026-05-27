-- SYS-09: Daily Google Sheet rows (24h company creditors for Keith)

alter table public.creditors
  add column if not exists zoominfo_company_id text;

comment on column public.creditors.zoominfo_company_id is
  'ZoomInfo company id from SYS-03 enrichment; used for daily report profile URL.';

create or replace function public.au_group_parse_creditor_city(p_address text)
returns text
language sql
immutable
as $$
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
$$;

comment on function public.au_group_parse_creditor_city is
  'Parse city from US-style creditor mailing address (best-effort).';

create or replace function public.au_group_creditor_pipeline_status(p_creditor_id uuid)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select case
    when exists (
      select 1
      from public.salesforce_accounts sa
      where sa.creditor_id = p_creditor_id
    ) then 'Salesforce Synced'
    when exists (
      select 1
      from public.zoom_info_contacts z
      where z.creditor_id = p_creditor_id
    ) then 'ZoomInfo Enriched'
    when exists (
      select 1
      from public.processing_jobs pj
      inner join public.bankruptcy_creditors bc on bc.bankruptcy_id = pj.bankruptcy_id
      where bc.creditor_id = p_creditor_id
        and pj.job_type = 'zoom_info_enrich'
        and pj.status = 'failed'
    ) then 'Enrichment Failed'
    else 'New'
  end;
$$;

create or replace function public.au_group_zoominfo_company_url(p_company_id text)
returns text
language sql
immutable
as $$
  select case
    when p_company_id is null or trim(p_company_id) = '' then ''
    else 'https://app.zoominfo.com/#/company/' || trim(p_company_id) || '/overview'
  end;
$$;

create or replace function public.au_group_daily_creditor_report_rows(
  p_since timestamptz default now() - interval '24 hours'
)
returns table (
  creditor text,
  city text,
  state char(2),
  claim text,
  status text,
  zoominfo_url text
)
language sql
stable
security definer
set search_path = public
as $$
  select distinct on (c.id)
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
  inner join public.bankruptcy_creditors bc on bc.creditor_id = c.id
  inner join public.bankruptcies b on b.id = bc.bankruptcy_id
  where c.created_at >= p_since
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name)
  order by c.id, c.created_at desc;
$$;

comment on function public.au_group_daily_creditor_report_rows is
  'SYS-09: company creditors created in the last 24h for the daily Google Sheet.';

grant execute on function public.au_group_daily_creditor_report_rows (timestamptz) to service_role;
