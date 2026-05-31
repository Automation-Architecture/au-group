-- Recovery migration: applied to live DB out-of-repo on 2026-06-02.
-- Captures enrichment + RSS normalization RPCs that depend on functions in
-- 20260602150201 and tables in 20260602150100:
--   au_group_normalize_rss_item, au_group_normalize_rss_items,
--   au_group_normalize_zoominfo_company_response,
--   au_group_normalize_zoominfo_contact_response,
--   au_group_upsert_zoom_info_contacts,
--   au_group_upsert_zoominfo_company_cache,
--   au_group_diff_pacer_favorites,
--   au_group_enrich_loop_push, au_group_enrich_loop_finalize,
--   au_group_evaluate_outreach_gates,
--   au_group_expand_import_rows,
--   au_group_pick_document_parse_handoff.
--
-- All functions use CREATE OR REPLACE — safe to replay.

-- ---------------------------------------------------------------------------
-- 1. au_group_normalize_rss_item (depends on au_group_schedule_f_keyword_hit)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_rss_item(p_item jsonb)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_item    jsonb := coalesce(p_item, '{}'::jsonb);
  v_title   text;
  v_content text;
  v_link    text;
  v_clean   text;
  v_case    text;
  v_debtor  text;
  v_chapter text;
  v_court   text;
  v_guid    text;
  v_doc_url text;
  v_signal  integer;
  v_qualified    boolean;
  v_is_business  boolean;
  v_is_person    boolean;
  v_excluded     boolean;
  c_max_html  constant integer := 32768;
  c_max_clean constant integer := 12000;
begin
  v_title   := btrim(regexp_replace(coalesce(v_item->>'title', ''), '\s+', ' ', 'g'));
  v_content := left(
    coalesce(
      v_item->>'content',
      v_item->>'contentSnippet',
      v_item->>'description',
      ''
    ),
    c_max_html
  );
  v_link  := coalesce(v_item->>'link', '');
  v_clean := left(
    btrim(regexp_replace(regexp_replace(v_content, '<[^>]+>', ' ', 'g'), '\s+', ' ', 'g')),
    c_max_clean
  );

  v_case    := (regexp_match(v_title, '(\d{2}-\d{4,6}(?:-[a-z0-9]+)*)', 'i'))[1];
  v_chapter := coalesce(
    (regexp_match(v_clean, 'chapter[:\s]+(\d+)', 'i'))[1],
    (regexp_match(v_clean, 'chapter\s+(\d+)', 'i'))[1]
  );
  v_court   := (regexp_match(v_link, 'ecf\.([a-z]+)\.uscourts\.gov', 'i'))[1];
  v_guid    := coalesce(v_item->>'guid', v_item->>'id', v_link);
  v_doc_url := (regexp_match(v_content, 'href=[''"]([^''" ]*doc1[^''" ]+)[''"]', 'i'))[1];
  if v_doc_url is null then
    v_doc_url := (regexp_match(v_content, 'https://ecf\.[^'' ]+/doc1/[^'' ]+', 'i'))[1];
  end if;

  v_debtor := btrim(regexp_replace(
    case when v_case is not null then regexp_replace(v_title, v_case, '', 'i') else v_title end,
    '\s+', ' ', 'g'
  ));
  v_is_business := v_debtor ~* '(llc|inc|corp|corporation|ltd|lp|holdings|company|co\.|group|enterprises)';
  v_is_person   := v_debtor ~ '^[A-Z][a-z]+ [A-Z][a-z]+' and not v_is_business;
  v_excluded    := v_clean ~* '(certificate of credit counseling|certificate of mailing|personal financial management|proof of claim|meeting of creditors|\[schedules\]|chapter 13 plan|notice of hearing)';

  v_signal := 0;
  if v_clean ~* 'voluntary petition' then v_signal := v_signal + 40; end if;
  if v_clean ~* 'petition filed'     then v_signal := v_signal + 30; end if;
  if v_clean ~* 'chapter\s*11'       then v_signal := v_signal + 20; end if;
  if public.au_group_schedule_f_keyword_hit(v_clean) then v_signal := v_signal + 15; end if;

  v_qualified := v_signal >= 40
    and not v_is_person
    and v_case  is not null
    and v_guid  is not null
    and not v_excluded;

  return jsonb_build_object(
    'case_number',      v_case,
    'debtor_name',      nullif(v_debtor, ''),
    'chapter',          v_chapter,
    'court_id',         v_court,
    'filing_date',      left(coalesce(v_item->>'isoDate', v_item->>'pubDate', ''), 10),
    'rss_guid',         v_guid,
    'document_url',     v_doc_url,
    'unique_key',       coalesce(v_court, '') || ':' || coalesce(v_case, '') || ':' || coalesce(v_guid, ''),
    'signal_score',     case when v_excluded then 0 else v_signal end,
    'is_business',      v_is_business,
    'is_likely_person', v_is_person,
    'is_excluded_event', v_excluded,
    'is_qualified',     v_qualified,
    'raw_content',      left(v_clean, 4000)
  );
