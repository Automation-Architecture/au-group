-- RPC for n8n SYS-02: upsert per-document parse results (bypasses RLS via security definer).
-- PostgREST: POST /rest/v1/rpc/au_group_upsert_document_parse_result

create or replace function public.au_group_upsert_document_parse_result (
  p_processing_job_id uuid,
  p_bankruptcy_id uuid,
  p_doc_index integer,
  p_doc_key text,
  p_parser_status text,
  p_manual_review_required boolean default false,
  p_s3_key text default null,
  p_document_url text default null,
  p_document_id text default null,
  p_parser_result jsonb default null,
  p_parse_error text default null
) returns jsonb
language plpgsql
security definer
set search_path to public
as $$
declare
  v_row public.document_parse_results;
begin
  if p_processing_job_id is null then
    raise exception 'p_processing_job_id is required' using errcode = 'P0001';
  end if;
  if p_bankruptcy_id is null then
    raise exception 'p_bankruptcy_id is required' using errcode = 'P0001';
  end if;
  if p_doc_key is null or btrim(p_doc_key) = '' then
    raise exception 'p_doc_key is required' using errcode = 'P0001';
  end if;

  insert into public.document_parse_results (
    processing_job_id,
    bankruptcy_id,
    doc_index,
    doc_key,
    s3_key,
    document_url,
    document_id,
    parser_status,
    manual_review_required,
    parser_result,
    parse_error,
    updated_at
  )
  values (
    p_processing_job_id,
    p_bankruptcy_id,
    p_doc_index,
    p_doc_key,
    p_s3_key,
    p_document_url,
    p_document_id,
    p_parser_status,
    coalesce(p_manual_review_required, false),
    p_parser_result,
    p_parse_error,
    now()
  )
  on conflict (processing_job_id, doc_index)
  do update set
    bankruptcy_id = excluded.bankruptcy_id,
    doc_key = excluded.doc_key,
    s3_key = excluded.s3_key,
    document_url = excluded.document_url,
    document_id = excluded.document_id,
    parser_status = excluded.parser_status,
    manual_review_required = excluded.manual_review_required,
    parser_result = excluded.parser_result,
    parse_error = excluded.parse_error,
    updated_at = now()
  returning * into v_row;

  return to_jsonb(v_row);
end;
$$;

grant execute on function public.au_group_upsert_document_parse_result (
  uuid,
  uuid,
  integer,
  text,
  text,
  boolean,
  text,
  text,
  text,
  jsonb,
  text
) to service_role;

revoke execute on function public.au_group_upsert_document_parse_result (
  uuid,
  uuid,
  integer,
  text,
  text,
  boolean,
  text,
  text,
  text,
  jsonb,
  text
) from public, anon, authenticated;
