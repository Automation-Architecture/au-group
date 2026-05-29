-- KD-68 / KD-63: Schedule F keyword config + RSS normalize (SYS-01 no-Code).

create table if not exists public.au_group_schedule_f_keywords (
  id bigserial primary key,
  pattern text not null,
  active boolean not null default true,
  notes text,
  created_at timestamptz not null default now()
);

alter table public.au_group_schedule_f_keywords enable row level security;

insert into public.au_group_schedule_f_keywords (pattern, notes)
select v.pattern, v.notes
from (values
  ('schedule f', 'Schedule F filing'),
  ('statement of financial affairs', 'SOFA'),
  ('list of creditors', 'creditor list amendment')
) as v(pattern, notes)
where not exists (select 1 from public.au_group_schedule_f_keywords limit 1);

create or replace function public.au_group_schedule_f_keyword_hit(p_text text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.au_group_schedule_f_keywords k
    where k.active is true
      and coalesce(trim(p_text), '') ilike '%' || k.pattern || '%'
  );
$$;

create or replace function public.au_group_diff_pacer_favorites(
  p_favorites jsonb,
  p_bankruptcy_ids uuid[] default null
)
returns jsonb
language sql
stable
security definer
set search_path = public
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

-- RSS item normalization (replaces SYS-01 Code node; ports core JS rules).
create or replace function public.au_group_normalize_rss_items(p_items jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_out jsonb := '[]'::jsonb;
  v_item jsonb;
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
  i integer;
begin
  for i in 0 .. coalesce(jsonb_array_length(p_items), 0) - 1 loop
    v_item := p_items->i;
    v_title := btrim(regexp_replace(coalesce(v_item->>'title', ''), '\s+', ' ', 'g'));
    v_content := coalesce(v_item->>'content', v_item->>'contentSnippet', v_item->>'description', '');
    v_link := coalesce(v_item->>'link', '');
    v_clean := btrim(regexp_replace(regexp_replace(v_content, '<[^>]+>', ' ', 'g'), '\s+', ' ', 'g'));
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
    v_qualified := v_signal >= 40 and not v_is_person and v_case is not null and v_guid is not null and not v_excluded;

    v_out := v_out || jsonb_build_array(jsonb_build_object(
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
    ));
  end loop;

  return jsonb_build_object('items', v_out);
end;
$$;

grant execute on function public.au_group_schedule_f_keyword_hit(text) to service_role;
revoke execute on function public.au_group_schedule_f_keyword_hit(text) from public;

grant execute on function public.au_group_diff_pacer_favorites(jsonb, uuid[]) to service_role;
revoke execute on function public.au_group_diff_pacer_favorites(jsonb, uuid[]) from public;

grant execute on function public.au_group_normalize_rss_items(jsonb) to service_role;
revoke execute on function public.au_group_normalize_rss_items(jsonb) from public;

create or replace function public.au_group_expand_import_rows(p_body jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
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

grant execute on function public.au_group_expand_import_rows(jsonb) to service_role;
revoke execute on function public.au_group_expand_import_rows(jsonb) from public;
