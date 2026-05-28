-- SYS-01: Keith-editable caps for RSS volume per run.

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('rss_max_items_per_run', '200', 'Max RSS rows processed per SYS-01 execution (all courts combined)'),
  ('rss_normalize_batch_size', '20', 'Rows per au_group_normalize_rss_items RPC call in n8n')
on conflict (config_key) do nothing;
