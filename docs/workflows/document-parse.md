# Document Parse Workflow (n8n → SYS-02A)

Orchestration uses **HTTP** to the document-parser service. n8n owns `pipeline_executions` and `processing_jobs`; the parser owns extraction and Supabase audit tables.

## Prerequisites

- Form 201 / Form 204 PDF in S3 (`raw-documents/{case_number}/...`)
- `bankruptcies` row exists (from PACER poll / `au_group_upsert_bankruptcy`)
- Document-parser service reachable on VPC (port `8001`)
- Header `X-API-Key` set in n8n credentials

## Workflow: Parse new filing documents

### 1. Create processing job

Supabase insert into `processing_jobs`:

- `job_type`: `document_parse`
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
  "force": false
}
```

Repeat for Form 204 with `docket_hint`: `CREDITOR_MATRIX` and the Form 204 `s3_key`.

### 4. Branch on `manual_review_required`

IF `{{ $json.manual_review_required }}` = true:

- Update `processing_jobs.status` → `manual_review_required`
- Optional: Slack/email to Keith
- **Stop** — do not call ZoomInfo or Salesforce

ELSE:

- Update `processing_jobs.status` → `completed`
- Continue enrichment workflow

### 5. Complete pipeline execution

Update `pipeline_executions`:

- `status`: `completed` or `failed`
- `completed_at`: now
- `payload`: include parser response (`document_id`, `confidence`, `filing_type`)

## Timeout handling

For documents > ~30 pages, use poll pattern:

1. `POST /api/v1/parse/document` with short n8n timeout **or** split into `/parse/ocr` then `/extract/form201`
2. Poll `GET /api/v1/jobs/{document_id}` until `status` = `completed`

## Idempotency

Re-running the same PDF with the same `parser_version` returns cached `documents` row unless `force: true`.

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
- `bankruptcies` (via `au_group_upsert_bankruptcy_from_form201`)
- `creditors` (via `au_group_merge_creditor_matrix` when confidence OK)

## Related RPCs

- `au_group_upsert_bankruptcy` — PACER metadata (existing)
- `au_group_upsert_bankruptcy_from_form201` — Form 201 fields + ranges
- `au_group_merge_creditor_matrix` — creditor rows into pipeline tables
