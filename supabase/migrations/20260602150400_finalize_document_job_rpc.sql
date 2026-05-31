-- Recovery migration: applied to live DB out-of-repo on 2026-06-02.
-- Captures: au_group_finalize_document_job RPC which collects document_parse_results
-- for a job and returns a structured summary for pipeline handoff.
--
-- Placed last because it depends on document_parse_results (existing table) and
-- references types/patterns established in the earlier 20260602150xxx migrations.

-- ---------------------------------------------------------------------------
-- au_group_finalize_document_job
-- ---------------------------------------------------------------------------
create or replace function public.au_group_finalize_document_job(
  p_job_id                uuid,
  p_pipeline_execution_id uuid default null,
  p_schedule_f_queue_id   uuid default null
)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_rows        jsonb;
  v_expected    integer;
  v_any_failed  boolean;
  v_any_review  boolean;
  v_first       jsonb;
  v_bankruptcy_id uuid;
begin
  if p_job_id is null then
    raise exception 'p_job_id is required' using errcode = 'P0001';
  end if;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'bankruptcy_id',          r.bankruptcy_id,
      'processing_job_id',      r.processing_job_id,
      'pipeline_execution_id',  p_pipeline_execution_id,
      'schedule_f_queue_id',    p_schedule_f_queue_id,
      'doc_index',              r.doc_index,
      'doc_key',                r.doc_key,
      's3_key',                 r.s3_key,
      'document_url',           r.document_url,
      'document_id',            r.document_id,
      'parser_status',          r.parser_status,
      'manual_review_required', r.manual_review_required,
      'parser_result',          r.parser_result,
      'parse_error',            r.parse_error
    ) order by r.doc_index
  ), '[]'::jsonb)
  into v_rows
  from public.document_parse_results r
  where r.processing_job_id = p_job_id;

  if jsonb_array_length(v_rows) = 0 then
    raise exception 'no document_parse_results for job %', p_job_id using errcode = 'P0001';
  end if;

  v_first         := v_rows->0;
  v_bankruptcy_id := (v_first->>'bankruptcy_id')::uuid;
  v_any_failed    := exists (
    select 1 from jsonb_array_elements(v_rows) e
    where e->>'parser_status' = 'failed'
  );
  v_any_review    := exists (
    select 1 from jsonb_array_elements(v_rows) e
    where (e->>'manual_review_required')::boolean is true
  );

  return jsonb_build_object(
    'bankruptcy_id',          v_bankruptcy_id,
    'processing_job_id',      p_job_id,
    'pipeline_execution_id',  p_pipeline_execution_id,
    'schedule_f_queue_id',    p_schedule_f_queue_id,
    'parser_results',         v_rows,
    'any_failed',             v_any_failed,
    'any_manual_review',      v_any_review,
    'document_count',         jsonb_array_length(v_rows)
  );
end;
$$;

grant execute on function public.au_group_finalize_document_job(uuid, uuid, uuid)
  to service_role;
revoke execute on function public.au_group_finalize_document_job(uuid, uuid, uuid)
  from public;
