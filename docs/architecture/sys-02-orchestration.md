# SYS-02 — Document parse orchestration (target architecture)

**Status:** Active  
**Date:** 2026-05-19  
**Workflow ID (n8n):** `qwVPSlI3L1RMsw9V` — AU Group - SYS-02 - Bankruptcy Intelligence v2

## Responsibility

SYS-02 is an **orchestrator only** (FR-1.2, FR-1.3 via parser, FR-3.3 HITL). It does **not** parse PDFs in n8n Code nodes and does **not** own Schedule F (FR-2.2–2.4).

| Owns | Does not own |
|------|----------------|
| `processing_jobs` (`document_parse`) | `form201_extractions` inserts (parser writes) |
| `pipeline_executions` | `bankruptcies` insert on intake (SYS-01) |
| HTTP to document-parser | Schedule F detect/process (SYS-06/07) |
| Branch → SYS-03 or stop on manual review | Direct PACER API (SYS-01B / SYS-06) |

## Related workflows

| ID | Name | Role |
|----|------|------|
| `pVPVaIbUixU95f43` | SYS-01 RSS Intelligence | Intake → `bankruptcies`, `schedule_f_queue` (`monitoring`) → calls SYS-02 |
| `qwVPSlI3L1RMsw9V` | SYS-02 | Document parse orchestration |
| `j26cimQ4S7kN67IP` | SYS-03 Creditor Enrichment | After successful parse (no manual review) |
| `gGRp6dF85A015TMH` | SYS-06 Schedule F Detector | Unarchived; **inactive** until PACER stubs are production-ready |
| `Sm45TsSpCR0LDo3l` | SYS-07 Schedule F Processor | Unarchived; **inactive** until Keith approval flow is wired |

## Authentication (document-parser)

| Consumer | Method | Notes |
|----------|--------|-------|
| n8n SYS-02 | `X-API-Key` header | Production; no token expiry |
| Operators / Swagger | `POST /api/v1/auth/login` → `Authorization: Bearer` | Set `JWT_SECRET`, `AUTH_USERNAME`, `AUTH_PASSWORD` on Railway |
| Parser enforcement | `REQUIRE_BANKRUPTCY_ID=true` | `POST /parse/document` returns 400 without `bankruptcy_id` |

See [document-parse.md](../workflows/document-parse.md) and [services/document-parser/README.md](../../services/document-parser/README.md).

## Target flow

```
Execute Workflow (from SYS-01)
  → Create processing_jobs (running)
  → pipeline_executions (started)
  → Load bankruptcies
  → For each document in job_payload:
       POST /parse/document (async_mode)
       → Poll GET /jobs/{document_id} if 202
  → If manual_review_required: job → manual_review_required, STOP
  → Else: job → completed, Execute SYS-03
  → pipeline_executions (completed)
```

## SYS-02 must not

- Insert or update `bankruptcies` / `form201_extractions` directly (duplicate parser).
- Run Schedule F weekly scan or PACER approval (use SYS-06/07).
- Mark `pacer_poll` jobs as completed (belongs to SYS-01B).