end;
$$;

grant execute on function public.au_group_normalize_rss_item(jsonb)
  to service_role;
revoke execute on function public.au_group_normalize_rss_item(jsonb)
  from public;

-- ---------------------------------------------------------------------------
-- 2. au_group_normalize_rss_items (batch wrapper; depends on normalize_rss_item)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_rss_items(p_items jsonb)
returns jsonb
language sql
stable security definer
set search_path to public
as $$
  select jsonb_build_object(
    'items',
    coalesce(
      jsonb_agg(public.au_group_normalize_rss_item(elem) order by ord),
      '[]'::jsonb
    )
  )
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) with ordinality as t(elem, ord);
$$;

grant execute on function public.au_group_normalize_rss_items(jsonb)
  to service_role;
revoke execute on function public.au_group_normalize_rss_items(jsonb)
  from public;

-- ---------------------------------------------------------------------------
-- 3. au_group_normalize_zoominfo_company_response
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_zoominfo_company_response(
  p_body        jsonb,
  p_ctx         jsonb,
  p_status_code integer default null
)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_ctx         jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body        jsonb;
  v_data        jsonb;
  v_candidates  jsonb;
  v_state_hint  text;
  v_top         jsonb;
  v_second      jsonb;
  v_top_score   numeric;
  v_second_score numeric;
  v_attrs       jsonb;
  v_company_id  text;
  v_revenue     numeric;
  v_employees   numeric;
  v_industry    text;
  v_hq          text;
  i             integer;
  v_item        jsonb;
  v_attrs_i     jsonb;
  v_hq_i        text;
  v_conf        numeric;
  v_geo         numeric;
  v_score       numeric;
  v_best        jsonb;
  v_best_score       numeric := -1;
  v_second_best_score numeric := -1;
  v_err         text;
