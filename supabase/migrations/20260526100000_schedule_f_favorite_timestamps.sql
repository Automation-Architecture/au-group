-- Wave 1: PACER favorites audit columns (FR-2.4 / EC-4.2 re-favorite)

alter table public.schedule_f_queue
  add column if not exists pacer_favorite_added_at timestamptz,
  add column if not exists rejected_at timestamptz,
  add column if not exists approved_at timestamptz;

comment on column public.schedule_f_queue.pacer_favorite_added_at is
  'When SYS-06 added this docket to PACER Case Locator reports/favorites';
comment on column public.schedule_f_queue.rejected_at is
  'When Keith unfavorited or SYS-07 diff marked rejected';
comment on column public.schedule_f_queue.approved_at is
  'When SYS-07 diff confirmed still favorited and download approved';
