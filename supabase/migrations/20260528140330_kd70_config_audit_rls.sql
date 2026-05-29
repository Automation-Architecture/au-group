-- KD-70: Enable RLS on au_group_config_audit (NFR-5.3). Trigger writes via security definer / service_role.
-- Version aligned with prod schema_migrations (MCP apply 20260528140330).

alter table public.au_group_config_audit enable row level security;

drop policy if exists au_group_config_audit_deny_public on public.au_group_config_audit;
create policy au_group_config_audit_deny_public
  on public.au_group_config_audit
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
