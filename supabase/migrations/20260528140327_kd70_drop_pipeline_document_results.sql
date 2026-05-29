-- KD-70: Remove legacy SYS-02 table superseded by document_parse_results (20260520140000).
-- Prod pre-check (2026-05-28): 0 rows; no repo references.
-- Version aligned with prod schema_migrations (MCP apply 20260528140327).

drop table if exists public.pipeline_document_results cascade;
