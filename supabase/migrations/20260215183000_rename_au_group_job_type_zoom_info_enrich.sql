-- Align au_group_job_type enum label with snake_case (table: zoom_info_contacts).
-- Idempotent: no-op if the old label was never created.
do $$
begin
  if exists (
    select 1
    from pg_enum e
    join pg_type t on e.enumtypid = t.oid
    where t.typname = 'au_group_job_type'
      and e.enumlabel = 'zoominfo_enrich'
  ) then
    alter type public.au_group_job_type rename value 'zoominfo_enrich' to 'zoom_info_enrich';
  end if;
end $$;
