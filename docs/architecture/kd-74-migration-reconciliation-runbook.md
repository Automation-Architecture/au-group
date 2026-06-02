# KD-74 — Supabase Migration Reconciliation Runbook (baseline squash)

**Status:** ✅ EXECUTED 2026-06-02. Baseline `20260602080219_baseline_live_public_schema.sql` captured + replay-validated (zero real drift; `db push --dry-run` = no-op). DB password was reset via Management API (stored in 1Password, AU Group vault). Remaining open item: **Step 5 deploy-mechanism decision** (see below) — the `deploy-supabase.yml` deploy job is still `if: false` pending that call. The steps below are retained as the executed procedure / re-run reference.
**Project:** `umivttszdnsrosbqryia` (AU Group)
**Approach:** Baseline squash (chosen over incremental reconcile).
**Companion:** [`supabase-live-schema-state.md`](./supabase-live-schema-state.md) (the divergence map), [`../ci/deploy-workflow-investigation-2026-06-01.md`](../ci/deploy-workflow-investigation-2026-06-01.md) (why `db push` is disabled).

---

## Why baseline squash (not incremental)

The repo migration history and the live DB have **diverged irreconcilably at the version level**:

- MCP `apply_migration` stamps its **own application-time version**, not the repo filename's. Example: the FK-fix file `20260603130003_fix_bankruptcy_fk_on_delete_drift.sql` is registered on live as version **`20260601145649`** with `name = "20260603130003_fix_bankruptcy_fk_on_delete_drift"`.
- **~16 migration names are double-registered** under two timestamps each (e.g. `kd22_contact_tiers_and_contacts` at both `20260528051036` and `20260528133812`; `creditors_normalized_name` at `20260529160500` and `20260529175000`).
- A phantom entry (`20260530120000`) is registered but its SQL never ran.
- A fresh replay of the repo migrations does **not** reproduce live (KD-71 `au_group_list_company_creditors` body, `processing_job_status` enum, extra `processing_jobs` columns `worker_name`/`job_payload`, historical FK `ON DELETE` drift).

Version-by-version reconciliation against this is a quagmire. A squash makes the repo a **faithful mirror of live in one move** and lets CI `migrate-reset` finally mean something.

**Safety note:** This procedure only rewrites *migration files* and the `supabase_migrations.schema_migrations` *metadata* table. It does **not** touch live application data or live schema objects. Live is the source of truth and is read, not modified.

---

## Pre-flight (must pass before touching anything)

1. **Confirm nothing uses a direct Postgres / pooler connection** (only then is the password reset in Step 1 safe). Services use the service-role key over PostgREST (`SUPABASE_URL`), not direct PG. Check **both** consumers:
   - **Railway** — all 39 vars on service `au-group` (project `au-group-be`), key names only:
     ```bash
     railway variables --json --service au-group | python3 -c "import sys,json;[print(k) for k in json.load(sys.stdin)]" \
       | grep -iE 'DB_URL|DATABASE|POSTGRES|PG_|POOLER|DSN|CONN' || echo 'OK: no direct-PG var on Railway'
     ```
   - **n8n (still live — parallel-run pending decommission).** The n8n **Postgres node** connects with the DB password, *not* the service-role REST key. Check the AU Group n8n workflows/credentials for any Postgres credential pointing at `umivttszdnsrosbqryia` / `db.umivttszdnsrosbqryia.supabase.co` (n8n UI → Credentials, or `/n8n-debug`). **If one exists, the password reset will break the live pipeline** — rotate that n8n credential in the same maintenance window.

   If any direct-PG consumer exists (Railway or n8n), STOP and rotate it there in the same window, or do the reset during a planned n8n-paused window.
2. **Take a fresh backup / PITR checkpoint** of the live project (Supabase dashboard → Database → Backups) before any `migration repair`.
3. Work on a topic branch; keep the 63 archived files until validation passes (Step 6).

---

## Step 1 — Obtain the DB password (reset; pre-authorized)

