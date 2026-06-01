# Supabase Live Schema State — Divergence Reference

**Project:** `umivttszdnsrosbqryia` (AU Group)  
**Last audited:** 2026-05-30  
**Why this exists:** The live Supabase DB has drifted from the local migration files through ad-hoc MCP `apply_migration` + `execute_sql` calls made during early development. Any engineer writing new migrations or debugging schema errors must treat this doc as ground truth alongside querying the live DB directly.

---

## TL;DR — the three things most likely to bite you

1. **Status enum is `processing_job_status`, not `au_group_job_status`.** The value `pending` does not exist; use `queued`. Cast explicitly: `'queued'::processing_job_status`.
2. **`processing_jobs` has two extra columns** not in the local migration files: `worker_name text` and `job_payload jsonb`.
3. **Migration `20260530120000` is a phantom** — registered in `schema_migrations` but its SQL never executed. Do not re-apply; start new migrations at `20260530120001` or later.

---

## 1. Enum divergence

### `processing_jobs.status`

| Local migration files say | Live DB has |
|---|---|
| Type: `public.au_group_job_status` | Type: `processing_job_status` |
| Values: `pending`, `running`, `completed`, `failed` | Values: `queued`, `running`, `completed`, `failed`, `retrying` |

**Rule for new migrations:** always cast explicitly and use the live values:

```sql
where status = 'queued'::processing_job_status
where status = 'running'::processing_job_status
-- etc.
```

The `au_group_job_status` type still exists on the live DB as a legacy object but is NOT what `processing_jobs.status` uses.

### `processing_jobs.job_type`

The `au_group_job_type` enum is consistent between local files and live DB:

```
pacer_poll | document_parse | zoom_info_enrich | salesforce_push | document_intelligence
```

---

## 2. Extra columns on `processing_jobs`

The live DB has two columns not present in any local migration file:

| Column | Type | Nullable |
|---|---|---|
| `worker_name` | `text` | yes |
| `job_payload` | `jsonb` | yes |

These were added via a direct MCP call in a prior session. A reconciliation migration that adds them to the local history is needed before any CI `db reset` or fresh-deploy will succeed.

---

## 3. Out-of-repo migrations

The following versions are registered in `supabase_migrations.schema_migrations` on the live DB but have **no corresponding file** in `supabase/migrations/`:

| Version | Status |
|---|---|
| `20260530120000` | **Phantom** — SQL never ran (MCP bug: version registered before SQL executed; execution failed on wrong enum type) |
| `20260531100000` | Unknown — applied in a prior session; SQL not recovered |
| `20260602150100` | Unknown — applied in a prior session; SQL not recovered |
| `20260602150201` | Unknown — applied in a prior session; SQL not recovered |
| `20260602150300` | Unknown — applied in a prior session; SQL not recovered |
| `20260602150400` | Unknown — applied in a prior session; SQL not recovered |

**Action required:** use `execute_sql` + `pg_get_functiondef` / `information_schema` to reverse-engineer each version and create the corresponding local file. Until this is done, `supabase db reset` and CI migration replay will diverge from the live schema.

To recover a version's DDL:
```sql
-- functions
select proname, pg_get_functiondef(oid)
from pg_proc where pronamespace = (select oid from pg_namespace where nspname = 'public');

-- indexes added after a given timestamp (approximate via index name prefix)
select indexname, indexdef from pg_indexes where schemaname = 'public';

-- table column changes
select column_name, udt_name, column_default, is_nullable
from information_schema.columns
where table_schema = 'public' order by table_name, ordinal_position;
```

---

## 4. `processing_jobs` indexes — live DB state (2026-05-30)