begin
  if p_status_code = 429 then
    return v_ctx || jsonb_build_object(
      'statusCode',           429,
      'zoominfo_status',      'rate_limited',
      'zoominfo_match_status','rate_limited'
    );
  end if;

  v_body := coalesce(p_body, '{}'::jsonb);
  v_err  := coalesce(v_body->>'error', v_body->>'message');
  if v_err is not null and v_err <> '' then
    return v_ctx || jsonb_build_object(
      'zoominfo_status',        'error',
      'zoominfo_match_status',  'error',
      'zoominfo_error',         left(v_err, 500),
      'zoominfo_company_id',    null,
      'match_confidence',       null,
      'cache_hit',              false
    );
  end if;

  v_data := coalesce(v_body->'data', v_body->'results', v_body);
  if jsonb_typeof(v_data) = 'array' then
    v_candidates := v_data;
  elsif v_data is null or v_data = 'null'::jsonb then
    v_candidates := '[]'::jsonb;
  else
    v_candidates := jsonb_build_array(v_data);
  end if;

  if jsonb_array_length(v_candidates) = 0 then
    return v_ctx || jsonb_build_object(
      'zoominfo_status',       'no_match',
      'zoominfo_match_status', 'no_match',
      'zoominfo_company_id',   null,
      'match_confidence',      null,
      'cache_hit',             false,
      'skipped_reason',        'no_match'
    );
  end if;

  v_state_hint := upper(left(coalesce(v_ctx->>'creditor_state', ''), 2));

  for i in 0 .. jsonb_array_length(v_candidates) - 1 loop
    v_item    := v_candidates->i;
    v_attrs_i := coalesce(v_item->'attributes', v_item);
    v_hq_i   := upper(coalesce(
      v_attrs_i->>'headquarters',
      v_attrs_i->>'headquartersState',
      v_attrs_i->>'state',
      ''
    ));
    v_conf := coalesce(
      nullif(v_attrs_i->>'matchScore',   '')::numeric,
      nullif(v_attrs_i->>'confidence',   '')::numeric,
      nullif(v_attrs_i->>'score',        '')::numeric,
      0.5
    );
    v_geo := 0;
    if v_state_hint <> '' and position(v_state_hint in v_hq_i) > 0 then
      v_geo := 1;
    end if;
    v_score := v_conf + v_geo * 0.5;

    if v_score > v_best_score then
      v_second_best_score := v_best_score;
      v_best_score        := v_score;
      v_best := jsonb_build_object('item', v_item, 'attrs', v_attrs_i, 'score', v_score);
    elsif v_score > v_second_best_score then
      v_second_best_score := v_score;
    end if;
  end loop;

  if v_second_best_score >= 0 and abs(v_best_score - v_second_best_score) < 0.05 then
    return v_ctx || jsonb_build_object(
      'zoominfo_status',       'ambiguous',
      'zoominfo_match_status', 'ambiguous',
      'zoominfo_company_id',   null,
      'match_confidence',      v_best_score,
      'cache_hit',             false,
      'skipped_reason',        'ambiguous_match'
    );
  end if;

  v_attrs     := v_best->'attrs';
  v_item      := v_best->'item';
  v_revenue   := coalesce(
    nullif(v_attrs->>'revenue',       '')::numeric,
    nullif(v_attrs->>'annualRevenue', '')::numeric
  );
  v_employees := coalesce(
    nullif(v_attrs->>'employeeCount', '')::numeric,
    nullif(v_attrs->>'employees',     '')::numeric
  );
  v_industry  := coalesce(v_attrs->>'industry', v_attrs->>'primaryIndustry');
  v_company_id := coalesce(v_item->>'id', v_attrs->>'companyId');
  v_hq        := coalesce(v_attrs->>'headquarters', v_attrs->>'headquartersState');

  return v_ctx || jsonb_build_object(
    'zoominfo_status',        'matched',
    'zoominfo_match_status',  'matched',
    'zoominfo_company_id',    v_company_id,
    'match_confidence',       v_best_score,
    'normalized_name',        coalesce(v_attrs->>'name', v_attrs->>'companyName', v_ctx->>'normalized_name'),
    'company_revenue',        v_revenue,
    'company_employee_count', v_employees,
    'company_industry',       v_industry,
    'company_headquarters',   v_hq,
    'zoominfo_firmographics', jsonb_build_object(
      'revenue',        v_revenue,
      'employee_count', v_employees,
      'industry',       v_industry,
      'headquarters',   v_hq
    ),
    'cache_hit',    false,
    'raw_zoominfo', v_body
  );
end;
$$;

grant execute on function public.au_group_normalize_zoominfo_company_response(jsonb, jsonb, integer)
  to service_role;
revoke execute on function public.au_group_normalize_zoominfo_company_response(jsonb, jsonb, integer)
  from public;

-- ---------------------------------------------------------------------------
-- 4. au_group_normalize_zoominfo_contact_response
-- ---------------------------------------------------------------------------
create or replace function public.au_group_normalize_zoominfo_contact_response(
  p_body        jsonb,
  p_ctx         jsonb,
  p_status_code integer default null
)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_base     jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body     jsonb := coalesce(p_body, '{}'::jsonb);
  v_data     jsonb;
  v_raw      jsonb;
  v_contacts jsonb := '[]'::jsonb;
  i          integer;
  v_item     jsonb;
  v_attrs    jsonb;
  v_first    text;
  v_last     text;
  v_full     text;
  v_eng      numeric;
  v_sorted   jsonb;
