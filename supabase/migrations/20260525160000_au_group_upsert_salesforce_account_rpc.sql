-- SYS-04: idempotent map creditor_id → Salesforce Account Id (FR-5.1 dedup cache)

create or replace function public.au_group_upsert_salesforce_account(
  p_creditor_id uuid,
  p_salesforce_account_id varchar,
  p_territory_rep varchar default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
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

comment on function public.au_group_upsert_salesforce_account is
  'SYS-04: upsert salesforce_accounts after successful Salesforce push';

grant execute on function public.au_group_upsert_salesforce_account(uuid, varchar, varchar) to service_role;
