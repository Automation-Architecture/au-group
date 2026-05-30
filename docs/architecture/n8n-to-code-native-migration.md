# AU Group — n8n to Code-Native Pipeline Migration

**Prepared:** 2026-05-30  
**Author:** CTO / Technical Architect  
**PRD:** [docs/project/prd.md](../project/prd.md) (v3.0, MVP scope banner governs)  
**Brief:** [docs/project/project-brief.md](../project/project-brief.md) (v2.0)  
**Salesforce audit:** [docs/project/salesforce-audit.md](../project/salesforce-audit.md)  
**ADR:** [adr-001-rss-vs-pacer-intake.md](./adr-001-rss-vs-pacer-intake.md)  
**Status:** Draft — engineering review required

---

## Background and decision

The 26 AU Group n8n workflows share the single `automationarchitecture.app.n8n.cloud` instance with ~120 other client workflows.  The platform has hit its execution quota (SYS-05/SYS-10 fail: "Execution limit reached"), `$env` access is blocked in Code nodes (SYS-01B), and logic failures are indistinguishable from platform failures in the cloud UI.

**The selected path:** replace all MVP-relevant n8n workflows with version-controlled Python in/alongside the existing `services/document-parser/` FastAPI service on Railway, orchestrated by Railway cron and the Postgres `processing_jobs` queue already in Supabase.  Eliminate the n8n Cloud dependency for this client entirely.  Phase-2+ workflows (SYS-06/07/08/10) are designed but deprioritised.

---

## 1. Executive summary

- **Stack:** FastAPI (Python 3.11+) on Railway + Supabase Postgres + S3 for PDFs.  No new services.  Redis/Celery are already gone from `requirements.txt`; the Postgres queue replaced them.
- **Orchestration:** Railway cron services invoke standalone Python entry-points that drain the `processing_jobs` queue; each cron service runs-to-exit (≥5 min granularity, UTC).  Daily report delivery is a separate, simpler cron service.  No in-process APScheduler (would die on Railway redeploy).
- **Critical constraint — two stages are access-blocked:** ZoomInfo enrichment (SYS-03) and Salesforce push (SYS-04) build behind their respective credential/access blockers (KD-53).  Intake, parse, and daily-report delivery are unblocked today.
- **Daily report interim contract:** the existing `au_group_daily_creditor_report_rows` RPC covers 5 of 7 PRD FR-5.7 columns now (Creditor, City, State, Claim, ZoomInfo URL via stored `zoominfo_company_id`).  The two blocked columns — **Tier** (depends on ZoomInfo company firmographics) and the **FR-5.5 Salesforce-recency Status** ("New Salesforce account" / "Existing activity in Salesforce") — cannot be computed until those stages run.  An interim Status column reports pipeline progress ("New" / "Pending Enrichment" / "ZoomInfo Enriched" / "Salesforce Synced") so the report delivers useful signal while blocked.  Full FR-5.7 contract delivers when ZoomInfo + SF blockers clear.
- **Target delivery:** intake + parse + interim daily report in 1–2 engineer-weeks (unblocked); enrich + SF push behind access blockers; decommission n8n after 5-business-day parallel-run confirming output parity.

---

## 2. Stack reconciliation — EC2/Secrets Manager vs. Railway

`docs/architecture/final-tech-stack.md` describes the original AWS stack (EC2, RDS, ElastiCache, Secrets Manager).  That stack was never deployed.  **The live deployed stack is:**

| Component | Original spec | Deployed reality | Action |
|---|---|---|---|
| Compute | AWS EC2 t3.medium | Railway (FastAPI service, Nixpacks) | Keep Railway |
| Database | AWS RDS PostgreSQL | Supabase Postgres | Keep Supabase |
| Queue/broker | Redis + Celery | Postgres `processing_jobs` + RPC acquire | Keep; Redis/Celery not in `requirements.txt` |
| Object storage | AWS S3 | AWS S3 (`boto3` in requirements; `S3_BUCKET`/`AWS_*` env vars live) | Keep S3 for court PDFs |
| Secrets | AWS Secrets Manager | Railway env vars | Keep Railway env vars |
| Monitoring | CloudWatch + Sentry | Structured JSON logs (Railway log drain) | Extend with Slack error alerts (replacing SYS-99) |

**Do not** reintroduce Secrets Manager, EC2, ElastiCache, or Celery.  S3 stays.

Secrets handling: all credentials live as Railway environment variables.  Names follow the existing pattern: `PACER_USERNAME`, `PACER_PASSWORD`, `ZOOMINFO_API_KEY`, `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`, `SALESFORCE_REFRESH_TOKEN`, `SALESFORCE_INSTANCE_URL`, `SLACK_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

Railway `railway.toml` gotcha (per CLAUDE.md): `startCommand` is not bash-parsed; use `$PORT` not `${PORT:-8001}`; `rootDirectory` + GitHub source connection must both be set or toml is silently ignored.

---

## 3. Target architecture

### 3.1 Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Railway                                                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  document-parser  (existing FastAPI service; extended)       │  │
│  │  ├─ /api/v1/parse/document  (OCR + extract — unchanged)     │  │
│  │  └─ /health, /health/ready  (unchanged)                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │  intake-cron    │  │  pipeline-cron  │  │  report-cron     │   │
│  │  (Railway cron) │  │  (Railway cron) │  │  (Railway cron)  │   │
│  │  0 9 * * 1-5   │  │  */30 * * * *  │  │  0 13 * * 1-5   │   │
│  │  (daily, UTC)   │  │  (drain queue) │  │  (8AM ET=13UTC) │   │
│  └────────┬────────┘  └────────┬────────┘  └────────┬─────────┘   │
└───────────┼────────────────────┼────────────────────┼─────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌───────────────────────────────────────────────────────────────────┐
│  Supabase Postgres                                                │
│  ┌──────────────┐  ┌─────────────────────┐  ┌─────────────────┐ │
│  │ bankruptcies │  │  processing_jobs    │  │    creditors    │ │
│  │ creditors    │──│  (job queue)        │  │  zoom_info_     │ │
│  │ bankruptcy_  │  │  acquire_RPC        │  │  contacts       │ │
│  │ creditors    │  │  fail_stale_RPC     │  │  salesforce_    │ │
│  │ schedule_f_  │  │  singleton indexes  │  │  accounts       │ │
│  │ queue        │  └─────────────────────┘  └─────────────────┘ │
│  └──────────────┘                                                 │
│  daily_creditor_report_rows() RPC — daily report query           │
└───────────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
    ┌───────────┐         ┌─────────────┐      ┌──────────┐
    │   PACER   │         │  ZoomInfo   │      │Salesforce│
    │   API     │         │  API        │      │  API     │
    │(unblocked)│         │ (blocked:   │      │(blocked: │
    └───────────┘         │  KD-53)    │      │ VPN/IP)  │
                          └─────────────┘      └──────────┘
            │
            ▼
        ┌───────┐
        │  S3   │  (court PDFs — existing)
        └───────┘
            │
            ▼
        ┌─────────────────────────────┐
        │  document-parser /parse     │  (existing FastAPI endpoint)
        │  OCR + Form 201/204 extract │
        └─────────────────────────────┘
            │
            ▼
        ┌────────┐
        │ Slack  │  #au-group-sprint — daily report + error alerts
        └────────┘
```

### 3.2 Three-tier orchestration model