begin
  if p_status_code = 429 then
    return v_base || jsonb_build_object(
      'statusCode',           429,
      'contacts_saved',       0,
      'zoominfo_status',      'rate_limited',
      'zoominfo_match_status','rate_limited'
    );
  end if;

  if coalesce(v_body->>'error', v_body->>'message') is not null then
    return v_base || jsonb_build_object(
      'contacts_saved',       0,
      'contact_search_error', left(coalesce(v_body->>'error', v_body->>'message'), 300)
    );
  end if;

  v_data := coalesce(v_body->'data', v_body->'results', v_body);
  if jsonb_typeof(v_data) = 'array' then
    v_raw := v_data;
  elsif v_data is null then
    v_raw := '[]'::jsonb;
  else
    v_raw := jsonb_build_array(v_data);
  end if;

  for i in 0 .. jsonb_array_length(v_raw) - 1 loop
    v_item  := v_raw->i;
    v_attrs := coalesce(v_item->'attributes', v_item);
    v_first := coalesce(v_attrs->>'firstName', v_attrs->>'first_name', '');
    v_last  := coalesce(v_attrs->>'lastName',  v_attrs->>'last_name',  '');
    v_full  := coalesce(
      v_attrs->>'fullName',
      v_attrs->>'name',
      nullif(btrim(v_first || ' ' || v_last), ''),
      'Unknown'
    );
    if v_full is null or v_full = 'Unknown' then
      continue;
    end if;
    v_eng := coalesce(
      nullif(v_attrs->>'engagementScore',       '')::numeric,
      nullif(v_attrs->>'contactAccuracyScore',  '')::numeric,
      nullif(v_attrs->>'score',                 '')::numeric,
      0
    );
    v_contacts := v_contacts || jsonb_build_array(jsonb_build_object(
      'full_name',            v_full,
      'title',                coalesce(v_attrs->>'jobTitle', v_attrs->>'title', v_attrs->>'primaryTitle'),
      'email',                coalesce(v_attrs->>'email',    v_attrs->>'emailAddress'),
      'phone',                coalesce(v_attrs->>'phone',    v_attrs->>'directPhone', v_attrs->>'mobilePhone'),
      'engagement_score',     v_eng,
      'company_revenue',      v_base->'company_revenue',
      'company_employee_count', v_base->'company_employee_count',
      'company_industry',     v_base->'company_industry'
    ));
  end loop;

  -- Order by engagement_score first, then limit to top 3.
  select coalesce(jsonb_agg(e), '[]'::jsonb)
  into v_sorted
  from (
    select e
    from jsonb_array_elements(v_contacts) e
    order by (e->>'engagement_score')::numeric desc nulls last
    limit 3
  ) sub;

  return v_base || jsonb_build_object(
    'contacts_payload', v_sorted,
    'contacts_saved',   jsonb_array_length(v_sorted),
    'zoominfo_status',  case
      when jsonb_array_length(v_sorted) > 0 then v_base->>'zoominfo_status'
      when v_base->>'zoominfo_status' = 'matched' then 'no_contact_found'
      else v_base->>'zoominfo_status'
    end
  );
end;
$$;

grant execute on function public.au_group_normalize_zoominfo_contact_response(jsonb, jsonb, integer)
  to service_role;
revoke execute on function public.au_group_normalize_zoominfo_contact_response(jsonb, jsonb, integer)
  from public;

-- ---------------------------------------------------------------------------
-- 5. au_group_upsert_zoom_info_contacts (depends on zoom_info_contacts table)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_upsert_zoom_info_contacts(
  p_creditor_id          uuid,
  p_contacts             jsonb,
  p_company_revenue      numeric  default null,
  p_company_employee_count integer default null,
  p_company_industry     text     default null
)
returns integer
language plpgsql
security definer
set search_path to public
as $$
declare
  v_elem  jsonb;
  v_count integer := 0;
  v_saved integer := 0;
