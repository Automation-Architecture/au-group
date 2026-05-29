-- SYS-01: per-item RSS normalize (avoids huge batched PostgREST payloads).

create or replace function public.au_group_normalize_rss_item(p_item jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_item jsonb := coalesce(p_item, '{}'::jsonb);
  v_title text;
  v_content text;
  v_link text;
  v_clean text;
  v_case text;
  v_debtor text;
  v_chapter text;
  v_court text;
  v_guid text;
  v_doc_url text;
  v_signal integer;
  v_qualified boolean;
  v_is_business boolean;
  v_is_person boolean;
  v_excluded boolean;
  -- Cap HTML before regex (large PACER entries can exceed PostgREST limits when batched).
  c_max_html constant integer := 32768;
  c_max_clean constant integer := 12000;
begin
  v_title := btrim(regexp_replace(coalesce(v_item->>'title', ''), '\s+', ' ', 'g'));
  v_content := left(
    coalesce(
      v_item->>'content',
      v_item->>'contentSnippet',
      v_item->>'description',
      ''
    ),
    c_max_html
  );
  v_link := coalesce(v_item->>'link', '');
  v_clean := left(
    btrim(regexp_replace(regexp_replace(v_content, '<[^>]+>', ' ', 'g'), '\s+', ' ', 'g')),
    c_max_clean
  );

  v_case := (regexp_match(v_title, '\b(\d{2}-\d{4,6}(?:-[a-z0-9]+)*)\b', 'i'))[1];
  v_chapter := (regexp_match(v_clean, '\bchapter\s*(\d+)\b', 'i'))[1];
  v_court := (regexp_match(v_link, 'ecf\.([a-z]+)\.uscourts\.gov', 'i'))[1];
  v_guid := coalesce(v_item->>'guid', v_item->>'id', v_link);

  v_doc_url := (regexp_match(v_content, 'href=[''"]([^''"]*doc1[^''"]+)[''"]', 'i'))[1];
  if v_doc_url is null then
    v_doc_url := (regexp_match(v_content, 'https://ecf\.[^''" ]+/doc1/[^''" ]+', 'i'))[1];
  end if;

  v_debtor := btrim(regexp_replace(
    case when v_case is not null then regexp_replace(v_title, v_case, '', 'i') else v_title end,
    '\s+', ' ', 'g'
  ));
  v_is_business := v_debtor ~* '(llc|inc|corp|corporation|ltd|lp|holdings|company|co\.|group|enterprises)';
  v_is_person := v_debtor ~ '^[A-Z][a-z]+ [A-Z][a-z]+' and not v_is_business;
  v_excluded := v_clean ~* '(certificate of credit counseling|certificate of mailing|personal financial management|proof of claim|meeting of creditors|\[schedules\]|chapter 13 plan|notice of hearing)';

  v_signal := 0;
  if v_clean ~* 'voluntary petition' then v_signal := v_signal + 40; end if;
  if v_clean ~* 'petition filed' then v_signal := v_signal + 30; end if;
  if v_clean ~* 'chapter 11' then v_signal := v_signal + 20; end if;
  if public.au_group_schedule_f_keyword_hit(v_clean) then v_signal := v_signal + 15; end if;

  v_qualified := v_signal >= 40
    and not v_is_person
    and v_case is not null
    and v_guid is not null
    and not v_excluded;

  return jsonb_build_object(
    'case_number', v_case,
    'debtor_name', nullif(v_debtor, ''),
    'chapter', v_chapter,
    'court_id', v_court,
    'filing_date', left(coalesce(v_item->>'isoDate', v_item->>'pubDate', ''), 10),
    'rss_guid', v_guid,
    'document_url', v_doc_url,
    'unique_key', coalesce(v_court, '') || ':' || coalesce(v_case, '') || ':' || coalesce(v_guid, ''),
    'signal_score', case when v_excluded then 0 else v_signal end,
    'is_business', v_is_business,
    'is_likely_person', v_is_person,
    'is_excluded_event', v_excluded,
    'is_qualified', v_qualified,
    'raw_content', left(v_clean, 4000)
  );
end;
$$;

-- Batch wrapper (SQL tests only); n8n should call au_group_normalize_rss_item per feed row.
create or replace function public.au_group_normalize_rss_items(p_items jsonb)
returns jsonb
language sql
stable
security definer
set search_path = public
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

grant execute on function public.au_group_normalize_rss_item(jsonb) to service_role;
revoke execute on function public.au_group_normalize_rss_item(jsonb) from public;

grant execute on function public.au_group_normalize_rss_items(jsonb) to service_role;
revoke execute on function public.au_group_normalize_rss_items(jsonb) from public;
