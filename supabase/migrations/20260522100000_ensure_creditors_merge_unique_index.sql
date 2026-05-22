-- au_group_merge_creditor_matrix ON CONFLICT requires this expression index.
-- Safe to re-run if 20260518130001 was skipped or the remote DB was created before it landed.
create unique index if not exists idx_creditors_normalized_name_address
  on public.creditors (
    lower(trim(name)),
    lower(trim(coalesce(address, '')))
  );