begin
  if p_creditor_id is null then
    return 0;
  end if;

  delete from public.zoom_info_contacts where creditor_id = p_creditor_id;

  if p_contacts is null or jsonb_typeof(p_contacts) <> 'array' then
    return 0;
  end if;

  for v_elem in
    select value
    from jsonb_array_elements(p_contacts) as value
    order by coalesce((value->>'engagement_score')::integer, 0) desc
    limit 3
  loop
    v_count := v_count + 1;
    insert into public.zoom_info_contacts (
      creditor_id,
      full_name,
      title,
      email,
      phone,
      company_revenue,
      company_employee_count,
      company_industry,
      engagement_score
    ) values (
      p_creditor_id,
      coalesce(nullif(trim(v_elem->>'full_name'), ''), 'Unknown'),
      nullif(trim(v_elem->>'title'), ''),
      nullif(trim(v_elem->>'email'), ''),
      nullif(trim(v_elem->>'phone'), ''),
      coalesce(nullif(v_elem->>'company_revenue', '')::numeric,        p_company_revenue),
      coalesce(nullif(v_elem->>'company_employee_count', '')::integer, p_company_employee_count),
      coalesce(nullif(trim(v_elem->>'company_industry'), ''),          p_company_industry),
      coalesce(nullif(v_elem->>'engagement_score', '')::integer, 0)
    );
    v_saved := v_saved + 1;
  end loop;

  return v_saved;
end;
$$;

grant execute on function public.au_group_upsert_zoom_info_contacts(uuid, jsonb, numeric, integer, text)
  to service_role;
revoke execute on function public.au_group_upsert_zoom_info_contacts(uuid, jsonb, numeric, integer, text)
  from public;

-- ---------------------------------------------------------------------------
-- 6. au_group_upsert_zoominfo_company_cache (depends on zoominfo_company_cache)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_upsert_zoominfo_company_cache(
  p_cache_key      text,
  p_company_id     text,
  p_normalized_name text  default null,
  p_match_confidence numeric default null,
  p_firmographics  jsonb  default '{}'::jsonb,
  p_raw_response   jsonb  default null,
  p_ttl_days       integer default 7
)
returns boolean
language plpgsql
security definer
set search_path to public
as $$
begin
  if p_cache_key is null or trim(p_cache_key) = '' then return false; end if;
  if p_company_id is null or trim(p_company_id) = '' then return false; end if;

  insert into public.au_group_zoominfo_company_cache (
    cache_key, company_id, normalized_name, match_confidence,
    firmographics, raw_response, expires_at
  ) values (
    trim(p_cache_key),
    trim(p_company_id),
    nullif(trim(p_normalized_name), ''),
    p_match_confidence,
    coalesce(p_firmographics, '{}'::jsonb),
    p_raw_response,
    now() + make_interval(days => greatest(coalesce(p_ttl_days, 7), 1))
  )
  on conflict (cache_key) do update set
    company_id       = excluded.company_id,
    normalized_name  = excluded.normalized_name,
    match_confidence = excluded.match_confidence,
    firmographics    = excluded.firmographics,
    raw_response     = excluded.raw_response,
    expires_at       = excluded.expires_at,
    updated_at       = now();

  return true;
end;
$$;

grant execute on function public.au_group_upsert_zoominfo_company_cache(text, text, text, numeric, jsonb, jsonb, integer)
  to service_role;
revoke execute on function public.au_group_upsert_zoominfo_company_cache(text, text, text, numeric, jsonb, jsonb, integer)
  from public;

-- ---------------------------------------------------------------------------
-- 7. au_group_diff_pacer_favorites (depends on schedule_f_queue, bankruptcies)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_diff_pacer_favorites(
  p_favorites      jsonb,
  p_bankruptcy_ids uuid[] default null
)
returns jsonb
language sql
stable security definer
set search_path to public
as $$
  with fav as (
    select coalesce(f->>'case_number', f->>'caseNumber') as case_number
    from jsonb_array_elements(coalesce(p_favorites, '[]'::jsonb)) f
  ),
  pending as (
    select q.id, b.case_number, q.status
    from public.schedule_f_queue q
    inner join public.bankruptcies b on b.id = q.bankruptcy_id
    where q.status = 'pending_approval'
      and (p_bankruptcy_ids is null or q.bankruptcy_id = any (p_bankruptcy_ids))
  )
  select jsonb_build_object(
    'new_favorites', coalesce((
      select jsonb_agg(jsonb_build_object('case_number', f.case_number))
      from fav f
      where not exists (
        select 1
        from public.schedule_f_queue q
        inner join public.bankruptcies b on b.id = q.bankruptcy_id
        where b.case_number = f.case_number
      )
    ), '[]'::jsonb),
    'pending_approval', coalesce((
      select jsonb_agg(jsonb_build_object('id', p.id, 'case_number', p.case_number, 'status', p.status))
      from pending p
    ), '[]'::jsonb)
  );
