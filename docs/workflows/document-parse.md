# Document Parse Workflow (n8n → SYS-02A)

Orchestration uses **HTTP** to the document-parser service. n8n owns `pipeline_executions` and `processing_jobs`; the parser owns extraction and Supabase audit tables.

**SYS-02 v2 (2026-05):** n8n no longer runs duplicate Form 201 Code/Supabase nodes — only `POST /api/v1/parse/document`. SYS-01 must pass `bankruptcy_id` into the Execute Workflow trigger (configure in n8n UI, not repo scripts).

**Important:** Parser `documents.id` is the job id for polling. Store it on `processing_jobs` (e.g. in `payload.document_id` or a dedicated column) so retries and support can correlate n8n ↔ parser.

**Workflow IDs:** SYS-01 `pVPVaIbUixU95f43` → SYS-02 `qwVPSlI3L1RMsw9V` → SYS-03 `j26cimQ4S7kN67IP`. Target architecture: [sys-02-orchestration.md](../architecture/sys-02-orchestration.md).

## SYS-02 must not

- Direct Supabase **insert** into `bankruptcies`, `form201_extractions`, or `creditors` (parser + RPCs own that).
- Schedule F detect/process nodes (use SYS-06 / SYS-07).
- `Route Job Type` branches for `schedule_f_detect` / `schedule_f_process` on the active path.

## Authentication

| Caller | How |
|--------|-----|
| **n8n** | `X-API-Key: {{DOCUMENT_PARSER_API_KEY}}` on Parse + Poll nodes |
| **Humans / Swagger** | `POST /api/v1/auth/login` then `Authorization: Bearer {access_token}` |

Login requires `JWT_SECRET`, `AUTH_USERNAME`, `AUTH_PASSWORD` on the parser service ([README](../../services/document-parser/README.md)).

## Prerequisites

- Form 201 / Form 204 PDF in S3 (`raw-documents/{case_number}/...`)
- `bankruptcies` row exists (from PACER poll / `au_group_upsert_bankruptcy`)
- Document-parser service reachable on VPC (port `8001`)
- Header `X-API-Key` set in n8n credentials
- Supabase migrations applied, including `20260519120000_manual_review_resolve.sql`

## Workflow: Parse new filing documents

### 1. Create processing job

Supabase insert into `processing_jobs`:

- `job_type`: `document_intelligence` (legacy: `document_parse`)
- `status`: `running`
- `bankruptcy_id`: from trigger

Record `processing_job_id` for `pipeline_executions`.

### 2. Log pipeline execution (started)

Insert `pipeline_executions`:

- `status`: `started`
- `n8n_workflow_id`, `n8n_execution_id`
- `processing_job_id`, `bankruptcy_id`
- `payload`: `{ "s3_key": "...", "step": "parse_document" }`

### 3. HTTP Request — parse document

```
POST {{DOCUMENT_PARSER_URL}}/api/v1/parse/document
Headers:
  X-API-Key: {{DOCUMENT_PARSER_API_KEY}}
  Content-Type: application/json
Body:
{
  "bankruptcy_id": "{{ $json.bankruptcy_id }}",
  "s3_key": "{{ $json.s3_key }}",
  "docket_hint": "FORM_201",
  "force": false,
  "async_mode": true
}
```

| Response | Meaning |
|----------|---------|
| **200** | Sync parse finished — body is the **final** result (use for step 4) |
| **202** | Async accepted — body has `status: "processing"` and `document_id` — **must poll (step 3b)** before step 4 |
| **409** | Same PDF still processing — poll existing `document_id`; do not use `force: true` until poll is terminal |
| **429** | Parser busy (`ASYNC_PARSE_MAX_CONCURRENT`) — wait 30–60s and retry POST |

- With `"async_mode": true`, n8n HTTP timeout can stay short (e.g. 30s); OCR runs in the background.
- Omit `async_mode` (or `false`) for small PDFs when a single blocking **200** is acceptable.

Repeat for Form 204 with `docket_hint`: `CREDITOR_MATRIX` and the Form 204 `s3_key` (separate `document_id` per file).

### 3b. Poll until complete (required when step 3 returned 202)

Do **not** use the 202 body for enrichment or `manual_review_required`. Loop:

```
GET {{DOCUMENT_PARSER_URL}}/api/v1/jobs/{{ document_id }}
Headers:
  X-API-Key: {{DOCUMENT_PARSER_API_KEY}}
```

Suggested n8n loop:

- Interval: **10s** (5–15s acceptable)
- Max wait: **30 minutes** (adjust for very large scans)
- Stop when `status` is `completed` or `failed`

