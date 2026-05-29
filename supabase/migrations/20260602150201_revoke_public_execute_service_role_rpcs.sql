-- Hardening: service_role-only RPCs must not remain executable by PUBLIC (default in Postgres).

revoke execute on function public.au_group_upsert_bankruptcy (
  varchar,
  varchar,
  date,
  varchar,
  public.au_group_chapter_type,
  varchar,
  numeric,
  numeric,
  integer
) from public;

revoke execute on function public.au_group_upsert_bankruptcy_from_form201 (
  uuid, text, text, text, text, text, jsonb, jsonb, jsonb, numeric, boolean
) from public;

revoke execute on function public.au_group_safe_numeric (text) from public;

revoke execute on function public.au_group_merge_creditor_matrix (uuid, jsonb) from public;

revoke execute on function public.au_group_merge_creditor_matrix (uuid, jsonb, numeric) from public;

revoke execute on function public.au_group_resolve_manual_review (uuid, text) from public;

revoke execute on function public.au_group_fail_stale_processing_jobs (interval) from public;

revoke execute on function public.au_group_link_document_bankruptcy (uuid, uuid) from public;

-- 2-arg overload may not exist on all environments (remote uses 3-arg only).
do $$
begin
  execute 'revoke execute on function public.au_group_acquire_processing_job (uuid, public.au_group_job_type) from public';
exception
  when undefined_function then null;
end;
$$;

revoke execute on function public.au_group_acquire_processing_job (
  uuid,
  public.au_group_job_type,
  interval
) from public;

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

revoke execute on function public.au_group_upsert_docket_entries (uuid, jsonb) from public;

revoke execute on function public.au_group_upsert_salesforce_account(uuid, varchar, varchar) from public;

revoke execute on function public.au_group_list_company_creditors(uuid) from public;

revoke execute on function public.au_group_count_company_creditors(uuid) from public;

revoke execute on function public.au_group_resolve_territory_rep (text) from public;

do $$
begin
  execute 'revoke execute on function public.au_group_recompute_exposure (uuid) from public';
exception
  when undefined_function then null;
end;
$$;

revoke execute on function public.au_group_check_repeat_exposure (uuid, integer, integer) from public;

revoke execute on function public.au_group_daily_pipeline_summary (timestamptz) from public;

revoke execute on function public.au_group_list_target_states () from public;

revoke execute on function public.au_group_is_target_state (text) from public;

revoke execute on function public.au_group_is_junk_creditor_name (text) from public;

revoke execute on function public.au_group_finalize_document_job(uuid, uuid, uuid) from public;

revoke execute on function public.au_group_enrich_loop_push(uuid, uuid, jsonb) from public;

revoke execute on function public.au_group_enrich_loop_finalize(uuid, uuid, uuid) from public;

revoke execute on function public.au_group_build_lookup_context(jsonb, jsonb) from public;

revoke execute on function public.au_group_normalize_zoominfo_company_response(jsonb, jsonb, integer) from public;

revoke execute on function public.au_group_normalize_zoominfo_contact_response(jsonb, jsonb, integer) from public;

revoke execute on function public.au_group_schedule_f_keyword_hit(text) from public;

revoke execute on function public.au_group_diff_pacer_favorites(jsonb, uuid[]) from public;

revoke execute on function public.au_group_normalize_rss_items(jsonb) from public;

revoke execute on function public.au_group_normalize_rss_item(jsonb) from public;

revoke execute on function public.au_group_expand_import_rows(jsonb) from public;

revoke execute on function public.au_group_config_bool(text, boolean) from public;

revoke execute on function public.au_group_audit_config_change() from public;

grant execute on function public.au_group_creditor_pipeline_status(uuid) to service_role;
revoke execute on function public.au_group_creditor_pipeline_status(uuid) from public;
