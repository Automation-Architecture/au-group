# ADR-001: Bankruptcy case intake — RSS + PACER

**Status:** Accepted  
**Date:** 2026-05-19  
**Context:** FR-1.1 requires daily discovery of new Chapter 11 filings. SYS-01 uses court RSS + CourtListener; PRD also specifies PACER polling.

## Decision

Use a **dual-source intake** model:

| Source | Workflow | Role | Frequency |
|--------|----------|------|-----------|
| **RSS / CourtListener** | SYS-01 RSS Intelligence | Fast discovery, recap document URLs, initial `bankruptcies` row | Per RSS trigger (near real-time) |
| **PACER poll** | SYS-01 (job `pacer_poll`) + future dedicated nightly workflow | Authoritative case metadata, docket sync, spend-controlled | Daily overnight (target: results by 8:00 AM local) |

RSS alone does **not** satisfy FR-1.1. PACER poll remains required for production MVP.

## Consequences

- `processing_jobs.job_type = pacer_poll` must reach terminal status (`completed` / `failed`) — never leave `running` indefinitely.
- SYS-01 must pass `bankruptcy_id` and S3 keys to SYS-02 before document parse.
- Weekly Schedule F docket scans (SYS-06) use PACER/CM-ECF, not RSS.

## Alternatives considered

- **RSS only:** Rejected — misses official PACER timing and favorites workflow (FR-2.4).
- **PACER only:** Rejected — slower and higher cost for initial discovery; RSS reduces time-to-first-parse.
