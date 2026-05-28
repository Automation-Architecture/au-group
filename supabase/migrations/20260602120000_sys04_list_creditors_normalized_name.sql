-- SYS-04 / FR-5.1: expose normalized_name for Salesforce account match (KD-24).

drop function if exists public.au_group_list_company_creditors(uuid);

create or replace function public.au_group_list_company_creditors(p_bankruptcy_id uuid)
returns table (
  creditor_id uuid,
  creditor_name text,
  normalized_name text,
  creditor_address text,
  claim_amount numeric,
  creditor_state char(2)
)
language sql
stable
security definer
set search_path = public
as $$
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

comment on function public.au_group_list_company_creditors is
  'SYS-04: company creditors with normalized_name + creditor_state for SF match (FR-5.1).';

grant execute on function public.au_group_list_company_creditors(uuid) to service_role;

drop function if exists public.au_group_count_company_creditors(uuid);

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
    and not public.au_group_is_junk_creditor_name(c.name)
    and not public.au_group_is_suppressed_creditor_name(c.name);
$$;

grant execute on function public.au_group_count_company_creditors(uuid) to service_role;
