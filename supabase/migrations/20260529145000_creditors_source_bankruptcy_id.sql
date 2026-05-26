-- Bankruptcy provenance for creditors merged from Schedule F / matrix parse.
-- Referenced by au_group_merge_creditor_matrix and SYS-09 daily creditor report RPCs.

alter table public.creditors
  add column if not exists source_bankruptcy_id uuid references public.bankruptcies (id) on delete set null;

comment on column public.creditors.source_bankruptcy_id is
  'Bankruptcy case where this creditor was first extracted; used when bankruptcy_creditors is empty.';

create index if not exists idx_creditors_source_bankruptcy_id
  on public.creditors (source_bankruptcy_id)
  where source_bankruptcy_id is not null;