| Poll `status` | n8n action |
|---------------|------------|
| `processing` | Wait and poll again |
| `completed` | Use this JSON as **parser result** for step 4 and 5 |
| `failed` | See [Failed parse runbook](#failed-parse-runbook) |

Store `document_id` on `processing_jobs.payload` after first parse response.

### 4. Branch on `manual_review_required` (use polled or 200 body only)

Use the **final** parser result from step 3 (200) or step 3b (poll when 202):

```
manual_review_required = {{ $('Poll Job').item.json.manual_review_required }}
document_id = {{ $('Poll Job').item.json.document_id }}
```

IF `manual_review_required` = true:

- Update `processing_jobs.status` → `manual_review_required`
- Optional: Slack/email to Keith with `document_id` and link to review queue
- **Stop** — do not call ZoomInfo or Salesforce
- Follow [Manual review runbook](#manual-review-runbook)

ELSE:

- Update `processing_jobs.status` → `completed`
- Continue enrichment workflow (ZoomInfo → Salesforce)

### 5. Complete pipeline execution

Update `pipeline_executions`:

- `status`: `completed` or `failed`
- `completed_at`: now
- `payload`: include final parser result (`document_id`, `confidence`, `filing_type`, `manual_review_required`)

## Failed parse runbook

When poll returns `status: "failed"` (or POST returns 500 with `status: "failed"`):

1. Set `processing_jobs.status` → `failed`
2. Log `error` from job response into `processing_jobs.error_message` (or `pipeline_executions.payload`)
3. Alert operator (Slack/email)
4. **Do not** continue to ZoomInfo/Salesforce
5. Retry options (pick one per incident):
   - **Retry parse:** fix root cause (S3, OCR), then `POST /parse/document` with same `s3_key` and `"force": true` only after any in-flight job is terminal (not `processing`)
   - **Escalate:** manual review / re-upload PDF

## Manual review runbook

When step 4 stops on `manual_review_required`:

1. Operator lists queue: `GET /api/v1/review-queue?status=pending`
2. Fix data if needed (re-upload PDF, correct filing, etc.)
3. Resolve the queue item:
   ```
   POST {{DOCUMENT_PARSER_URL}}/api/v1/review/{{ review_queue_id }}/resolve
   Headers:
     X-API-Key: {{DOCUMENT_PARSER_API_KEY}}
   Body:
   { "resolved_by": "keith" }
   ```
   This sets queue row to `resolved` and clears `bankruptcies.manual_review_required` when no other pending reviews exist for that bankruptcy.

4. **Resume enrichment (choose one policy):**

   | Policy | When | Next step |
   |--------|------|-----------|
   | **A — Continue** (default) | Extraction is good enough for ops | Set `processing_jobs.status` → `completed`; run ZoomInfo/Salesforce using existing `form201_extractions` / DB data |
   | **B — Re-parse** | PDF was wrong or fields must be recomputed | `POST /parse/document` with `"force": true`, poll if async, then branch again on `manual_review_required` |
   | **C — Human-only** | Case closed without automation | Leave `processing_jobs` as `manual_review_required`; no auto resume |

Document the chosen policy in your n8n workflow comments. Policy **A** is typical after a false-positive review flag.

## Verification checklist (2026-05-19)

| Check | Result |
|-------|--------|
| SYS-02 active path | 23 nodes — document parse + async poll only |
| SYS-01 handoff | `Queue Document Parse` passes `bankruptcy_id`, `job_payload` |
| `schedule_f_queue` | `status=monitoring` at intake |
| Unit tests | `pytest tests/test_api_parse.py` — `bankruptcy_id` guard + async 202 |
| Railway `/health` | `https://au-group.railway.app/health` → 200 |
| Railway `/api/v1/*` | **Redeploy required** — routes return 404 on current deploy; push latest `services/document-parser` and confirm env from `.env.railway.example` |

## Timeout handling

For large PDFs, prefer async parse:

1. `POST /api/v1/parse/document` with `"async_mode": true`
2. Poll `GET /api/v1/jobs/{document_id}` until terminal (step 3b)
3. Alternative for small files: `"async_mode": false` and wait for **200**
4. `POST /api/v1/extract/form201` — runs the full parse pipeline (not OCR-only output). Prefer step 1–2 for n8n; use extract for ad-hoc or tooling calls.

### Extract endpoints (`/extract/form201`, `/extract/creditor-matrix`)

- **Validation without re-OCR:** Responses always include `validation`. If the cached parse omitted it, the parser recomputes validation from extracted fields (`validate_form201` / `validate_creditor_matrix`) without `force: true` re-parse.
- **Re-parse:** `extract/form201` calls `parse_document` with `force: true` only when `form201` is missing on a **terminal** row (`completed` or `failed`). It does **not** re-parse because `validation` is null.
- **While async job is processing:** Do not call extract until poll returns `completed`. If the document is still `processing`, extract returns **409** with a message to poll `GET /api/v1/jobs/{document_id}` first (same rule as `force: true` on `/parse/document`).

## Idempotency

Re-running the same PDF with the same `parser_version` returns cached `documents` row unless `force: true`.

- Same hash while job is **`processing`**: POST returns **202** with same job; do not schedule duplicate work — keep polling.
- **`force: true`** while still **`processing`**: returns **409** — poll until complete first.
- **`force: true`** after **`completed`** or **`failed`**: re-runs extraction; use for retry after fix.

## S3 layout

```
raw-documents/{case_number}/{document_id}.pdf
ocr-outputs/{case_number}/{document_id}.txt
parsed-outputs/{case_number}/{document_id}.json
```

## Supabase tables (parser writes)

- `documents`
- `form201_extractions`
- `creditor_matrix_extractions` / `creditor_matrix_rows`
- `manual_review_queue`
- `bankruptcies` (via `au_group_upsert_bankruptcy_from_form201`; sticky `manual_review_required` OR until all reviews resolved)
- `creditors` (via `au_group_merge_creditor_matrix` when confidence OK and not in manual review)

## Related RPCs

- `au_group_upsert_bankruptcy` — PACER metadata (existing)
- `au_group_upsert_bankruptcy_from_form201` — Form 201 fields + ranges
- `au_group_merge_creditor_matrix` — creditor rows into pipeline tables
- `au_group_resolve_manual_review` — clear review queue item + bankruptcy flag when appropriate
