-- KD-69: Parser reads dedup/junk thresholds from au_group_runtime_config (Keith-editable).

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('creditor_dedup_threshold', '85', 'Fuzzy dedup threshold 50-100 (parser + matrix)'),
  ('creditor_dedup_enabled', 'true', 'Enable creditor dedup in document-parser')
on conflict (config_key) do nothing;

create or replace function public.au_group_config_bool(p_key text, p_default boolean)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (
      select case lower(trim(c.config_value))
        when 'true' then true
        when '1' then true
        when 'yes' then true
        else false
      end
      from public.au_group_runtime_config c
      where c.config_key = p_key
      limit 1
    ),
    p_default
  );
$$;

grant execute on function public.au_group_config_bool(text, boolean) to service_role;
revoke execute on function public.au_group_config_bool(text, boolean) from public;
