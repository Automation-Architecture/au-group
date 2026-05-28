-- SYS-01 RSS normalize RPC smoke tests (run against Supabase SQL editor or psql).
-- Usage: psql $DATABASE_URL -f scripts/supabase/test-rss-normalize.sql

\set ON_ERROR_STOP on

do $$
declare
  v jsonb;
  v_batch jsonb;
begin
  -- Qualified Ch.11 business voluntary petition with doc1 link
  v := public.au_group_normalize_rss_item(
    jsonb_build_object(
      'title', '24-12345 Acme Holdings LLC',
      'link', 'https://ecf.nysb.uscourts.gov/cgi-bin/rss_outside.pl',
      'guid', 'test-guid-001',
      'isoDate', '2026-05-28T10:00:00Z',
      'content', '<p>Voluntary Petition filed. Chapter 11. '
        || '<a href="https://ecf.nysb.uscourts.gov/doc1/1234567890">Petition</a></p>'
    )
  );
  assert (v->>'case_number') = '24-12345', 'case_number';
  assert (v->>'court_id') = 'nysb', 'court_id';
  assert (v->>'chapter') = '11', 'chapter';
  assert (v->>'is_qualified')::boolean is true, 'is_qualified';
  assert (v->>'signal_score')::int >= 40, 'signal_score';
  assert (v->>'document_url') like '%doc1/%', 'document_url';
  assert (v->>'is_business')::boolean is true, 'is_business';

  -- Excluded event type (proof of claim)
  v := public.au_group_normalize_rss_item(
    jsonb_build_object(
      'title', '24-99999 Some Corp',
      'link', 'https://ecf.nysb.uscourts.gov/',
      'content', 'Proof of Claim filed by creditor.'
    )
  );
  assert (v->>'is_excluded_event')::boolean is true, 'excluded';
  assert (v->>'is_qualified')::boolean is false, 'not qualified when excluded';
  assert (v->>'signal_score')::int = 0, 'zero signal when excluded';

  -- Likely individual debtor (not business)
  v := public.au_group_normalize_rss_item(
    jsonb_build_object(
      'title', '24-55555 John Smith',
      'link', 'https://ecf.nysb.uscourts.gov/',
      'content', 'Voluntary Petition filed Chapter 11'
    )
  );
  assert (v->>'is_likely_person')::boolean is true, 'person';
  assert (v->>'is_qualified')::boolean is false, 'person not qualified';

  -- Batch wrapper returns items array
  v_batch := public.au_group_normalize_rss_items(
    jsonb_build_array(
      jsonb_build_object('title', '24-1 Test LLC', 'link', 'https://ecf.deb.uscourts.gov/', 'content', 'Voluntary Petition Chapter 11'),
      jsonb_build_object('title', '24-2 Other LLC', 'link', 'https://ecf.deb.uscourts.gov/', 'content', 'Certificate of Mailing')
    )
  );
  assert jsonb_array_length(v_batch->'items') = 2, 'batch length';
  assert (v_batch->'items'->0->>'court_id') = 'deb', 'batch court_id';

  raise notice 'test-rss-normalize.sql: all assertions passed';
end;
$$;