| Tier | Mechanism | When to use | Examples |
|---|---|---|---|
| **Cron-triggered pollers** | Railway cron service, runs-to-exit | Kick off intake; trigger daily report delivery | `intake-cron`, `report-cron` |
| **Queue-draining worker** | Railway cron service (frequent interval) that calls `au_group_claim_job` (new — WP-00), does work, then exits | Per-bankruptcy stage work that must survive retries | `pipeline-worker` draining `document_parse`, `zoom_info_enrich`, `salesforce_push` |
| **pg_cron / SQL** | Supabase pg_cron or manual call | Pure-SQL hygiene that requires no Python | `au_group_fail_stale_processing_jobs` — already exists as an RPC |

**Why not in-process APScheduler:** Railway restarts the container on redeploy; an in-process scheduler loses its state and does not fire while down.  Cron services are separate deployments that fire on schedule regardless of the API service state.

**Railway cron verification (from docs.railway.com/cron-jobs):**  
- Starts the full container, runs `startCommand`, expects process exit when done.  
- If the previous execution is still `Active`, the new run is **skipped** (not queued).  
- Minimum interval: 5 minutes.  
- Schedule is UTC.  
- 8:00 AM ET = `0 13 * * 1-5` (ET is UTC-5 standard / UTC-4 daylight; use `0 12 * * 1-5` during EDT; see open decision OD-1).

### 3.3 Service layout

Three Railway services total (one existing, two new):

| Service | Type | `rootDirectory` | Entry-point | Notes |
|---|---|---|---|---|
| `document-parser` | Web (existing) | `services/document-parser` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | Unchanged; OCR + parse API. Uses `$PORT` (Railway env) |
| `pipeline-worker` | Cron (new) | `services/document-parser` | `python -m pipeline.worker` | Drains `processing_jobs` queue; runs every 30 min. **Does not bind a port.** No `$PORT` in startCommand. |
| `daily-report` | Cron (new) | `services/document-parser` | `python -m pipeline.report` | Delivers Slack report; runs once per weekday at 13:00 UTC. **Does not bind a port.** |

Both new cron services share the same repo directory and Railway env vars as `document-parser`.  They are separate Railway services so their cron schedules are independent and each exits when done.

A fourth service `intake-cron` (`python -m pipeline.intake`) is also needed for daily PACER polling; it can be added once PACER credentials are integrated.  For the unblocked build slice it is not required (RSS/CourtListener intake already runs through the existing n8n SYS-01 path during parallel run).

---

## 4. Stage decomposition — n8n → code mapping

Each stage is a Python module under `services/document-parser/pipeline/`.

### 4.1 Stage overview

| n8n workflow(s) | Code module | Job type | Unblocked? |
|---|---|---|---|
| SYS-01 RSS Intelligence + SYS-01B PACER Nightly Poll | `pipeline/intake.py` | `pacer_poll` (existing enum) | ✅ Yes (PACER creds exist) |
| SYS-02 Bankruptcy Intelligence / Document Parse | `pipeline/parse.py` | `document_parse`, `document_intelligence` (existing enums) | ✅ Yes (calls existing document-parser endpoint) |
| SYS-03 Creditor Enrichment | `pipeline/enrich.py` | `zoom_info_enrich` (existing enum) | ❌ Blocked — ZoomInfo prod key (KD-53) |
| SYS-04 Salesforce Push | `pipeline/salesforce.py` | `salesforce_push` (existing enum) | ❌ Blocked — SF VPN/IP lockout |
| SYS-09 Daily Summary / report | `pipeline/report.py` | none (cron-triggered, off-queue) | ✅ Partially (4/7 columns fully populated; Tier + recency Status blocked) |
| SYS-99 Error Logger | `pipeline/alerts.py` (utility) | none | ✅ Yes |
| SYS-00 Get Docket, Resolve Territory Rep, Slack Notifier | absorbed into `intake.py`, `alerts.py` | — | ✅ Yes |
| SYS-06 Schedule F Detector, SYS-07 Processor, SYS-08 Historical, SYS-05 Outreach, SYS-10 OCR Review | `pipeline/schedule_f.py` (stub), `pipeline/outreach.py` (stub) | new job types needed | Phase 2+ |

### 4.2 Stage contracts

#### Stage 0: Intake (`pipeline/intake.py`)

Replaces: SYS-01 RSS Intelligence + SYS-01B PACER Nightly Poll + SYS-00 utility sub-workflows.

**Trigger:** `intake-cron` Railway cron service (`0 9 * * 1-5` UTC, i.e., ~4 AM ET).

**Inputs:**  
- `PACER_USERNAME`, `PACER_PASSWORD` from Railway env  
- `AU_GROUP_TARGET_STATES` — comma-separated state abbreviations (or read from `au_group_target_states` Supabase table per migration `20260528100000_au_group_target_states.sql`)  

**Logic:**
1. Query PACER for new Chapter 11 filings since last successful run (use `bankruptcies.created_at` max or a `last_run_at` config key in `au_group_runtime_config`).  
2. For each new case: download Form 201 (voluntary petition) + Form 204 (top-20 creditor list); store both PDFs in S3 under `raw-documents/{case_number}/`.  
3. Call `au_group_upsert_bankruptcy` RPC (existing, migration `20260515150100`) to insert/update the `bankruptcies` row.  
4. Call `au_group_enqueue_job(bankruptcy_id, 'document_parse')` (new RPC from WP-00) — inserts a `pending` job; no-ops if `pending` or `running` already exists.  
5. Insert a `pacer_poll` `processing_job` row (status `completed` or `failed`) per ADR-001.  
6. On any error: call `pipeline/alerts.py` → Slack.  

**Outputs:**
- `bankruptcies` rows upserted  
- `processing_jobs` rows with `job_type='document_parse'`, `status='pending'`  
- PDFs in S3  

**Idempotency:** `bankruptcies.case_number` is UNIQUE; `au_group_upsert_bankruptcy` is idempotent.  `au_group_enqueue_job` is a no-op if a `pending` or `running` job already exists for the same `(bankruptcy_id, job_type)` — uses the existing singleton partial index to enforce this.

#### Stage 1: Parse (`pipeline/parse.py`)

Replaces: SYS-02 Bankruptcy Intelligence / Document Parse.  
SYS-02 owned both `document_intelligence` and `document_parse` job types.  In code-native, `document_parse` is the primary queue type for the parse worker; `document_intelligence` is the legacy n8n-orchestration type (still accepted by the acquire RPC, but new enqueues use `document_parse`).

**Trigger:** `pipeline-worker` cron service drains the queue every 30 min.

**Queue claim:** call `au_group_claim_job('document_parse')` (new RPC from WP-00) — `UPDATE processing_jobs SET status='running', started_at=now() WHERE id = (SELECT id FROM processing_jobs WHERE status='pending' AND job_type=$1 ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *`.  Returns the claimed job or NULL if nothing pending.  The singleton partial index ensures at most one `running` job per `(bankruptcy_id, job_type)` — if the UPDATE would violate it (because n8n is holding a running job for this bankruptcy), the `unique_violation` is caught and the row is skipped (parallel-run mutual exclusion preserved).

**Logic:**
1. Loop: claim one `document_parse` job at a time until none remain.  
2. Load `bankruptcy_id`, look up S3 keys for Form 201 + Form 204 PDFs.  
3. POST `{DOCUMENT_PARSER_URL}/api/v1/parse/document` with `bankruptcy_id`, the Form 204 S3 key, and **`async_mode: true`** in the body (`X-API-Key: {API_KEY}`).  Background processing requires **both** `ASYNC_PARSE_ENABLED=true` (service env) **and** `async_mode: true` (request body — see `ParseDocumentRequest.async_mode` and the router check); otherwise the call runs synchronously and returns no `document_id` to poll.  Then poll `GET /api/v1/jobs/{document_id}` until `completed` or `failed` (existing async pattern — see README).  
4. The document-parser service writes creditor rows to Supabase and returns structured output; no direct DB write from this stage.  
5. Mark `document_parse` job `completed`.  
6. Call `au_group_enqueue_job(bankruptcy_id, 'zoom_info_enrich')` (new RPC) to queue the next stage.  