$$;

grant execute on function public.au_group_diff_pacer_favorites(jsonb, uuid[])
  to service_role;
revoke execute on function public.au_group_diff_pacer_favorites(jsonb, uuid[])
  from public;

-- ---------------------------------------------------------------------------
-- 8. au_group_enrich_loop_push (depends on au_group_enrich_loop_staging)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_enrich_loop_push(
  p_job_id      uuid,
  p_creditor_id uuid,
  p_result      jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to public
as $$
begin
  if p_job_id is null or p_creditor_id is null then
    raise exception 'job_id and creditor_id required' using errcode = 'P0001';
  end if;

  insert into public.au_group_enrich_loop_staging (job_id, creditor_id, result, updated_at)
  values (p_job_id, p_creditor_id, coalesce(p_result, '{}'::jsonb), now())
  on conflict (job_id, creditor_id) do update
    set result     = public.au_group_enrich_loop_staging.result || excluded.result,
        updated_at = now();

  return jsonb_build_object('ok', true, 'job_id', p_job_id, 'creditor_id', p_creditor_id);
end;
$$;

grant execute on function public.au_group_enrich_loop_push(uuid, uuid, jsonb)
  to service_role;
revoke execute on function public.au_group_enrich_loop_push(uuid, uuid, jsonb)
  from public;

-- ---------------------------------------------------------------------------
-- 9. au_group_enrich_loop_finalize (depends on au_group_enrich_loop_staging)
-- ---------------------------------------------------------------------------
create or replace function public.au_group_enrich_loop_finalize(
  p_job_id              uuid,
  p_bankruptcy_id       uuid default null,
  p_pipeline_execution_id uuid default null
)
returns jsonb
language plpgsql
volatile security definer
set search_path to public
as $$
declare
  v_all     jsonb;
  v_matched text[] := array['matched', 'cached', 'dry_run'];
begin
  select coalesce(jsonb_agg(s.result order by s.creditor_id), '[]'::jsonb)
  into v_all
  from public.au_group_enrich_loop_staging s
  where s.job_id = p_job_id;

  delete from public.au_group_enrich_loop_staging where job_id = p_job_id;

  return jsonb_build_object(
    'bankruptcy_id',         p_bankruptcy_id,
    'enrich_job_id',         p_job_id,
    'pipeline_execution_id', p_pipeline_execution_id,
    'enrichment_summary', jsonb_build_object(
      'creditors_processed',      jsonb_array_length(v_all),
      'zoominfo_company_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where coalesce(e->>'zoominfo_company_id', '') <> ''
           or (e->>'zoominfo_status') = any (v_matched)
      ),
      'zoominfo_matched', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'matched'
      ),
      'cache_hits', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where (e->>'cache_hit')::boolean is true
      ),
      'no_match', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'no_match'
      ),
      'ambiguous', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'ambiguous'
      ),
      'no_contact_found', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' in ('no_contact_found', 'no_match')
          and coalesce((e->>'contacts_saved')::integer, 0) = 0
      ),
      'rate_limited', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'rate_limited'
      ),
      'contacts_saved', (
        select coalesce(sum((e->>'contacts_saved')::integer), 0)::integer
        from jsonb_array_elements(v_all) e
      ),
      'skipped_individual', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'skipped_individual'
      ),
      'errors', (
        select count(*)::integer from jsonb_array_elements(v_all) e
        where e->>'zoominfo_status' = 'error'
      )
    )
  );
end;
$$;

grant execute on function public.au_group_enrich_loop_finalize(uuid, uuid, uuid)
  to service_role;
revoke execute on function public.au_group_enrich_loop_finalize(uuid, uuid, uuid)
  from public;

