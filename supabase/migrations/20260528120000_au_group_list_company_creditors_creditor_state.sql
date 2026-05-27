-- KD-11 / FR-5.3: creditor_state from address with bankruptcy.state fallback

drop function if exists public.au_group_list_company_creditors(uuid);

create or replace function public.au_group_parse_creditor_state(
  p_address text,
  p_fallback_state char(2)
)
returns char(2)
language sql
immutable
as $$
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
$$;

create or replace function public.au_group_list_company_creditors(p_bankruptcy_id uuid)
returns table (
  creditor_id uuid,
  creditor_name text,
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
    c.address,
    c.claim_amount,
    public.au_group_parse_creditor_state(c.address, b.state)
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  inner join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and length(trim(c.name)) >= 3
    and lower(trim(c.name)) not in ('contact', 'contacts')
    and c.name !~* '(mailing address|email address)'
    and trim(c.name) !~ '^\d{1,2}$';
$$;

comment on function public.au_group_list_company_creditors is
  'SYS-04: company creditors with creditor_state (address parse + bankruptcy fallback)';

grant execute on function public.au_group_list_company_creditors(uuid) to service_role;