**Outputs:**
- `creditors` + `bankruptcy_creditors` rows (written by document-parser service, not by this stage directly)  
- `processing_jobs` row `document_parse` → `completed`  
- `processing_jobs` row `zoom_info_enrich` → `pending`  

**Idempotency:** document-parser's merge RPC (`au_group_upsert_document_parse_result`, migration `20260523140000`) is idempotent on `(bankruptcy_id, creditor_name)`.

#### Stage 2: ZoomInfo Enrichment (`pipeline/enrich.py`)

Replaces: SYS-03 Creditor Enrichment.

**Status: BLOCKED — ZoomInfo production API key (KD-53).** Build this module; guard with an env-var check at entry (`if not settings.zoominfo_api_key: sys.exit(0)`).

**Queue entry claimed:** `job_type='zoom_info_enrich'`, `status='running'`.

**Inputs:** creditors for the bankruptcy where `is_company=true`, not junk, not yet enriched (`zoominfo_company_id IS NULL`).

**Logic per creditor:**
1. POST ZoomInfo company search: `name` + `state` (from address parse).  
2. Apply name normalization (FR-4.5): use ZoomInfo canonical name if match confidence ≥ threshold.  
3. Classify tier (FR-4.2):  
   - Enterprise: revenue ≥ $1B OR employees ≥ 5,000  
   - Mid-Market: revenue $100M–$1B OR employees 500–5,000  
   - SMB: below thresholds; inclusive boundary ($100M → Mid-Market)  
4. Store `zoominfo_company_id` on `creditors` via `au_group_set_creditor_zoominfo_company_id` RPC (migration `20260529160000`).  
5. Store tier and firmographics in `zoom_info_contacts` (repurpose as company-level record in MVP; contact fields NULL until Phase 2).  
6. Persist `normalized_name` (canonical ZoomInfo company name) to `creditors.normalized_name` (column exists per migration `20260529160500`).  

**New data model fields required:**
- `creditors.company_tier` — `VARCHAR(20)` CHECK IN ('Enterprise', 'Mid-Market', 'SMB'); migration needed (see §5).  
- `zoom_info_contacts.company_tier` — same; or derive from creditors at report time (see OD-2).  

**Rate limiting:** batch in groups of 10 with `tenacity` exponential backoff on HTTP 429 (3 attempts, 15 s base).  ZoomInfo rate-limit behavior: **[OPEN DECISION OD-3]** — verify API tier limit with client before coding the batch size.

**Outputs:**
- `creditors.zoominfo_company_id` set  
- `creditors.normalized_name` set  
- `creditors.company_tier` set (new column)  
- `zoom_info_contacts` row (company-level firmographics)  
- `processing_jobs` `zoom_info_enrich` → `completed`  
- `processing_jobs` `salesforce_push` → `pending` (via `au_group_enqueue_job`)  

#### Stage 3: Salesforce Push (`pipeline/salesforce.py`)

Replaces: SYS-04 Salesforce Push.

**Status: BLOCKED — Salesforce login-IP/VPN lockout.** Build this module; guard with env-var check.

**Queue entry claimed:** `job_type='salesforce_push'`, `status='running'`.

**Library:** `simple-salesforce` (already in `requirements.txt` of original spec; add to `document-parser/requirements.txt`).

**Logic per creditor (company, enriched):**
1. SF account lookup: search by `Name` + `BillingState`.  Fuzzy-match threshold: flag to manual review when no clean match (EC-3.1 in PRD).  
2. **Create or update** Account with:  
   - Standard fields: `Name` (normalized company name), `BillingStreet/City/State/PostalCode` (from creditor address), `Industry`, `NumberOfEmployees`, `AnnualRevenue` (from ZoomInfo firmographics)  
   - Custom fields: `Company_Tier__c` (Enterprise/Mid-Market/SMB), `ZoomInfo_URL__c` (from `au_group_zoominfo_company_url(zoominfo_company_id)`), email merge variables per FR-5.6b (confirmed field list — **[OPEN DECISION OD-4]**)  
3. Create `Bankruptcy_Event__c` child record: `Debtor_Name__c`, `Filing_Date__c`, `Claim_Amount__c`, `Case_Number__c`, `Court_District__c`, `Chapter_Type__c`, `PACER_URL__c`.  
4. **Compute recent-activity flag (FR-5.5):** query `Opportunity` (any non-Closed-Lost stage) OR `Task`/`Event` with `CreatedDate >= LAST_N_DAYS:90` for this account.  Result: `"New Salesforce account"` or `"Existing activity in Salesforce"`.  **[OPEN DECISION OD-5]** — exact Opportunity stage set + objects to query (see salesforce-audit.md §3.2).  
5. **Persist the recency flag** to `salesforce_accounts.sf_recency_status VARCHAR(50)` (new column — see §5) — this is how the daily report reads the correct FR-5.5 Status without needing a live SF call at report time.  
6. Call `au_group_upsert_salesforce_account(creditor_id, sf_account_id)` RPC.  
7. Mark `salesforce_push` job `completed`.  

**Idempotency:** `simple-salesforce` upsert on `CaseNumber` for Bankruptcy_Event__c.  Duplicate accounts: zero (FR-5.1) — use `upsert` with an `ExternalId` field (`Pipeline_Creditor_ID__c = creditor_id`) **[OPEN DECISION OD-6]** — confirm with SF audit whether external-ID field exists.

#### Stage 4: Daily Report (`pipeline/report.py`)

Replaces: SYS-09 Daily Summary.

**Trigger:** `daily-report` Railway cron service (`0 13 * * 1-5` UTC = 8 AM ET standard / 9 AM EDT — see OD-1).

**Inputs:** `SLACK_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` from Railway env.

**⚠️ RPC gap — the existing `au_group_daily_creditor_report_rows` cannot be used for debtor-grouped output without a fix.**  
The current RPC (migration `20260529180000`) returns flat per-creditor rows with no `bankruptcy_id` or `debtor_name`.  The lateral join inside the RPC picks only the *latest* bankruptcy's state per creditor, collapsing a creditor that appears in two debtors to a single row.  The PRD requires grouping by bankrupt company (debtor).

**Solution (part of WP-03):** create a new Supabase function `au_group_daily_creditor_report_grouped(p_since timestamptz)` that returns rows with `debtor_name`, `case_number`, `filing_date` included per-row (not just the latest-bankruptcy lateral), so Python can group without losing multi-debtor creditors.  The existing `au_group_daily_creditor_report_rows` function is unchanged (backward-compatible); the new function is additive.

**New function contract:**
```sql
create function public.au_group_daily_creditor_report_grouped(
  p_since timestamptz default null
)
returns jsonb  -- {since, debtor_count, creditor_count, rows: [{debtor_name, case_number, filing_date, creditor, city, state, claim, status, zoominfo_url}, ...]}
```
Each row is one (creditor × bankruptcy) pair — a creditor appearing in two debtors produces two rows with different `debtor_name`.

