-- SYS-01B → SYS-02: pick first docket document_url for document parse handoff.

create or replace function public.au_group_pick_document_parse_handoff(p_bankruptcy_id uuid)
returns jsonb
language sql
stable
security definer
set search_path = public
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

comment on function public.au_group_pick_document_parse_handoff is
  'SYS-01B: resolve document_url + schedule_f_queue_id for SYS-02 handoff after PACER docket persist.';

grant execute on function public.au_group_pick_document_parse_handoff(uuid) to service_role;
revoke execute on function public.au_group_pick_document_parse_handoff(uuid) from public;
