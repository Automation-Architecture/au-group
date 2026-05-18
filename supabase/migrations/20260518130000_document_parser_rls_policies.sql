-- Explicit RLS deny for anon/authenticated on document-parser tables.
-- service_role bypasses RLS and is used only by the document-parser service.

create policy documents_deny_public
  on public.documents
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

create policy form201_extractions_deny_public
  on public.form201_extractions
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

create policy creditor_matrix_extractions_deny_public
  on public.creditor_matrix_extractions
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

create policy creditor_matrix_rows_deny_public
  on public.creditor_matrix_rows
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

create policy manual_review_queue_deny_public
  on public.manual_review_queue
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
