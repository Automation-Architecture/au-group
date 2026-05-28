-- KD-22 / FR-1 / FR-5: Keith-editable suppression lists + outreach gate RPC for SYS-05.

create table if not exists public.au_group_suppression_lenders (
  id bigserial primary key,
  pattern text not null,
  active boolean not null default true,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.au_group_suppression_keywords (
  id bigserial primary key,
  pattern text not null,
  active boolean not null default true,
  notes text,
  created_at timestamptz not null default now()
);

alter table public.au_group_suppression_lenders enable row level security;
alter table public.au_group_suppression_keywords enable row level security;

create or replace function public.au_group_is_suppressed_creditor_name(p_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.au_group_suppression_lenders l
    where l.active is true
      and coalesce(trim(p_name), '') ilike '%' || l.pattern || '%'
  )
  or exists (
    select 1
    from public.au_group_suppression_keywords k
    where k.active is true
      and coalesce(trim(p_name), '') ilike '%' || k.pattern || '%'
  );
$$;

grant execute on function public.au_group_is_suppressed_creditor_name (text) to service_role;
revoke execute on function public.au_group_is_suppressed_creditor_name (text) from public;

-- Outreach eligibility for SYS-05 (replaces inline Code where possible).
create or replace function public.au_group_evaluate_outreach_gates(
  p_creditor_id uuid,
  p_suppress boolean default false,
  p_dnc boolean default false,
  p_active_engagement boolean default false,
  p_repeat_threshold integer default null,
  p_repeat_window_months integer default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_repeat record;
  v_threshold integer;
  v_window integer;
  v_repeat_exposure boolean := false;
  v_outreach_eligible boolean;
  v_reason text := 'ok';
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
    from public.au_group_check_repeat_exposure(
      p_creditor_id,
      v_threshold,
      v_window
    )
    limit 1;
    v_repeat_exposure := coalesce(v_repeat.is_repeat, false);
  else
    v_repeat := null;
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
    'creditor_id', p_creditor_id,
    'suppress', p_suppress,
    'dnc', p_dnc,
    'active_engagement', p_active_engagement,
    'repeat_exposure', v_repeat_exposure,
    'outreach_eligible', v_outreach_eligible,
    'gate_reason', v_reason,
    'repeat_filing_count',
      case when p_creditor_id is not null then v_repeat.filing_count else null end,
    'suggested_message',
      case when p_creditor_id is not null then v_repeat.suggested_message else null end
  );
end;
$$;

comment on function public.au_group_evaluate_outreach_gates is
  'SYS-05: centralize DNC / engagement / repeat-exposure gates (FR-5.4, FR-5.5, FR-6.3).';

grant execute on function public.au_group_evaluate_outreach_gates (
  uuid, boolean, boolean, boolean, integer, integer
) to service_role;
revoke execute on function public.au_group_evaluate_outreach_gates (
  uuid, boolean, boolean, boolean, integer, integer
) from public;

insert into public.au_group_runtime_config (config_key, config_value, notes)
values
  ('repeat_exposure_threshold', '4', 'FR-6.3: filings in window before suppress auto-send'),
  ('repeat_exposure_window_months', '18', 'FR-6.3: rolling window months')
on conflict (config_key) do nothing;