Resetting is pre-authorized (KD-74) and low-risk given pre-flight #1.

```bash
# Supabase personal access token (verify this item is a PAT with AU Group org access first)
export SUPABASE_ACCESS_TOKEN="$(op item get otxb7wvcugobkkkafvknvvj6py --field credential --reveal)"
```

Reset the database password **via the Supabase dashboard** (Project Settings → Database → *Reset database password*) — primary method, least error-prone — **or** the Management API (confirm the current endpoint in the Management API docs before running; do not assume a path). Capture the new password into a shell var without echoing it, e.g. read it from the dashboard into:

```bash
read -rs SUPABASE_DB_PASSWORD; export SUPABASE_DB_PASSWORD   # paste, no echo
```

**Persist the new password** into 1Password (AU Group vault `xgtzybwg4orw274xuhyy27vyae`) as a new item or a field on the existing `AU Group — Document Parser / Pipeline` item — value resolved at runtime, never written to repo/doc/log:
```bash
op item edit pai2uzmigqhftt3aqibmsxiyfu "SUPABASE_DB_PASSWORD[password]=$SUPABASE_DB_PASSWORD"
```

---

## Step 2 — Capture the live schema as the baseline (`supabase db pull`)

> **Use `supabase db pull`, NOT `supabase migration squash`.** `migration squash` produces "a schema-only dump of the local database **after applying existing migration files**" — i.e. it bakes in the *repo's drift* (the inferior KD-71 `au_group_list_company_creditors`, etc.), the opposite of what we want. `db pull` dumps the **remote (live)** schema and updates the remote migration history in one step.

```bash
supabase login --token "$SUPABASE_ACCESS_TOKEN"
supabase link --project-ref umivttszdnsrosbqryia -p "$SUPABASE_DB_PASSWORD"

# Archive the 63 drifted files OUT of the scanned migrations dir first (git history retains them):
mkdir -p supabase/migrations_archive_pre_baseline
git mv supabase/migrations/*.sql supabase/migrations_archive_pre_baseline/

# Pull the live schema as the single baseline migration. Prompts: "Update remote migration
# history table? [Y/n]" → Y  (this performs the Step 3 repair automatically, marking the new
# baseline version => applied on remote). Writes supabase/migrations/<ts>_remote_schema.sql.
supabase db pull --schema public
# Optionally rename the generated file to <ts>_baseline_live_public_schema.sql for clarity.
```

**The pulled file is pg_dump output and will likely need light surgery to replay cleanly** — this is expected, and Step 4 (`db reset --local`) is where you find out. Common fixes:
- Strip/adjust ownership + `GRANT ... TO supabase_admin` / `ALTER ... OWNER` noise that doesn't exist on a fresh local stack.
- Ensure `create extension` lines for every extension used (`pg_trgm`, `pgcrypto`, etc.) — in the right schema (`extensions`).
- Confirm it contains all `public` objects: tables, the `processing_job_status` + `au_group_job_type` enums, every `au_group_*` / `sys0*` function, indexes (incl. the partial UNIQUE singleton indexes), **RLS policies**, **grants** (the service-role-only ACL on `au_group_*` RPCs), sequences, comments, and FK `ON DELETE` rules (must show `SET NULL`/`CASCADE` per §7 of the divergence doc, not `NO ACTION`).
- If grants/roles are missing, supplement with `supabase db dump --linked --role-only` output or append the ACL-reapply logic.

---

## Step 3 — Verify the remote migration history

`db pull` already offered to update the remote history (answer **Y** above), marking the new baseline `=> applied`. Verify, and decide what to do with the stale rows:

```bash
supabase migration list   # baseline must show applied on BOTH local + remote
```
- The ~98 pre-existing remote versions remain in `schema_migrations` and will show as remote-only in `migration list`. Review them there; optionally `supabase migration repair --status reverted <version>` each for a clean list. Do not over-promise `db push` behavior toward them — confirm with a `--dry-run` push (Step 4) that no unwanted apply/revert is attempted.

