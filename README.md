# AU Group — Bankruptcy Creditor Intelligence

AI-powered lead-generation platform that monitors federal bankruptcy filings, extracts creditors from Schedule F documents, enriches them with decision-maker contacts, and delivers qualified leads into Salesforce.

**Client:** Keith Woods · **Slug:** `au-group` · **Jira:** `KD` · **Stage:** discovery → build

## What it does

1. **Monitor** federal bankruptcy filings via PACER (and RSS feeds for early detection).
2. **Detect & ingest** Schedule F documents 1–3 months post-filing — the long tail of mid-sized creditors competitors miss.
3. **Parse** PDFs (Form 201/204, Schedule E/F) with OCR + NLP to extract creditor names, addresses, claim amounts, and company-vs-individual classification.
4. **Enrich** companies via ZoomInfo for decision-maker contacts, revenue, and firmographics.
5. **Route** qualified leads to Salesforce with territory assignment and historical bankruptcy-exposure context for differentiated outreach.

Human-in-the-loop gating on PACER document purchases ($0.10/page) controls cost.

## Repo layout

| Path | Purpose |
|---|---|
| [`project.config.yaml`](./project.config.yaml) | Canonical project metadata (slug, Jira key, dashboard config) |
| [`services/document-parser/`](./services/document-parser/) | **SYS-02A** — FastAPI document OCR/classification service (Railway). Orchestrated by n8n over HTTP. |
| [`supabase/migrations/`](./supabase/migrations/) | Pipeline schema: `bankruptcies`, `creditors`, `bankruptcy_creditors`, `zoom_info_contacts`, `salesforce_accounts`, `processing_jobs`, `schedule_f_queue`, document-intelligence tables, RLS policies |
| [`types/database.types.ts`](./types/database.types.ts) | Generated TypeScript types for the Supabase schema |
| [`docs/project/`](./docs/project/) | Project brief, PRD, Jira backlog, client dashboard config, credentials checklist |
| [`docs/architecture/`](./docs/architecture/) | Final tech stack, ADR-001 (RSS vs PACER intake), SYS-02 orchestration, architecture debate |
| [`docs/workflows/`](./docs/workflows/) | n8n workflow specs (document-parse, booking, active-workflows live view) |
| [`docs/n8n/`](./docs/n8n/) | n8n-MCP setup and reference for AI-assisted workflow authoring |
| [`scripts/`](./scripts/) | One-off operational scripts (e.g. `backfill_orphan_documents.py`) |
| [`references/`](./references/) | Step-by-step discovery reference files (artifact of the AAA Discovery flow that scoped this project) |

## Deployed stack

- **Database:** Supabase Postgres — migrations prefixed `au_group_*` and `sys02_*`
- **Document parser:** FastAPI on Railway (`services/document-parser/`), Python 3.11, Tesseract + pdfplumber + spaCy
- **Orchestration:** n8n (workflows specified in `docs/workflows/`, `docs/n8n/`)
- **Storage:** Supabase Storage / S3 for raw PDFs and parsed outputs
- **Destination CRM:** Salesforce (`Bankruptcy_Event__c`, `Creditor__c` custom objects)
- **Enrichment:** ZoomInfo

`docs/architecture/final-tech-stack.md` documents the originally-debated AWS RDS/ECS path; the actual deployed stack converged on Supabase + Railway + n8n. RDS/ECS remain documented as the scale-out alternative.

## Document parser (SYS-02A)

The FastAPI service in `services/document-parser/` is the only deployed compute in this repo. See its [README](./services/document-parser/README.md) for local dev setup, system dependencies, and the n8n integration contract.

```bash
cd services/document-parser
cp .env.example .env   # Supabase, S3, API_KEY
./scripts/dev.sh
# Health: GET http://localhost:8001/health
```

## Pipeline reference

| Stage | Job type (`processing_jobs.job_type`) | Notes |
|---|---|---|
| Filing intake | `pacer_poll` | PACER + RSS monitoring |
| Document classification | `document_intelligence` | Detect Schedule F, gate on cost |
| Document extraction | `document_parse` | SYS-02A document-parser service |
| Creditor enrichment | `zoom_info_enrich` | ZoomInfo company + contact lookup |
| CRM push | `salesforce_push` | Territory-routed lead creation |

## Client dashboard

Live at `https://dashboard.automationarchitecture.ai/client/au-group`. Per-slug stage tracker is backed by the AAA Dashboard API (Railway); Sprint Board, Activity, Horizon, Weekly Updates, and Documents are pulled from the `Automation-Architecture/aaa-client-dashboard-data` repo's `sync` branch. See `docs/project/client-dashboard.md` and `docs/AAA_CLIENT_DASHBOARD_REPO_STATUS.md`.

## Discovery artifacts

This project was scoped via the AAA Discovery flow. The numbered step references in [`references/`](./references/) and the throughput log in [`docs/throughput-log.md`](./docs/throughput-log.md) are the historical record of how the scope, PRD, tech spec, and Jira backlog were produced. They are not part of the runtime system.
