-- KD-65: Port SYS-03 ZoomInfo/contact shaping from Code nodes to config-friendly RPCs.

create or replace function public.au_group_build_lookup_context(
  p_row jsonb,
  p_ctx jsonb
)
returns jsonb
language sql
immutable
as $$
  select coalesce(p_row, '{}'::jsonb)
    || coalesce(p_ctx, '{}'::jsonb)
    || jsonb_build_object(
      'lookup_name', btrim(coalesce(p_row->>'creditor_name', p_row->>'name', '')),
      'lookup_address', coalesce(p_row->>'address', p_row->>'creditor_address'),
      'dry_run', coalesce((p_row->>'dry_run')::boolean, false)
        or coalesce((p_ctx->>'dry_run')::boolean, false)
    );
$$;

create or replace function public.au_group_normalize_zoominfo_company_response(
  p_body jsonb,
  p_ctx jsonb,
  p_status_code integer default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_ctx jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body jsonb;
  v_data jsonb;
  v_candidates jsonb;
  v_state_hint text;
  v_top jsonb;
  v_second jsonb;
  v_top_score numeric;
  v_second_score numeric;
  v_attrs jsonb;
  v_company_id text;
  v_revenue numeric;
  v_employees numeric;
  v_industry text;
  v_hq text;
  i integer;
  v_item jsonb;
  v_attrs_i jsonb;
  v_hq_i text;
  v_conf numeric;
  v_geo numeric;
  v_score numeric;
  v_best jsonb;
  v_best_score numeric := -1;
  v_second_best_score numeric := -1;
  v_err text;
begin
  if p_status_code = 429 then
    return v_ctx || jsonb_build_object('statusCode', 429);
  end if;

  v_body := coalesce(p_body, '{}'::jsonb);
  v_err := coalesce(v_body->>'error', v_body->>'message');
  if v_err is not null and v_err <> '' then
    return v_ctx || jsonb_build_object(
      'zoominfo_status', 'error',
      'zoominfo_match_status', 'error',
      'zoominfo_error', left(v_err, 500),
      'zoominfo_company_id', null,
      'match_confidence', null,
      'cache_hit', false
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
      'zoominfo_status', 'no_match',
      'zoominfo_match_status', 'no_match',
      'zoominfo_company_id', null,
      'match_confidence', null,
      'cache_hit', false,
      'skipped_reason', 'no_match'
    );
  end if;

  v_state_hint := upper(left(coalesce(v_ctx->>'creditor_state', ''), 2));

  for i in 0 .. jsonb_array_length(v_candidates) - 1 loop
    v_item := v_candidates->i;
    v_attrs_i := coalesce(v_item->'attributes', v_item);
    v_hq_i := upper(coalesce(
      v_attrs_i->>'headquarters',
      v_attrs_i->>'headquartersState',
      v_attrs_i->>'state',
      ''
    ));
    v_conf := coalesce(
      nullif(v_attrs_i->>'matchScore', '')::numeric,
      nullif(v_attrs_i->>'confidence', '')::numeric,
      nullif(v_attrs_i->>'score', '')::numeric,
      0.5
    );
    v_geo := 0;
    if v_state_hint <> '' and position(v_state_hint in v_hq_i) > 0 then
      v_geo := 1;
    end if;
    v_score := v_conf + v_geo * 0.5;

    if v_score > v_best_score then
      v_second_best_score := v_best_score;
      v_best_score := v_score;
      v_best := jsonb_build_object('item', v_item, 'attrs', v_attrs_i, 'score', v_score);
    elsif v_score > v_second_best_score then
      v_second_best_score := v_score;
    end if;
  end loop;

  if v_second_best_score >= 0 and abs(v_best_score - v_second_best_score) < 0.05 then
    return v_ctx || jsonb_build_object(
      'zoominfo_status', 'ambiguous',
      'zoominfo_match_status', 'ambiguous',
      'zoominfo_company_id', null,
      'match_confidence', v_best_score,
      'cache_hit', false,
      'skipped_reason', 'ambiguous_match'
    );
  end if;

  v_attrs := v_best->'attrs';
  v_item := v_best->'item';
  v_revenue := coalesce(
    nullif(v_attrs->>'revenue', '')::numeric,
    nullif(v_attrs->>'annualRevenue', '')::numeric
  );
  v_employees := coalesce(
    nullif(v_attrs->>'employeeCount', '')::numeric,
    nullif(v_attrs->>'employees', '')::numeric
  );
  v_industry := coalesce(v_attrs->>'industry', v_attrs->>'primaryIndustry');
  v_company_id := coalesce(v_item->>'id', v_attrs->>'companyId');
  v_hq := coalesce(v_attrs->>'headquarters', v_attrs->>'headquartersState');

  return v_ctx || jsonb_build_object(
    'zoominfo_status', 'matched',
    'zoominfo_match_status', 'matched',
    'zoominfo_company_id', v_company_id,
    'match_confidence', v_best_score,
    'normalized_name', coalesce(v_attrs->>'name', v_attrs->>'companyName', v_ctx->>'normalized_name'),
    'company_revenue', v_revenue,
    'company_employee_count', v_employees,
    'company_industry', v_industry,
    'company_headquarters', v_hq,
    'zoominfo_firmographics', jsonb_build_object(
      'revenue', v_revenue,
      'employee_count', v_employees,
      'industry', v_industry,
      'headquarters', v_hq
    ),
    'cache_hit', false,
    'raw_zoominfo', v_body
  );
end;
$$;

create or replace function public.au_group_normalize_zoominfo_contact_response(
  p_body jsonb,
  p_ctx jsonb,
  p_status_code integer default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_base jsonb := coalesce(p_ctx, '{}'::jsonb);
  v_body jsonb := coalesce(p_body, '{}'::jsonb);
  v_data jsonb;
  v_raw jsonb;
  v_contacts jsonb := '[]'::jsonb;
  i integer;
  v_item jsonb;
  v_attrs jsonb;
  v_first text;
  v_last text;
  v_full text;
  v_eng numeric;
  v_sorted jsonb;
begin
  if p_status_code = 429 then
    return v_base || jsonb_build_object('statusCode', 429, 'contacts_saved', 0);
  end if;

  if coalesce(v_body->>'error', v_body->>'message') is not null then
    return v_base || jsonb_build_object(
      'contacts_saved', 0,
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
    v_item := v_raw->i;
    v_attrs := coalesce(v_item->'attributes', v_item);
    v_first := coalesce(v_attrs->>'firstName', v_attrs->>'first_name', '');
    v_last := coalesce(v_attrs->>'lastName', v_attrs->>'last_name', '');
    v_full := coalesce(
      v_attrs->>'fullName',
      v_attrs->>'name',
      nullif(btrim(v_first || ' ' || v_last), ''),
      'Unknown'
    );
    if v_full is null or v_full = 'Unknown' then
      continue;
    end if;
    v_eng := coalesce(
      nullif(v_attrs->>'engagementScore', '')::numeric,
      nullif(v_attrs->>'contactAccuracyScore', '')::numeric,
      nullif(v_attrs->>'score', '')::numeric,
      0
    );
    v_contacts := v_contacts || jsonb_build_array(jsonb_build_object(
      'full_name', v_full,
      'title', coalesce(v_attrs->>'jobTitle', v_attrs->>'title', v_attrs->>'primaryTitle'),
      'email', coalesce(v_attrs->>'email', v_attrs->>'emailAddress'),
      'phone', coalesce(v_attrs->>'phone', v_attrs->>'directPhone', v_attrs->>'mobilePhone'),
      'engagement_score', v_eng,
      'company_revenue', v_base->'company_revenue',
      'company_employee_count', v_base->'company_employee_count',
      'company_industry', v_base->'company_industry'
    ));
  end loop;

  select coalesce(jsonb_agg(e order by (e->>'engagement_score')::numeric desc nulls last), '[]'::jsonb)
  into v_sorted
  from (
    select e from jsonb_array_elements(v_contacts) e limit 3
  ) sub;

  return v_base || jsonb_build_object(
    'contacts_payload', v_sorted,
    'contacts_saved', jsonb_array_length(v_sorted),
    'zoominfo_status', case
      when jsonb_array_length(v_sorted) > 0 then v_base->>'zoominfo_status'
      when v_base->>'zoominfo_status' = 'matched' then 'no_contact_found'
      else v_base->>'zoominfo_status'
    end
  );
end;
$$;

grant execute on function public.au_group_build_lookup_context(jsonb, jsonb) to service_role;
revoke execute on function public.au_group_build_lookup_context(jsonb, jsonb) from public;

grant execute on function public.au_group_normalize_zoominfo_company_response(jsonb, jsonb, integer) to service_role;
revoke execute on function public.au_group_normalize_zoominfo_company_response(jsonb, jsonb, integer) from public;

grant execute on function public.au_group_normalize_zoominfo_contact_response(jsonb, jsonb, integer) to service_role;
revoke execute on function public.au_group_normalize_zoominfo_contact_response(jsonb, jsonb, integer) from public;
