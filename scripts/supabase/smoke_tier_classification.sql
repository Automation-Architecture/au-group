-- KD-21: smoke tier classification RPCs + golden fixture accuracy (NFR-2.2 >= 95%).
\set ON_ERROR_STOP on

do $$
declare
  v_tier smallint;
  v_name text;
  v_total int := 0;
  v_correct int := 0;
  v_pct numeric;
begin
  -- Boundary cases (EC-2.3)
  select c.tier, c.tier_name
  into v_tier, v_name
  from public.au_group_classify_company_tier(1000000000::numeric, null::integer) c;

  if v_tier <> 1 then
    raise exception 'KD-21 smoke: expected tier 1 at $1B revenue, got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(100000000::numeric, null::integer) c;

  if v_tier <> 2 then
    raise exception 'KD-21 smoke: expected tier 2 at $100M revenue (EC-2.3), got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(null::numeric, 500::integer) c;

  if v_tier <> 2 then
    raise exception 'KD-21 smoke: expected tier 2 at 500 employees, got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(99999999::numeric, 499::integer) c;

  if v_tier <> 3 then
    raise exception 'KD-21 smoke: expected tier 3 for SMB, got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(null::numeric, 5000::integer) c;

  if v_tier <> 1 then
    raise exception 'KD-21 smoke: expected tier 1 at 5000 employees, got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(null::numeric, null::integer) c;

  if v_tier <> 3 then
    raise exception 'KD-21 smoke: expected tier 3 for null firmographics, got %', v_tier;
  end if;

  select c.tier into v_tier
  from public.au_group_classify_company_tier(100000000::numeric, 5000::integer) c;

  if v_tier <> 1 then
    raise exception 'KD-21 smoke: expected tier 1 when mixed signals favor enterprise, got %', v_tier;
  end if;

  -- Title lists match PRD seed counts
  if (select count(*) from public.au_group_list_tier_contact_titles(1)) < 4 then
    raise exception 'KD-21 smoke: expected at least 4 enterprise titles';
  end if;

  if (select count(*) from public.au_group_list_tier_contact_titles(2)) < 4 then
    raise exception 'KD-21 smoke: expected at least 4 mid-market titles';
  end if;

  if (select count(*) from public.au_group_list_tier_contact_titles(3)) < 5 then
    raise exception 'KD-21 smoke: expected at least 5 SMB titles';
  end if;

  if not (
    select exists (
      select 1
      from public.au_group_list_tier_contact_titles(1) t
      where t.title = 'VP of Finance'
    )
  ) then
    raise exception 'KD-21 smoke: missing VP of Finance in tier 1 titles';
  end if;

  -- Config snapshot
  if public.au_group_get_tier_targeting_config() -> 'tiers' is null then
    raise exception 'KD-21 smoke: get_tier_targeting_config returned null tiers';
  end if;

  -- Golden fixture cases (20 labeled revenue/employee → tier expectations)
  select count(*)::int, count(*) filter (where ok)::int
  into v_total, v_correct
  from (
    values
      (1000000000::numeric, null::integer, 1::smallint),
      (null::numeric, 5000::integer, 1::smallint),
      (100000000::numeric, null::integer, 2::smallint),
      (null::numeric, 500::integer, 2::smallint),
      (99999999::numeric, 499::integer, 3::smallint),
      (null::numeric, null::integer, 3::smallint),
      (100000000::numeric, 5000::integer, 1::smallint),
      (1500000000::numeric, 100::integer, 1::smallint),
      (750000000::numeric, 3000::integer, 2::smallint),
      (50000000::numeric, 10000::integer, 1::smallint),
      (100000000::numeric, 499::integer, 2::smallint),
      (999999999::numeric, 4999::integer, 2::smallint),
      (1000000000::numeric, 4999::integer, 1::smallint),
      (100000000::numeric, 5000::integer, 1::smallint),
      (500000000::numeric, null::integer, 2::smallint),
      (null::numeric, 2500::integer, 2::smallint),
      (25000000::numeric, null::integer, 3::smallint),
      (null::numeric, 100::integer, 3::smallint),
      (2000000000::numeric, 8000::integer, 1::smallint),
      (100000000::numeric, 500::integer, 2::smallint)
  ) as g(revenue, employees, expected_tier)
  cross join lateral (
    select (
      select c.tier
      from public.au_group_classify_company_tier(g.revenue, g.employees) c
    ) = g.expected_tier as ok
  ) x;

  if v_total = 0 then
    raise exception 'KD-21 smoke: golden fixture produced zero cases';
  end if;

  v_pct := round((v_correct::numeric / v_total::numeric) * 100, 2);

  if v_pct < 95 then
    raise exception 'KD-21 smoke: golden accuracy % < 95%% (% / %)', v_pct, v_correct, v_total;
  end if;

  -- set_creditor_company_tier error paths
  if public.au_group_set_creditor_company_tier(null, 2) then
    raise exception 'KD-21 smoke: expected false for null creditor_id';
  end if;

  if public.au_group_set_creditor_company_tier(gen_random_uuid(), 0) then
    raise exception 'KD-21 smoke: expected false for invalid tier 0';
  end if;

  if (select count(*) from public.au_group_list_tier_contact_titles(99)) <> 0 then
    raise exception 'KD-21 smoke: expected empty titles for invalid tier 99';
  end if;

  -- Persist tier on creditor (unscoped + bankruptcy-scoped)
  declare
    v_bid uuid;
    v_creditor_id uuid;
    v_ok boolean;
    v_case text := 'KD21-SMOKE-' || replace(gen_random_uuid()::text, '-', '');
  begin
    insert into public.creditors (name, is_company)
    values ('KD21 Tier Smoke Creditor Unscoped', true)
    returning id into v_creditor_id;

    v_ok := public.au_group_set_creditor_company_tier(v_creditor_id, 2);
    if not v_ok then
      raise exception 'KD-21 smoke: set_creditor_company_tier returned false';
    end if;

    delete from public.creditors where id = v_creditor_id;

    insert into public.bankruptcies (
      case_number,
      debtor_name,
      filing_date,
      court_district,
      chapter_type,
      state
    )
    values (
      v_case,
      'KD21 Tier Smoke Debtor',
      current_date,
      'D. Delaware',
      '11',
      'DE'
    )
    returning id into v_bid;

    insert into public.creditors (name, is_company)
    values ('KD21 Tier Smoke Creditor Scoped', true)
    returning id into v_creditor_id;

    insert into public.bankruptcy_creditors (bankruptcy_id, creditor_id)
    values (v_bid, v_creditor_id);

    if public.au_group_set_creditor_company_tier(v_creditor_id, 2, gen_random_uuid()) then
      raise exception 'KD-21 smoke: set_creditor_company_tier should reject wrong bankruptcy_id';
    end if;

    v_ok := public.au_group_set_creditor_company_tier(v_creditor_id, 2, v_bid);
    if not v_ok then
      raise exception 'KD-21 smoke: set_creditor_company_tier failed for scoped bankruptcy';
    end if;

    select c.company_tier into v_tier
    from public.creditors c
    where c.id = v_creditor_id;

    if v_tier <> 2 then
      raise exception 'KD-21 smoke: expected company_tier 2 on creditor, got %', v_tier;
    end if;

    delete from public.creditors where id = v_creditor_id;
    delete from public.bankruptcies where id = v_bid;
  end;

  raise notice 'KD-21 tier classification smoke OK (% / % = %%% correct)', v_correct, v_total, v_pct;
end;
$$;
