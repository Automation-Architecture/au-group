-- SYS-09: add company_name (normalized / ZoomInfo canonical) alongside filing creditor name.

drop function if exists public.au_group_daily_creditor_report_rows(timestamptz);

create or replace function public.au_group_daily_creditor_report_rows(
  p_since timestamptz default now() - interval '24 hours'
)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with creditor_bankruptcy as (
    select c.id as creditor_id, bc.bankruptcy_id
    from public.creditors c
    inner join public.bankruptcy_creditors bc on bc.creditor_id = c.id
    union
    select c.id, c.source_bankruptcy_id
    from public.creditors c
    where c.source_bankruptcy_id is not null
  ),
  v_since as (
    select coalesce(p_since, now() - interval '24 hours') as since
  ),
  row_data as (
    select distinct on (c.id)
      coalesce(nullif(trim(c.original_name), ''), c.name)::text as creditor,
      coalesce(nullif(trim(c.normalized_name), ''), c.name)::text as company_name,
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
    cross join v_since vs2
    where c.is_company is true
      and not public.au_group_is_junk_creditor_name(c.name)
      and (
        c.created_at >= vs2.since
        or exists (
          select 1
          from creditor_bankruptcy cb2
          inner join public.bankruptcies b2 on b2.id = cb2.bankruptcy_id
          where cb2.creditor_id = c.id
            and b2.created_at >= vs2.since
        )
      )
    order by c.id, c.created_at desc
  )
  select jsonb_build_object(
    'since', vs.since,
    'row_count', (select count(*)::int from row_data),
    'rows', coalesce((select jsonb_agg(to_jsonb(rd)) from row_data rd), '[]'::jsonb)
  )
  from v_since vs;
$$;

comment on function public.au_group_daily_creditor_report_rows is
  'SYS-09: daily sheet rows; creditor=filing name, company_name=normalized/ZoomInfo canonical';

grant execute on function public.au_group_daily_creditor_report_rows (timestamptz) to service_role;