**Logic in `report.py`:**
1. Call `au_group_daily_creditor_report_grouped()`.
2. Group rows by `debtor_name`; sort debtors by `filing_date DESC`; within each debtor sort by `claim` (numeric parse) DESC.
3. Format Slack message (see §4.3).
4. POST to `SLACK_WEBHOOK_URL`.
5. Exit 0 on success; exit 1 on failure (`alerts.py` fires on exception).

**Note on the RPC's `status` column vs. PRD FR-5.5:**  
The `status` field from the new function also calls `au_group_creditor_pipeline_status`, which returns pipeline progress ("New" / "Pending Enrichment" / "ZoomInfo Enriched" / "Salesforce Synced") — not FR-5.5's recency flag.  This is correct interim behavior while SF is blocked.  When WP-09 is active, the Python report module replaces the pipeline-status string with `salesforce_accounts.sf_recency_status` for rows that have a `salesforce_accounts` record.  **RPC update required (part of the grouped-report migration):** `au_group_creditor_pipeline_status` currently treats only `queued`/`running`/`retrying` enrichment jobs as pending — it must also count the new queue's **`pending`** rows, or pending enrichments will mis-render as "New" instead of "Pending Enrichment".

**The Tier column:** the new grouped function should include `creditors.company_tier` (NULL while ZoomInfo is blocked); `report.py` renders NULL as `—`.

#### Stage 5: Error alerting (`pipeline/alerts.py`)

Replaces: SYS-99 Error Logger.

Simple utility: `send_error_alert(stage: str, error: str, bankruptcy_id: Optional[str])` → POST to `SLACK_WEBHOOK_URL` with a formatted error block.  Called by all other stages on unhandled exceptions.

---

### 4.3 Slack report format

PRD FR-5.7 columns: Creditor · City · State · Claim ($) · Tier · Status · ZoomInfo URL.

Interim format (until ZoomInfo + SF active): replace Tier with `—`; replace Status with pipeline-progress string.

```
*Daily Creditor Report — Thu 29 May 2026*
Processed 14 company creditors from 2 bankruptcies.

---

*XYZ Wholesaler, Inc. (Bankrupt Company)* | Case 26-10042 · D.Tex · Filed 2026-05-28

| Creditor | City | State | Claim | Tier | Status | ZoomInfo |
|---|---|---|---|---|---|---|
| Acme Supply Co | Dallas | TX | $412,000.00 | Mid-Market | Existing activity in Salesforce | https://app.zoominfo.com/... |
| Harbor Logistics | Houston | TX | $88,500.00 | SMB | New Salesforce account | https://app.zoominfo.com/... |
| ... | | | | | | |

---

*Another Debtor Corp (Bankrupt Company)* | Case 26-10043 · S.D.Fla · Filed 2026-05-27
...
```

Slack has a 4,000-character limit per block.  For reports with > ~40 creditors, split into multiple Slack messages (one per debtor group) with a header message for the summary count.

---

## 5. Data model — additions and confirmations

### 5.1 Existing schema (no changes needed)

All tables from migration `20260215180000_au_group_bankruptcy_pipeline.sql` and subsequent migrations are authoritative.  Key confirmed facts:

- `processing_jobs` with `au_group_job_type` enum: `pacer_poll`, `document_parse`, `document_intelligence`, `zoom_info_enrich`, `salesforce_push` — **no new job types needed for MVP pipeline stages**.
- `au_group_acquire_processing_job(bankruptcy_id, job_type, stale_interval)` RPC with singleton partial indexes: single-running-job guarantee per `(bankruptcy_id, job_type)`.
- `au_group_fail_stale_processing_jobs(p_max_age)` RPC: run daily via pg_cron or at pipeline-worker startup.
- `creditors.zoominfo_company_id` (TEXT): exists, populated by enrich stage.
- `creditors.normalized_name` (TEXT): exists (migration `20260529175000`).
- `creditors.original_name` (TEXT): exists.
- `salesforce_accounts` table: creditor_id → salesforce_account_id mapping.
- `au_group_daily_creditor_report_rows(timestamptz)` → JSONB: most recent version is in migration `20260529180000` (canonical).
- `au_group_runtime_config` table with `au_group_get_runtime_config(key)` and helper RPCs.

### 5.2 New columns required (migrations needed)

Two new columns blocked on their respective stages:

```sql
-- Migration: 20260530XXXXXX_creditors_company_tier.sql
ALTER TABLE public.creditors
  ADD COLUMN IF NOT EXISTS company_tier VARCHAR(20)
    CHECK (company_tier IN ('Enterprise', 'Mid-Market', 'SMB'));

COMMENT ON COLUMN public.creditors.company_tier IS
  'FR-4.2 tier classification from ZoomInfo firmographics (Enterprise/Mid-Market/SMB). NULL until SYS-03 enrichment runs.';
```

```sql
-- Migration: 20260530XXXXXX_salesforce_accounts_recency_status.sql
ALTER TABLE public.salesforce_accounts
  ADD COLUMN IF NOT EXISTS sf_recency_status VARCHAR(60);

COMMENT ON COLUMN public.salesforce_accounts.sf_recency_status IS
  'FR-5.5 Salesforce-recency flag: "New Salesforce account" or "Existing activity in Salesforce". Persisted at push time so daily report does not require a live SF call.';
```

### 5.3 Salesforce schema gaps (from salesforce-audit.md §2)

Two custom fields must be created in the SF org before SYS-04 build:

| Field | Object | Type | Purpose |
|---|---|---|---|
| `Company_Tier__c` | Account | Picklist (Enterprise / Mid-Market / SMB) | FR-4.2 tier attribute |
| `ZoomInfo_URL__c` | Account | URL | FR-4.1/FR-5.7 ZoomInfo profile link |

These are additions to the existing designed schema in salesforce-audit.md §1.  See OD-4 for email merge variable field list.

### 5.4 `pipeline_executions` table

The `n8n_workflow_id` / `n8n_execution_id` columns exist to track n8n runs.  After cutover, populate `n8n_workflow_id` with a string like `"code-native/intake"` and `n8n_execution_id` with a UUID generated per Python run.  No schema change needed; no backfill of historical n8n rows.

---

## 6. Key flows

### 6.1 Daily pipeline (MVP happy path)

```
09:00 UTC  intake-cron fires (`0 9 * * 1-5`; exact time/DST handling per OD-1)
│
├─ intake.py: query PACER for prior-day CH11 filings in target states
├─ For each new case:
│   ├─ Download Form 201 + Form 204 → S3
│   ├─ upsert bankruptcies row
│   └─ au_group_enqueue_job(bankruptcy_id, 'document_parse') → inserts status='pending'
│       (no-op if pending/running already exists for this bankruptcy)
│
09:00 UTC  pipeline-worker fires (every 30 min)
│
├─ au_group_fail_stale_processing_jobs('4 hours')  ← cleanup first
│
├─ claim loop: au_group_claim_job('document_parse')
│   → UPDATE status='pending'→'running' WHERE job_type='document_parse'
│       ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED
│   → unique_violation = n8n holds this bankruptcy; skip, try next
│
├─ For each claimed document_parse job:
│   ├─ POST document-parser /parse/document (async, poll for completion)
│   ├─ Mark document_parse completed
│   └─ au_group_enqueue_job(bankruptcy_id, 'zoom_info_enrich') → pending
│
│  (until ZoomInfo unblocked: zoom_info_enrich jobs sit pending; worker exits after
│   claiming all document_parse jobs; SKIP_ENRICH=true guard skips enrich claiming)
│
│  zoom_info_enrich jobs (when unblocked):
│   ├─ Claim via au_group_claim_job('zoom_info_enrich')
│   ├─ Company match + tier classification
│   ├─ Persist zoominfo_company_id, company_tier, normalized_name
│   └─ au_group_enqueue_job(bankruptcy_id, 'salesforce_push') → pending
│
│  salesforce_push jobs (when unblocked):
│   ├─ Claim via au_group_claim_job('salesforce_push')
│   ├─ SF account match/create/update
│   ├─ Bankruptcy_Event__c create
│   ├─ Email merge variables populated
│   ├─ sf_recency_status computed + persisted
│   └─ salesforce_accounts row upserted
│
13:00 UTC  daily-report cron fires (0 13 * * 1-5)
│
├─ report.py: SELECT au_group_daily_creditor_report_grouped()  ← new grouped RPC (WP-03)
├─ Group by debtor_name in Python
├─ Format Slack blocks (grouped by debtor, sorted by filing_date DESC)
└─ POST to SLACK_WEBHOOK_URL
```