---

## Step 4 — Validate (the KD-74 acceptance bar)

```bash
supabase db reset --local                                 # replay baseline on a fresh local PG — must succeed
supabase db diff --linked --schema public                 # MUST report NO differences (zero drift) ← the key gate
supabase db push --linked --dry-run                        # MUST be a no-op (no migrations to apply against prod)
```

Then run the repo's existing schema verifications locally against the reset DB:
```bash
psql "$LOCAL_DB_URL" -f scripts/supabase/verify-rpc-acl.sql
bash scripts/supabase/verify-supabase-rls.sh
psql "$LOCAL_DB_URL" -f scripts/supabase/smoke_merge_creditor_matrix_dedup_audit.sql
```
Zero `db diff` output is the success signal: the repo now reproduces live exactly.

---

## Step 5 — Decide the go-forward deploy mechanism

Now that the repo is a faithful mirror, pick ONE (record the choice in `environments.md`):

- **(A) Re-enable `db push` as the single deploy path** — remove `if: false` from `deploy-supabase.yml`, add the `SUPABASE_ACCESS_TOKEN` / `SUPABASE_PROJECT_REF` / `SUPABASE_DB_PASSWORD` repo/env secrets, and **add a CI drift-guard** (`supabase db diff` fails the build if repo ≠ prod). Strongest guarantee against re-drift, but requires discipline that *all* schema changes go through migration files (no ad-hoc MCP `execute_sql` DDL).
- **(B) Keep MCP `apply_migration` as the canonical mechanism** (what the team actually uses) and leave the `db push` job disabled, BUT add the same CI drift-guard so re-drift is caught early. Lower process change; relies on the drift-guard to enforce parity.

**Recommended: (A)** — a single, CI-enforced path is what makes the reconciliation durable. The drift-guard is mandatory either way; without it the repo will silently re-drift the next time someone runs an MCP `execute_sql` DDL.

---

## Step 6 — Cleanup & docs

- Delete `supabase/migrations_archive_pre_baseline/` once `db diff` is clean and CI is green (git history retains the files). Keep until then.
- Rewrite [`supabase-live-schema-state.md`](./supabase-live-schema-state.md): the divergence is resolved → it becomes "schema baselined as of `<TS>`; repo is now source of truth; see this runbook for how."
- Update `docs/ci/environments.md` + `docs/ci/rollback.md` + `docs/ci/requirements-traceability.md` to the chosen deploy mechanism (Step 5).
- Update [`../ci/deploy-workflow-investigation-2026-06-01.md`](../ci/deploy-workflow-investigation-2026-06-01.md) "Actions taken" with the reconciliation outcome.
- Close KD-74 against the acceptance criteria below.

---

## KD-74 acceptance criteria → where satisfied

| AC | Satisfied by |
|---|---|
| Canonical baseline captured into repo | Step 2 (`${TS}_baseline_live_public_schema.sql`) |
| `db reset --local` + diff vs live = zero drift | Step 4 (`supabase db diff` clean) |
| 10 stale repo-only migrations removed; KD-71 regressor no longer applies | Step 2 (all 63 archived; baseline carries live's correct `au_group_list_company_creditors`) |
| Single source-of-truth deploy mechanism documented | Step 5 + Step 6 |
| `deploy-supabase.yml` deploy job re-enabled or intentionally removed | Step 5 |

---

## Rollback / abort

At any point before Step 6 cleanup:
- **Files:** `git checkout .` / delete the branch — restores the 63 originals from `migrations_archive_pre_baseline/` (or git).
- **Remote history:** `migration repair` edits only `schema_migrations` metadata. If a repair was wrong, re-run `repair` with the correct status. Live schema/data are never touched by this procedure, so there is nothing to restore on the data side.
- If `db diff` (Step 4) is **not** clean, do not proceed to Step 5/6 — investigate the delta (usually a missing extension, grant, or RLS policy the dump omitted) and re-dump.
