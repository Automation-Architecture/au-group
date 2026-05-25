-- SYS-06 Schedule F monitoring columns (FR-2.1 / FR-2.2)
alter table public.schedule_f_queue
  add column if not exists next_scan_at timestamptz,
  add column if not exists monitoring_status text default 'active',
  add column if not exists scan_attempts integer not null default 0,
  add column if not exists schedule_f_detected boolean default false,
  add column if not exists last_error text,
  add column if not exists pacer_document_url text,
  add column if not exists ai_summary jsonb,
  add column if not exists priority integer default 5;

create index if not exists idx_schedule_f_queue_next_scan
  on public.schedule_f_queue (next_scan_at)
  where status in ('monitoring', 'pending_approval', 'detected');

create index if not exists idx_schedule_f_queue_monitoring_active
  on public.schedule_f_queue (status, monitoring_status)
  where monitoring_status = 'active';

comment on column public.schedule_f_queue.next_scan_at is
  'SYS-06: earliest time to include case in weekly docket scan batch';
comment on column public.schedule_f_queue.ai_summary is
  'SYS-06: detection metadata (companion docket, amended flag, truncation)';
