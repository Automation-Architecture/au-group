-- Clear manual review after human approval; keep sticky OR on form201 upsert (20260518130001).

create or replace function public.au_group_resolve_manual_review (
  p_review_id uuid,
  p_resolved_by text default null
) returns jsonb
language plpgsql
security invoker
set search_path to public
as $$
declare
  v_row public.manual_review_queue%rowtype;
  v_pending integer;
begin
  update public.manual_review_queue
  set
    status = 'resolved',
    assigned_to = coalesce(nullif(trim(p_resolved_by), ''), assigned_to),
    updated_at = now()
  where id = p_review_id
    and status in ('pending', 'in_review')
  returning * into v_row;

  if v_row.id is null then
    select * into v_row
    from public.manual_review_queue
    where id = p_review_id;

    if v_row.id is null then
      raise exception 'manual_review_queue row not found: %', p_review_id
        using errcode = 'P0002';
    end if;

    if v_row.status <> 'resolved' then
      raise exception 'manual review item is not resolvable (status=%)', v_row.status
        using errcode = 'P0001';
    end if;
  end if;

  if v_row.bankruptcy_id is not null then
    select count(*)::integer
    into v_pending
    from public.manual_review_queue q
    where q.bankruptcy_id = v_row.bankruptcy_id
      and q.status in ('pending', 'in_review');

    if v_pending = 0 then
      update public.bankruptcies
      set manual_review_required = false, updated_at = now()
      where id = v_row.bankruptcy_id;
    end if;
  end if;

  return jsonb_build_object(
    'review_id', v_row.id,
    'document_id', v_row.document_id,
    'bankruptcy_id', v_row.bankruptcy_id,
    'status', v_row.status,
    'bankruptcy_manual_review_required', (
      select b.manual_review_required
      from public.bankruptcies b
      where b.id = v_row.bankruptcy_id
    )
  );
end;
$$;

grant execute on function public.au_group_resolve_manual_review (uuid, text) to service_role;