```
idx_processing_jobs_bankruptcy              btree (bankruptcy_id)
idx_processing_jobs_bankruptcy_id           btree (bankruptcy_id)  ← duplicate; candidate for cleanup
idx_processing_jobs_one_queued_per_bankruptcy_type
                                            UNIQUE btree (bankruptcy_id, job_type)
                                            WHERE status = 'queued'
idx_processing_jobs_one_running_doc_intel   UNIQUE btree (bankruptcy_id, job_type)
                                            WHERE status = 'running' AND job_type = 'document_intelligence'
idx_processing_jobs_one_running_document_parse
                                            UNIQUE btree (bankruptcy_id)
                                            WHERE status = 'running' AND job_type = 'document_parse'
idx_processing_jobs_one_running_pacer_poll  UNIQUE btree (bankruptcy_id)
                                            WHERE status = 'running' AND job_type = 'pacer_poll'
idx_processing_jobs_one_running_salesforce_push
                                            UNIQUE btree (bankruptcy_id)
                                            WHERE status = 'running' AND job_type = 'salesforce_push'
idx_processing_jobs_one_running_zoom_info_enrich
                                            UNIQUE btree (bankruptcy_id)
                                            WHERE status = 'running' AND job_type = 'zoom_info_enrich'
idx_processing_jobs_status                  btree (status)
processing_jobs_pkey                        UNIQUE btree (id)
```

---

## 5. MCP `apply_migration` phantom-registration behaviour

The Supabase MCP tool inserts the migration version into `schema_migrations` **before** executing the SQL body. If the SQL fails, the version is permanently registered but the DDL was never applied. This creates a phantom entry that blocks future `apply_migration` calls for the same version.

**Workaround:** use the next sequential timestamp for the corrected migration. Do not delete the phantom entry from `schema_migrations` (it would re-enable the broken version).

**Affected version in this repo:** `20260530120000` (failed on `'pending'::processing_job_status` — type doesn't exist; corrected version is `20260530120001`).

---

## 6. Reconciliation plan

Priority order for bringing local files in sync with live DB:

1. **Recover the 5 unknown out-of-repo migrations** (`20260531100000`, `20260602150100`–`150400`) via DDL introspection and create stub migration files.
2. **Add `worker_name` + `job_payload` columns** to a local migration so `db reset` produces a matching schema.
3. **Document `processing_job_status` type origin** — trace which ad-hoc call created it and add the `CREATE TYPE` to a migration so CI can replay it.
4. After (1)–(3): validate with `supabase db reset --local` against the full migration history.

---

## 7. Foreign-key `ON DELETE` drift on `bankruptcies` references (2026-06-01)

Three FKs referencing `public.bankruptcies` were created in the live DB **without** the `ON DELETE` clause their declaring migrations specify — they sit at `NO ACTION` instead. Any attempt to `DELETE` a `bankruptcies` row is blocked with `23503` until every referencing child row is removed by hand. This is what silently leaked `ITEST-*` integration rows (teardown's `DELETE bankruptcies` failed) and would break any pipeline path that deletes a bankruptcy.

| Constraint | Child table.column | Live (drifted) | Declaring migration intends |
|---|---|---|---|
| `creditors_source_bankruptcy_id_fkey` | `creditors.source_bankruptcy_id` | `NO ACTION` | `SET NULL` (`20260529145000`) |
| `bankruptcy_case_status_bankruptcy_id_fkey` | `bankruptcy_case_status.bankruptcy_id` | `NO ACTION` | `CASCADE` (`20260524110000`) |
| `docket_entries_bankruptcy_id_fkey` | `docket_entries.bankruptcy_id` | `NO ACTION` | `CASCADE` (`20260524110000`) |

All other `bankruptcies` FKs match intent (verified via `pg_constraint.confdeltype` 2026-06-01): `bankruptcy_creditors`, `creditor_matrix_extractions`, `document_parse_results`, `form201_extractions`, `schedule_f_queue` are `CASCADE`; `documents`, `manual_review_queue`, `pipeline_executions` are `SET NULL`; `bankruptcy_rss_events`, `processing_jobs` are `NO ACTION` (as their files declare).

**Fix:** migration `20260603130003_fix_bankruptcy_fk_on_delete_drift.sql` drops and re-adds the three drifted constraints with the intended `ON DELETE`. Idempotent (drop-if-exists + add). Applied to live via MCP `apply_migration` on 2026-06-01 (the `Deploy Supabase migrations` GH workflow's deploy job is intentionally disabled — `if: false`, KD-74 / #57 — so migrations are applied via MCP/CLI by design, not CI; the job was also never wired with the `SUPABASE_DB_PASSWORD`/`SUPABASE_PROJECT_REF` secrets it would need).