### 6.2 Retry / stale-fail path

```
pipeline-worker start:
├─ au_group_fail_stale_processing_jobs('4 hours')
│   (marks any running job stuck > 4h as failed — idempotent, run first)
│
├─ au_group_claim_job(job_type): UPDATE pending → running (FOR UPDATE SKIP LOCKED)
│   returns claimed job row or NULL (nothing pending, exit cleanly)
│
On stage exception:
├─ If retry_count < 3:
│   UPDATE SET status='pending', retry_count=retry_count+1
│   (re-queued for next worker invocation)
├─ If retry_count = 3:
│   UPDATE SET status='failed', error_message=<exception string>
└─ Call alerts.py → Slack (stage, bankruptcy_id, error, retry_count)
```

The singleton partial index (`idx_processing_jobs_one_running_*`) ensures stale-fail + re-claim is race-safe: at most one `running` job per `(bankruptcy_id, job_type)`.

### 6.3 Parallel run (n8n + code-native simultaneously)

`au_group_claim_job` does `FOR UPDATE SKIP LOCKED` on `pending` rows, then flips to `running`.  The singleton partial index blocks the flip if a `running` row already exists for the same `(bankruptcy_id, job_type)` — the worker skips that bankruptcy and tries the next one.

- If n8n holds a `running` job, the code-native worker skips that bankruptcy — no double-processing.
- If code-native claims a job first, n8n's acquire RPC returns `acquired=false` — same safety from the other direction.

**Recommended parallel-run protocol:**

