-- Restore the intended ON DELETE behaviour on three foreign keys to
-- public.bankruptcies that drifted to NO ACTION in the live DB (the tables were
-- created out-of-repo without the ON DELETE clause the declaring migrations
-- specify). Source of intent:
--   creditors.source_bankruptcy_id       -> SET NULL  (20260529145000)
--   bankruptcy_case_status.bankruptcy_id -> CASCADE   (20260524110000)
--   docket_entries.bankruptcy_id         -> CASCADE   (20260524110000)
--
-- Without this, deleting a bankruptcies row fails with 23503, which breaks
-- integration-test teardown (leaking ITEST-* rows) and any pipeline path that
-- deletes a bankruptcy. Discovered 2026-06-01 during a live parse.py E2E run.
-- Idempotent: drop-if-exists + re-add so it is safe to re-apply / db-reset.
--
-- Each table's drop + re-add is a SINGLE ALTER TABLE so the change is atomic per
-- table (no window without the constraint, even under autocommit) and the table
-- lock is taken once rather than twice.

alter table public.creditors
  drop constraint if exists creditors_source_bankruptcy_id_fkey,
  add constraint creditors_source_bankruptcy_id_fkey
    foreign key (source_bankruptcy_id) references public.bankruptcies (id)
    on delete set null;

alter table public.bankruptcy_case_status
  drop constraint if exists bankruptcy_case_status_bankruptcy_id_fkey,
  add constraint bankruptcy_case_status_bankruptcy_id_fkey
    foreign key (bankruptcy_id) references public.bankruptcies (id)
    on delete cascade;

alter table public.docket_entries
  drop constraint if exists docket_entries_bankruptcy_id_fkey,
  add constraint docket_entries_bankruptcy_id_fkey
    foreign key (bankruptcy_id) references public.bankruptcies (id)
    on delete cascade;
