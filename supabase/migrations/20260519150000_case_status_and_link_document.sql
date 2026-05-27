-- Lifecycle flags and helpers for document-parser / n8n pipeline

create or replace function public.au_group_upsert_case_status (
  p_bankruptcy_id uuid,
  p_has_creditor_matrix boolean default null,
  p_has_schedule_f boolean default null,
  p_has_asset_schedule boolean default null,
  p_enrichment_completed boolean default null,
  p_outreach_ready boolean default null,
  p_lifecycle_stage text default null
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.bankruptcy_case_status (
    bankruptcy_id,
    has_creditor_matrix,
    has_schedule_f,
    has_asset_schedule,
    enrichment_completed,
    outreach_ready,
    lifecycle_stage,
    updated_at
  )
  values (
    p_bankruptcy_id,
    coalesce(p_has_creditor_matrix, false),
    coalesce(p_has_schedule_f, false),
    coalesce(p_has_asset_schedule, false),
    coalesce(p_enrichment_completed, false),
    coalesce(p_outreach_ready, false),
    coalesce(p_lifecycle_stage, 'new'),
    now()
  )
  on conflict (bankruptcy_id) do update
  set
    has_creditor_matrix = coalesce(p_has_creditor_matrix, bankruptcy_case_status.has_creditor_matrix),
    has_schedule_f = coalesce(p_has_schedule_f, bankruptcy_case_status.has_schedule_f),
    has_asset_schedule = coalesce(p_has_asset_schedule, bankruptcy_case_status.has_asset_schedule),
    enrichment_completed = coalesce(
      p_enrichment_completed,
      bankruptcy_case_status.enrichment_completed
    ),
    outreach_ready = coalesce(p_outreach_ready, bankruptcy_case_status.outreach_ready),
    lifecycle_stage = coalesce(p_lifecycle_stage, bankruptcy_case_status.lifecycle_stage),
    updated_at = now();

  return p_bankruptcy_id;
end;
$$;

create or replace function public.au_group_link_document_bankruptcy (
  p_document_id uuid,
  p_bankruptcy_id uuid
) returns jsonb
language plpgsql
security invoker
set search_path to public
as $$
declare
  v_doc public.documents%rowtype;
begin
  update public.documents
  set bankruptcy_id = p_bankruptcy_id, updated_at = now()
  where id = p_document_id
  returning * into v_doc;

  if v_doc.id is null then
    raise exception 'document not found: %', p_document_id using errcode = 'P0002';
  end if;

  update public.form201_extractions
  set bankruptcy_id = p_bankruptcy_id
  where document_id = p_document_id;

  update public.creditor_matrix_extractions
  set bankruptcy_id = p_bankruptcy_id
  where document_id = p_document_id;

  update public.manual_review_queue
  set bankruptcy_id = p_bankruptcy_id
  where document_id = p_document_id and bankruptcy_id is null;

  return jsonb_build_object(
    'document_id', v_doc.id,
    'bankruptcy_id', p_bankruptcy_id,
    's3_key', v_doc.s3_key,
    'filing_type', v_doc.filing_type
  );
end;
$$;

grant execute on function public.au_group_upsert_case_status (
  uuid, boolean, boolean, boolean, boolean, boolean, text
) to service_role;
revoke execute on function public.au_group_upsert_case_status (
  uuid, boolean, boolean, boolean, boolean, boolean, text
) from public;

grant execute on function public.au_group_link_document_bankruptcy (uuid, uuid) to service_role;
