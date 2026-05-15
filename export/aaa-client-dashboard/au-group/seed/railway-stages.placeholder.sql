-- Placeholder: run AFTER reconciling with your real Railway / Postgres schema.
-- The aaa-client-init skill normally prints exact INSERTs for the dashboard DB.
--
-- Typical intent: register project slug `au-group` so timeline / budget widgets resolve.
--
-- Example pattern (FICTITIOUS columns — replace with actual names from your schema):
--
-- INSERT INTO projects (slug, display_name, client_name, started_at, target_launch_at)
-- VALUES (
--   'au-group',
--   'Bankruptcy Creditor Intelligence Platform',
--   'Keith Woods',
--   '2026-05-13',
--   '2026-09-20'
-- )
-- ON CONFLICT (slug) DO NOTHING;
--
-- If your app lazy-inserts on GET /api/projects/au-group/stages, you may skip this file.

SELECT 1 AS placeholder_ready_to_replace_with_real_seed_sql;
