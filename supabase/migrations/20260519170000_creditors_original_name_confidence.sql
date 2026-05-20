-- Add original_name and confidence_score to creditors (extraction provenance)
alter table public.creditors
  add column if not exists original_name text,
  add column if not exists confidence_score numeric(5, 4);

comment on column public.creditors.original_name is
  'Raw creditor name as extracted from source document before normalization.';
comment on column public.creditors.confidence_score is
  'Per-creditor extraction confidence (0–1), when available from parser/OCR.';
