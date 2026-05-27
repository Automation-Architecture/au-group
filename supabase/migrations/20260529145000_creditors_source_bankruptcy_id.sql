-- merge_creditor_matrix has written source_bankruptcy_id since 20260519171000;
-- daily-report SQL RPCs (20260529150000+) require the column at create time.

alter table public.creditors
  add column if not exists source_bankruptcy_id uuid references public.bankruptcies (id) on delete set null;

comment on column public.creditors.source_bankruptcy_id is
  'Bankruptcy case that first ingested this creditor; used when bankruptcy_creditors is empty.';

create index if not exists idx_creditors_source_bankruptcy_id
  on public.creditors (source_bankruptcy_id)
  where source_bankruptcy_id is not null;
