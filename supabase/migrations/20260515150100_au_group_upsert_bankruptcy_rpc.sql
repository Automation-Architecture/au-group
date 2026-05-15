-- RPC for n8n / clients: single round-trip upsert on case_number (PostgREST: POST /rest/v1/rpc/au_group_upsert_bankruptcy)
create or replace function public.au_group_upsert_bankruptcy (
  p_case_number varchar(50),
  p_debtor_name varchar(255),
  p_filing_date date,
  p_court_district varchar(100),
  p_chapter_type public.au_group_chapter_type,
  p_state varchar(2),
  p_estimated_assets numeric(15, 2) default null,
  p_estimated_liabilities numeric(15, 2) default null,
  p_estimated_creditor_count integer default null
) returns uuid
language plpgsql
security invoker
set search_path to public
as $$
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

grant execute on function public.au_group_upsert_bankruptcy (
  varchar,
  varchar,
  date,
  varchar,
  public.au_group_chapter_type,
  varchar,
  numeric,
  numeric,
  integer
) to service_role;