1. Deploy `pipeline-worker` and `daily-report` cron services to Railway with `SKIP_ENRICH=true` and `SKIP_SF=true` env flags.
2. Run both n8n and code-native for **5 business days** on intake/parse/report only.
3. Compare daily Slack report output (creditor count, case numbers) between n8n SYS-09 output and code-native report.
4. When outputs match: disable SYS-01/SYS-02/SYS-09 in n8n (deactivate, don't delete yet).
5. When ZoomInfo and SF access land: run enrich + SF push code-native; compare SYS-03/SYS-04 n8n output.
6. After full-stack parity for 5 days: delete n8n workflows (see §8.2).

---

## 7. Module and file layout

Extend `services/document-parser/` — do not create a new top-level service directory.

```
services/document-parser/
  pipeline/                      ← NEW directory
    __init__.py
    alerts.py                    ← SYS-99 replacement (Slack error util)
    intake.py                    ← SYS-01 / SYS-01B replacement
    parse.py                     ← SYS-02 replacement (calls /parse/document)
    enrich.py                    ← SYS-03 replacement (ZoomInfo; build, guard on ZOOMINFO_API_KEY)
    salesforce.py                ← SYS-04 replacement (SF push; guard on SALESFORCE_CLIENT_ID)
    report.py                    ← SYS-09 replacement (daily Slack report)
    schedule_f.py                ← SYS-06/07 stub (Phase 2+)
    worker.py                    ← Queue drain entry-point: claimed by pipeline-worker cron
    settings.py                  ← Pydantic settings shared across pipeline modules
  app/                           ← Unchanged (FastAPI document-parser)
  tests/
    pipeline/                    ← NEW tests
      test_intake.py
      test_parse.py
      test_enrich.py
      test_salesforce.py
      test_report.py
      test_worker.py
  requirements.txt               ← Add: simple-salesforce, tenacity, python-slugify
```

### 7.1 New dependencies

Add to `services/document-parser/requirements.txt`:

```
simple-salesforce==1.12.5   # SYS-04 SF REST API client
tenacity==8.2.3             # Exponential backoff for PACER, ZoomInfo, SF API calls
```

`httpx` (already present at 0.28.1) covers PACER and ZoomInfo calls.  `boto3` (already present) covers S3.

### 7.2 `pipeline/settings.py` (Pydantic Settings extension)

The existing `app/core/config.py` has `get_settings()`.  `pipeline/settings.py` extends it with pipeline-only env vars:

```python
class PipelineSettings(BaseSettings):
    pacer_username: str = ""
    pacer_password: str = ""
    zoominfo_api_key: str = ""
    zoominfo_api_url: str = "https://api.zoominfo.com"
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_refresh_token: str = ""
    salesforce_instance_url: str = ""
    slack_webhook_url: str = ""
    daily_report_window_hours: int = 24
    stale_job_interval_hours: int = 4
    enrich_batch_size: int = 10    # ZoomInfo batch size — verify against API tier
    skip_enrich: bool = False      # Parallel-run guard
    skip_sf: bool = False          # Parallel-run guard
```

---

## 8. Migration and decommission plan

### 8.1 Build order (blocker-aware)

| Order | Work package | Blocked? | Can start |
|---|---|---|---|
| 0 | **WP-00 Enqueue RPC + claim RPC** — `pending` state + `FOR UPDATE SKIP LOCKED` dequeue | No | Immediately (blocks WP-01/05/06) |
| 1 | WP-01 Pipeline module skeleton + `worker.py` drain loop | No | After WP-00 |
| 2 | WP-02 `alerts.py` (Slack error util) | No | Immediately (parallel) |
| 3 | WP-03 `report.py` + report RPC debtor-grouping fix + Railway cron service | No | After WP-00 + WP-01 |
| 4 | WP-04 DB migrations (company_tier + sf_recency_status columns) | No | Immediately |
| 5 | WP-05 `intake.py` — PACER polling + S3 + enqueue | No (PACER creds exist) | After WP-00 |
| 6 | WP-06 `parse.py` — queue drain → document-parser endpoint | No | After WP-00 |
| 7 | WP-07 `report.py` Tier + recency rendering (render-only; no RPC change — grouped RPC already returns `company_tier`) | Partial (Tier blocked on ZoomInfo) | WP-03/04 done |
| 8 | WP-08 `enrich.py` — ZoomInfo company match + tier | ❌ KD-53 (ZoomInfo key) | When ZoomInfo unblocked |
| 9 | WP-09 `salesforce.py` — SF push + recency flag | ❌ SF VPN/IP + KD-53 | When SF + ZI unblocked |
| 10 | WP-10 Parallel-run validation + n8n decommission | No (after WP parity) | After WP-06 for report; WP-09 for full |

### 8.2 n8n decommission plan

The n8n instance is shared across all clients.  Decommission is AU Group-specific only.

**Order of deactivation (do not delete until parity confirmed):**

1. Deactivate (not delete) SYS-01, SYS-01B, SYS-02 after 5-day intake/parse parity.
2. Deactivate SYS-03, SYS-04 after 5-day enrich/SF parity.
3. Deactivate SYS-09 after daily-report parity (count, columns, timing).
4. Deactivate SYS-99, SYS-00.
5. Deactivate SYS-06 × 2, SYS-07, SYS-08 × 3, SYS-05, SYS-10 (currently inactive stubs or inactive duplicates).
6. Delete all 26 AU Group workflows from n8n Cloud after deactivation confirmed.  Archive workflow JSON to `workflows/archived/` in this repo before deletion.

**Repo cleanup after decommission:**
- Update `README.md` and `CLAUDE.md` to remove n8n from the "orchestrated by n8n" description.
- Rename `pipeline_executions.n8n_workflow_id` / `n8n_execution_id` columns via migration to `source_workflow_id` / `source_execution_id` (optional — can defer to avoid breaking any live query).
- Archive `workflows/pulled/` n8n JSONs (keep in git history; remove from default view).

---

## 9. Work packages

All WPs are assigned to BE (Operator).  Effort: S = ~half day, M = 1–2 days, L = 3–5 days.

---

### WP-00: Enqueue RPC + claim RPC (Supabase migrations) [BE]

**Description:** The existing `au_group_acquire_processing_job` RPC creates a job in `running` state and returns `acquired=false` if a running job already exists.  This works for n8n's acquire-and-execute-in-one-step model but is wrong for a producer/consumer split (intake enqueues; worker claims later).  Add two Supabase RPCs:

1. **`au_group_enqueue_job(p_bankruptcy_id, p_job_type)`** — inserts a `pending` row; no-ops (returns `enqueued=false`) if a `pending` OR `running` job already exists for that `(bankruptcy_id, job_type)`.  The existing singleton partial indexes only enforce uniqueness on `running` rows, so WP-00 **adds a new partial unique index** `... ON processing_jobs (bankruptcy_id, job_type) WHERE status='pending'`; the enqueue does a guarded insert that catches the `unique_violation` (pending dupe) and the running-singleton violation, returning `enqueued=false` in both cases.

2. **`au_group_claim_job(p_job_type)`** — claims one `pending` job atomically: `UPDATE ... SET status='running', started_at=now() WHERE id = (SELECT id FROM processing_jobs WHERE status='pending' AND job_type=$1 ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *`.  Catches `unique_violation` from the singleton partial index (another worker or n8n claimed the same bankruptcy's job in a race) and retries on the next row.  Returns the claimed job row, or NULL if nothing pending.

These two RPCs replace all uses of `au_group_acquire_processing_job` in the new pipeline modules.  The existing acquire RPC is **not modified** — n8n continues to use it unchanged during the parallel-run window.

Migration naming: `20260530XXXXXX_au_group_enqueue_and_claim_job_rpcs.sql`.

**Dependencies:** none.

**Acceptance criteria:**
- [ ] `au_group_enqueue_job(id, 'document_parse')` inserts `status='pending'` row on first call
- [ ] Second call with same args returns `{enqueued: false}` (idempotent)
- [ ] `au_group_enqueue_job` is a no-op when a `running` job already exists (n8n running)
- [ ] New partial unique index on `(bankruptcy_id, job_type) WHERE status='pending'` created (existing singleton indexes only cover `running`)
- [ ] `au_group_claim_job('document_parse')` flips one `pending` row to `running`; returns the row
- [ ] `au_group_claim_job` returns NULL when no pending jobs exist
- [ ] Two concurrent `au_group_claim_job` calls on the same job: exactly one succeeds; the other skips (race-safe via SKIP LOCKED + unique_violation catch)
- [ ] Existing `au_group_acquire_processing_job` RPC is untouched (n8n compatibility)
- [ ] Migration applies cleanly via `supabase db push`

**Estimated effort:** S

---

### WP-01: Pipeline skeleton + worker drain loop [BE]

**Description:** Create `services/document-parser/pipeline/` directory with `__init__.py`, `settings.py`, and `worker.py`.  `worker.py` is the Railway cron entry-point: on startup (a) call `au_group_fail_stale_processing_jobs`, (b) loop — claim one **`pending`** `document_parse` job at a time via `au_group_claim_job` (which atomically flips it `pending`→`running`), (c) dispatch the claimed job to the appropriate stage module, repeat until `claim` returns NULL, (d) exit 0.  Add `pipeline-worker` Railway service config (new service in the same repo/rootDirectory as `document-parser`).

**Dependencies:** WP-00.

**Acceptance criteria:**
- [ ] `python -m pipeline.worker` runs locally without error (with a mock Supabase client)
- [ ] `worker.py` calls `au_group_fail_stale_processing_jobs` before claiming jobs
- [ ] `au_group_claim_job` RPC called; NULL return (nothing pending) causes worker to exit 0 cleanly
- [ ] Railway cron service (`*/30 * * * *`) configured; `startCommand = "python -m pipeline.worker"` (no port binding; cron services do not use `$PORT`)
- [ ] `SKIP_ENRICH=true` and `SKIP_SF=true` env-var guards wired (no-op when set)
- [ ] Worker exits within 25 minutes (well under the 30-minute cron interval to avoid Railway skip)

**Estimated effort:** M

---

### WP-02: Slack error alerting utility [BE]

**Description:** Create `pipeline/alerts.py` with `send_error_alert(stage, error, bankruptcy_id=None, metadata=None)`.  Posts a Slack message to `SLACK_WEBHOOK_URL` with error details.  Called in `except` blocks of all other pipeline modules.  Replaces SYS-99.

**Dependencies:** none.

**Acceptance criteria:**
- [ ] `send_error_alert("intake", "PACER timeout", "uuid-123")` posts a formatted Slack block
- [ ] Gracefully handles `SLACK_WEBHOOK_URL` missing (logs only, does not raise)
- [ ] Unit test: mock `httpx.post`; confirm payload shape
- [ ] No secrets logged

**Estimated effort:** S

---

### WP-03: Interim daily report + grouped RPC + Railway cron service [BE]

**Description:** Two deliverables:

(a) **New Supabase migration** — `au_group_daily_creditor_report_grouped(p_since timestamptz)` — additive function alongside the existing `au_group_daily_creditor_report_rows`.  Returns per (creditor × bankruptcy) rows including `debtor_name`, `case_number`, `filing_date`, `company_tier` (NULL until WP-08).  A creditor appearing in two debtors produces two rows.  The existing `au_group_daily_creditor_report_rows` is **not modified**.

(b) **`pipeline/report.py`** — calls the new grouped function; groups in Python by `debtor_name`; posts Slack message.  Add `daily-report` Railway cron service (`0 13 * * 1-5`).

**Dependencies:** WP-00, WP-01 (settings), WP-02 (alerts).

**Acceptance criteria:**
- [ ] Migration applies cleanly; `au_group_daily_creditor_report_grouped()` returns JSONB with per-(creditor × debtor) rows including `debtor_name`, `case_number`, `filing_date`
- [ ] A creditor linked to two bankruptcies appears in both debtor groups in the Slack output
- [ ] `python -m pipeline.report` posts a correctly-formatted Slack message to `#au-group-sprint`
- [ ] Report grouped by debtor; debtors sorted by `filing_date DESC`; creditors within debtor sorted by claim amount DESC (numeric, not string)
- [ ] Reports with > 40 creditors across all debtors split into multiple Slack messages (one per debtor group + a header)
- [ ] Tier column shows `—` when `company_tier IS NULL`
- [ ] Status column shows pipeline-progress string when `sf_recency_status IS NULL`; recency string when populated
- [ ] On Supabase RPC error: `alerts.py` fires; process exits 1
- [ ] Railway cron service fires at 13:00 UTC Mon–Fri; cron service has no port binding in startCommand; confirmed via Railway deploy log

**Estimated effort:** M

---

### WP-04: DB migrations — company_tier + sf_recency_status [BE]

**Description:** Write and apply two Supabase migrations: (1) `creditors.company_tier VARCHAR(20) CHECK IN (...)` and (2) `salesforce_accounts.sf_recency_status VARCHAR(60)`.  Follow naming convention `20260530XXXXXX_au_group_*.sql`.

**Dependencies:** none.

**Acceptance criteria:**
- [ ] Both migrations apply cleanly via `supabase db push`
- [ ] `company_tier` is nullable (NULL = not yet enriched); constraint enforced
- [ ] `sf_recency_status` is nullable (NULL = not yet pushed)
- [ ] TypeScript types in `types/database.types.ts` regenerated

**Estimated effort:** S

---

### WP-05: PACER intake module [BE]

**Description:** Create `pipeline/intake.py`.  Query PACER for new Chapter 11 filings since last run; download Form 201 + Form 204 to S3; upsert `bankruptcies`; enqueue `document_parse` jobs.  Add `intake-cron` Railway cron service.

**Dependencies:** WP-01.

**Acceptance criteria:**
- [ ] PACER session auth succeeds with `PACER_USERNAME`/`PACER_PASSWORD`
- [ ] Court search scoped to `au_group_target_states` (read from Supabase runtime config table)
- [ ] Form 201 + Form 204 PDFs stored in S3 `raw-documents/{case_number}/form-201.pdf` and `form-204.pdf`
- [ ] `bankruptcies` row upserted (no duplicate on re-run for same `case_number`)
- [ ] `document_parse` job **enqueued** via `au_group_enqueue_job`; `enqueued=false` (already pending/running) handled without error
- [ ] `pacer_poll` `processing_job` row set to `completed` or `failed` per ADR-001
- [ ] Dry-run mode (`PACER_DRY_RUN=true`): logs discovery without writing to DB or S3
- [ ] Integration test (with test PACER account or stub): verifies at least one case is found and enqueued

**Estimated effort:** L

---

### WP-06: Parse module (queue drain → document-parser API) [BE]

**Description:** Create `pipeline/parse.py`.  Claim `document_parse` jobs from the queue (`au_group_claim_job`); POST to `document-parser /api/v1/parse/document` (async mode); poll until completion; mark job completed; **enqueue** `zoom_info_enrich` (`au_group_enqueue_job`).

**Dependencies:** WP-01.

**Acceptance criteria:**
- [ ] Claims `document_parse` job via `au_group_claim_job` (consumes a `pending` row)
- [ ] Async mode: polls `GET /api/v1/jobs/{document_id}` until `completed` or `failed`
- [ ] On parser return `manual_review_required=true`: marks job `manual_review_required` (do **not** enqueue enrich job)
- [ ] On parser return `completed`: marks job `completed`; **enqueues** `zoom_info_enrich` via `au_group_enqueue_job`
- [ ] On parse failure after 3 retries: marks job `failed`; fires `alerts.py`
- [ ] `X-API-Key` header sent; 401/403 errors surface as fatal (do not retry)
- [ ] Unit test: mock `/parse/document` endpoint; verify job state transitions

**Estimated effort:** M

---

### WP-07: report.py Tier + recency rendering [BE]

**Description:** **Render-only — no RPC migration.** The grouped report RPC (`au_group_daily_creditor_report_grouped`, created in WP-03) already returns `company_tier` (NULL until WP-08), and `report.py` calls that grouped function — so the column already flows through.  Update `report.py` to (a) render `company_tier` in the Tier column, (b) for rows with a `salesforce_accounts` record, replace the interim pipeline-status with `sf_recency_status`.  (Do NOT add the column to the flat `au_group_daily_creditor_report_rows` function — that RPC is not the one `report.py` uses; adding it there would never reach the report.)

**Dependencies:** WP-03 (grouped RPC), WP-04 (`company_tier` column). Tier values populate once WP-08 runs; recency once WP-09 runs.

**Acceptance criteria:**
- [ ] `report.py` renders Tier as `Enterprise`/`Mid-Market`/`SMB` or `—` if NULL (sourced from the grouped RPC's `company_tier`)
- [ ] `report.py` renders Status as `sf_recency_status` when a `salesforce_accounts` record exists; pipeline-progress string otherwise
- [ ] No change to the flat `au_group_daily_creditor_report_rows` RPC
- [ ] Existing RPC unit tests pass

**Estimated effort:** S

---

### WP-08: ZoomInfo enrichment module [BE] — BLOCKED on KD-53

**Description:** Create `pipeline/enrich.py`.  Company search + tier classification + persist `company_tier` / `zoominfo_company_id` / `normalized_name`.

**Dependencies:** WP-01, WP-04, ZoomInfo production API key (KD-53).

**Acceptance criteria:**
- [ ] `ZOOMINFO_API_KEY` missing → module logs "ZoomInfo key not configured; skip" and exits 0
- [ ] Company search: name + state; returns top match with confidence score
- [ ] Tier classification: correct for all three boundary cases (including $100M exact = Mid-Market)
- [ ] `creditors.company_tier`, `zoominfo_company_id`, `normalized_name` updated via RPC / SQL
- [ ] `zoom_info_contacts` row created (company-level; contact fields NULL in MVP)
- [ ] HTTP 429 from ZoomInfo: exponential backoff (3 retries, 15 s base); batch remaining creditors for next worker run if still hitting limit
- [ ] 80%+ match rate on test dataset of 25 company names (integration test)

**Estimated effort:** L

---

### WP-09: Salesforce push module [BE] — BLOCKED on SF access + KD-53

**Description:** Create `pipeline/salesforce.py`.  Account match/create/update + Bankruptcy_Event__c + email merge variables + `sf_recency_status` computation + persist.

**Dependencies:** WP-01, WP-04, WP-08, Salesforce access restored + KD-53 resolved, salesforce-audit.md §4 checklist complete.

**Acceptance criteria:**
- [ ] `SALESFORCE_CLIENT_ID` missing → exits 0 (guard)
- [ ] Account match: company name + BillingState; no duplicates created (FR-5.1 AC)
- [ ] `Company_Tier__c`, `ZoomInfo_URL__c` populated on Account
- [ ] `Bankruptcy_Event__c` child record created; no duplicate for same `Case_Number__c`
- [ ] Email merge variable fields populated (confirmed field list from OD-4)
- [ ] `sf_recency_status` computed correctly: open Opportunity OR Task/Event within 90 days → "Existing activity in Salesforce"; else "New Salesforce account"
- [ ] `salesforce_accounts.sf_recency_status` persisted
- [ ] `au_group_upsert_salesforce_account` called
- [ ] Salesforce API 503: 3 retries with exponential backoff; remaining leads re-queued for next worker run
- [ ] Integration test against SF sandbox: Account created, event logged, recency flag verified

**Estimated effort:** L

---

### WP-10: Parallel-run validation + n8n decommission [BE + Operator]

**Description:** Run code-native and n8n in parallel for 5 business days; compare output; deactivate and then delete n8n AU Group workflows; update README.md and CLAUDE.md.

**Dependencies:** WP-03 + WP-06 for intake/parse/report parity; WP-09 for full parity.

**Acceptance criteria:**
- [ ] 5 consecutive business-day daily reports match n8n SYS-09 output on creditor count ± 0
- [ ] No duplicate `bankruptcies` or `creditors` rows created during parallel run
- [ ] All 26 AU Group n8n workflows archived to `workflows/archived/` before deletion
- [ ] n8n workflows deleted from Cloud; folder confirmed empty
- [ ] `README.md` updated: remove "orchestrated by n8n" statement
- [ ] `CLAUDE.md` updated: topology section reflects code-native orchestration

**Estimated effort:** M

---

## 10. Sequencing and critical path

```
Immediately (unblocked):
  WP-00 (enqueue + claim RPCs) ── blocks ──> WP-01, WP-05, WP-06
  WP-02 (alerts) — parallel, no deps
  WP-04 (DB migrations) — parallel, no deps

After WP-00:
  WP-01 (worker skeleton)
  WP-05 (intake — can begin before WP-01 completes; shares enqueue RPC)
  WP-06 (parse — same)

After WP-00 + WP-01 + WP-02:
  WP-03 (report + grouped RPC)

After WP-04:
  WP-07 (report RPC + Tier column)

After WP-05 + WP-06 + WP-03 (report running in parallel with n8n):
  Begin partial parallel-run (intake/parse/report parity)

[BLOCKED — await KD-53]:
  WP-08 (enrich)

[BLOCKED — await WP-08 + SF access]:
  WP-09 (SF push)

After WP-08 + WP-09 complete:
  WP-10 (full parallel-run + decommission)
```

**Milestone 1 (deliverable to Keith, unblocked):** Daily creditor report delivered to Slack each business day from code-native pipeline.  Columns: Creditor, City, State, Claim, ZoomInfo URL (when populated), pipeline-status.  WP-00 + WP-01 + WP-02 + WP-03 + WP-04 + WP-05 + WP-06.  Est. 1.5–2 engineer-weeks.

**Milestone 2 (full FR-5.7 report):** All 7 PRD columns populated.  WP-07 + WP-08.  Blocked on KD-53.

**Milestone 3 (full MVP pipeline + n8n decommission):** WP-09 + WP-10.  Blocked on KD-53 + SF access.

---

## 11. Open decisions

| ID | Question | Options | Owner | Blocker? |
|---|---|---|---|---|
| **OD-1** | Report timing: 8 AM ET = 13:00 UTC (EST, Nov–Mar) or 12:00 UTC (EDT, Mar–Nov). Should the cron fire at 13:00 UTC year-round (sometimes 9 AM ET in summer) or follow DST? | (a) Fixed 13:00 UTC (simple; 1hr late in EDT) · (b) Two schedules switched manually · (c) Accept 12:00 UTC (early in EST) | Operator + Keith | No — pick before WP-03 deploy |
| **OD-2** | Tier storage: persist `company_tier` on `creditors` table (recommended — simpler report join) OR only on `zoom_info_contacts`? | Recommended: `creditors.company_tier` (WP-04) | Operator | No — WP-04 |
| **OD-3** | ZoomInfo API rate limits and batch size for the production key. | Verify actual tier limits from KD-53 credentials before coding `enrich_batch_size` | Keith / Engineering | Blocks WP-08 |
| **OD-4** | Exact email merge variable field list on SF Account (FR-5.6b). Which Account fields do AU Group's email templates reference? | Confirm via salesforce-audit.md §3.1 with Keith | Keith | Blocks WP-09 |
| **OD-5** | Salesforce recent-activity rule (FR-5.5): which Opportunity stages count? Objects: Opportunity + Task/Event (add EmailMessage?). Does a prior `Bankruptcy_Event__c` on the account also set "Existing activity"? | Confirm from salesforce-audit.md §3.2 with Keith | Keith | Blocks WP-09 |
| **OD-6** | SF account deduplication external ID: does `Pipeline_Creditor_ID__c` exist on Account in the org, or should `simple-salesforce` upsert on a different field? | Check during salesforce-audit.md §4 checklist | Eng (post SF access) | Blocks WP-09 |
| **OD-7** | PACER intake: does AU Group want intake to cover Chapter 7 and Subchapter V filings in addition to Chapter 11 (PRD Q5/Q7)? | CH11-only (safe default) vs. all three | Keith | Blocks WP-05 scope |
| **OD-8** | PACER intake credential path: the existing creds (`PACER_USERNAME`/`PACER_PASSWORD`) — confirm PACER Case Locator API vs. PACER CM/ECF UI scrape. The `adr-001` references "PACER poll" but the actual API surface is not specified in the repo. | PACER Case Locator REST API (preferred) vs. CM/ECF scrape | Operator (verify PACER API access) | Blocks WP-05 implementation |

---

## 12. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Salesforce login-IP lockout persists | High | Re-auth without VPN per salesforce-audit.md §5; all SF work isolated to WP-09 behind the guard |
| ZoomInfo key (KD-53) delayed >2 weeks | Medium | Milestone 1 (report) ships independently; Tier column shows `—`; pipeline otherwise complete |
| Railway cron skips if previous run still active (exec > 30 min) | Medium | `pipeline-worker` must exit within 25 min per invocation; batch limit in `worker.py`; alert on long-running exec |
| n8n quota exhaustion during parallel run | Medium | Parallel run is 5 business days only; n8n runs only the deactivated-last workflows; RC: cut to code-native sooner if n8n blocks |
| PACER API / CM-ECF access model unclear | Medium | OD-8; stub `intake.py` with a PACER mock for WP-05 unit tests; do not block report WP on this |
| ZoomInfo company match rate < 80% (NFR-2.2) | Medium | Log no-match creditors in `pipeline/enrich.py`; report sends regardless; Keith reviews no-match list |
| SF duplicate account creation | High | `simple-salesforce` upsert + `Pipeline_Creditor_ID__c` external ID (OD-6); integration tests on SF sandbox before prod |
| Daily report delivered late (after 8 AM ET) | Low | Railway cron fires at 13:00 UTC (8 AM ET); if previous run still active it is skipped; monitor Railway deploy logs for skip events |
| `company_tier` boundary at $100M not enforced consistently | Low | Inclusive-boundary rule in `enrich.py`: `revenue >= 100_000_000 → Mid-Market`; unit test the three boundary cases |

---

## 13. References

| Source | Location | Notes |
|---|---|---|
| PRD v3.0 | `docs/project/prd.md` | MVP scope banner governs; FR-4.1/4.2/5.1/5.5/5.7 are the spec targets |
| Brief v2.0 | `docs/project/project-brief.md` | MVP pipeline + Phase-2 deferred |
| Salesforce audit | `docs/project/salesforce-audit.md` | Schema gaps §2; open decisions §3; OD-4/5/6 come from here |
| ADR-001 | `docs/architecture/adr-001-rss-vs-pacer-intake.md` | Dual-source intake; PACER poll job type semantics |
| SYS-02 orchestration | `docs/architecture/sys-02-orchestration.md` | SYS-02 boundaries; document-parser API contract |
| Final tech stack | `docs/architecture/final-tech-stack.md` | Original AWS spec; reconciled in §2 of this doc |
| DB migration set | `supabase/migrations/` | Job-queue RPCs in `20260520120000`, `20260520160000`, `20260519140000`; daily report RPC canonical version in `20260529180000`; runtime config helpers in `20260529160000` |
| Railway cron docs | https://docs.railway.com/cron-jobs | Verified 2026-05-30: 5 min min interval; must exit on completion; skips if prior run still active; UTC only |
| document-parser service | `services/document-parser/` | FastAPI + Nixpacks + Railway; `/parse/document` async endpoint; `X-API-Key` auth |
| Jira board | https://automationarchitecture.atlassian.net/jira/software/projects/KD/boards/451 | KD project; KD-53 = ZoomInfo + SF credentials |
