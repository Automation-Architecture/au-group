-- KD-71 (subtask of KD-68): expose normalized_name from au_group_list_company_creditors
-- so the code-native Salesforce push can key Account match on the same canonical
-- company name used for ZoomInfo lookup (FR-5.1), instead of re-normalizing in app code.
--
-- normalized_name is derived via the existing au_group_normalize_company_name RPC
-- (migration 20260602150201). This is a PURELY ADDITIVE trailing column — same rows,
-- same order as before.
--
-- A RETURNS TABLE return type cannot be changed via CREATE OR REPLACE, so the function
-- is dropped and recreated. DROP also drops all grants AND re-defaults EXECUTE to PUBLIC;
-- because this is a security-definer function, the revokes below are mandatory to keep it
-- service-role-only (the dynamic ACL sweep in 20260602150900 already ran and will not
-- re-fire for this recreated function). Body copied verbatim from 20260529120000 plus the
-- one new column. au_group_count_company_creditors returns a scalar bigint (no row
-- projection) and is intentionally left untouched.

drop function if exists public.au_group_list_company_creditors(uuid);

create or replace function public.au_group_list_company_creditors(p_bankruptcy_id uuid)
returns table (
  creditor_id uuid,
  creditor_name text,
  creditor_address text,
  claim_amount numeric,
  creditor_state char(2),
  normalized_name text
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
    public.au_group_parse_creditor_state(c.address, b.state),
    public.au_group_normalize_company_name(c.name)
  from public.bankruptcy_creditors bc
  inner join public.creditors c on c.id = bc.creditor_id
  inner join public.bankruptcies b on b.id = bc.bankruptcy_id
  where bc.bankruptcy_id = p_bankruptcy_id
    and c.is_company is true
    and not public.au_group_is_junk_creditor_name(c.name);
$$;

-- Service-role-only lockdown (DROP+CREATE re-defaulted EXECUTE to PUBLIC).
revoke execute on function public.au_group_list_company_creditors(uuid) from public;
revoke execute on function public.au_group_list_company_creditors(uuid) from anon;
revoke execute on function public.au_group_list_company_creditors(uuid) from authenticated;
grant  execute on function public.au_group_list_company_creditors(uuid) to service_role;
