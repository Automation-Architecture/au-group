-- SYS-04: company creditors for Salesforce push loop (no n8n Code join)

create or replace function public.au_group_list_company_creditors(p_bankruptcy_id uuid)
returns table (
  creditor_id uuid,
  creditor_name text,
  creditor_address text,
  claim_amount numeric
)
language sql
stable
security definer
set search_path = public
as $$
  select
    c.id,
    c.name,
    c.address,
    c.claim_amount
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and length(trim(c.name)) >= 3
    and c.name !~* '^(mailing address|email address|\d{1,2})$';
$$;

comment on function public.au_group_list_company_creditors is
  'SYS-04: company creditors for loop (junk names filtered in SQL)';

grant execute on function public.au_group_list_company_creditors(uuid) to service_role;

create or replace function public.au_group_count_company_creditors(p_bankruptcy_id uuid)
returns bigint
language sql
stable
security definer
set search_path = public
as $$
  select count(*)::bigint
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and length(trim(c.name)) >= 3
    and c.name !~* '^(mailing address|email address|\d{1,2})$';
$$;

grant execute on function public.au_group_count_company_creditors(uuid) to service_role;