-- ---------------------------------------------------------------------------
-- 10. au_group_evaluate_outreach_gates
-- ---------------------------------------------------------------------------
create or replace function public.au_group_evaluate_outreach_gates(
  p_creditor_id          uuid,
  p_suppress             boolean default false,
  p_dnc                  boolean default false,
  p_active_engagement    boolean default false,
  p_repeat_threshold     integer default null,
  p_repeat_window_months integer default null
)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_repeat           record;
  v_threshold        integer;
  v_window           integer;
  v_repeat_exposure  boolean := false;
  v_outreach_eligible boolean;
  v_reason           text := 'ok';
begin
  v_threshold := coalesce(
    p_repeat_threshold,
    public.au_group_config_int('repeat_exposure_threshold', 4)
  );
  v_window := coalesce(
    p_repeat_window_months,
    public.au_group_config_int('repeat_exposure_window_months', 18)
  );

  if p_creditor_id is not null then
    select *
    into v_repeat
    from public.au_group_check_repeat_exposure(p_creditor_id, v_threshold, v_window)
    limit 1;
    v_repeat_exposure := coalesce(v_repeat.is_repeat, false);
  else
    v_repeat          := null;
    v_repeat_exposure := false;
  end if;

  if p_suppress or p_dnc then
    v_outreach_eligible := false;
    v_reason := case when p_dnc then 'dnc' else 'suppressed' end;
  elsif p_active_engagement then
    v_outreach_eligible := false;
    v_reason := 'active_engagement';
  elsif v_repeat_exposure then
    v_outreach_eligible := false;
    v_reason := 'repeat_exposure';
  else
    v_outreach_eligible := true;
    v_reason := 'ok';
  end if;

  return jsonb_build_object(
    'creditor_id',       p_creditor_id,
    'suppress',          p_suppress,
    'dnc',               p_dnc,
    'active_engagement', p_active_engagement,
    'repeat_exposure',   v_repeat_exposure,
    'outreach_eligible', v_outreach_eligible,
    'gate_reason',       v_reason,
    'repeat_filing_count',
      case when p_creditor_id is not null then v_repeat.filing_count else null end,
    'suggested_message',
      case when p_creditor_id is not null then v_repeat.suggested_message else null end
  );
end;
$$;

grant execute on function public.au_group_evaluate_outreach_gates(uuid, boolean, boolean, boolean, integer, integer)
  to service_role;
revoke execute on function public.au_group_evaluate_outreach_gates(uuid, boolean, boolean, boolean, integer, integer)
  from public;

-- ---------------------------------------------------------------------------
-- 11. au_group_expand_import_rows
-- ---------------------------------------------------------------------------
create or replace function public.au_group_expand_import_rows(p_body jsonb)
returns jsonb
language plpgsql
stable security definer
set search_path to public
as $$
declare
  v_rows jsonb;
begin
  v_rows := coalesce(p_body->'rows', p_body->'body'->'rows');
  if v_rows is null or jsonb_typeof(v_rows) <> 'array' or jsonb_array_length(v_rows) = 0 then
    raise exception 'body.rows[] required' using errcode = 'P0001';
  end if;
  return jsonb_build_object('items', v_rows);
end;
$$;

grant execute on function public.au_group_expand_import_rows(jsonb)
  to service_role;
revoke execute on function public.au_group_expand_import_rows(jsonb)
  from public;

-- ---------------------------------------------------------------------------
-- 12. au_group_pick_document_parse_handoff
-- ---------------------------------------------------------------------------
create or replace function public.au_group_pick_document_parse_handoff(p_bankruptcy_id uuid)
returns jsonb
language sql
stable security definer
set search_path to public
as $$
  select jsonb_build_object(
    'bankruptcy_id', p_bankruptcy_id,
    'document_url', (
      select de.document_url
      from public.docket_entries de
      where de.bankruptcy_id = p_bankruptcy_id
        and nullif(btrim(de.document_url), '') is not null
      order by de.filed_at desc nulls last, de.created_at desc
      limit 1
    ),
    'schedule_f_queue_id', (
      select sfq.id::text
      from public.schedule_f_queue sfq
      where sfq.bankruptcy_id = p_bankruptcy_id
      order by sfq.created_at desc
      limit 1
    )
  );
$$;

grant execute on function public.au_group_pick_document_parse_handoff(uuid)
  to service_role;
revoke execute on function public.au_group_pick_document_parse_handoff(uuid)
  from public;
