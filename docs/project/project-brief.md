# Bankruptcy Creditor Intelligence Platform
## Project Brief

**Version:** 2.0
**Date:** May 29, 2026
**Client:** AU Group (contact: Keith Woods)
**Prepared by:** Automation Architecture

---

## MVP Scope (May 2026 client revision)

Keith has simplified the MVP to its highest-value core: **get the creditors out of PACER, enrich the company in ZoomInfo, push the company into Salesforce with bankruptcy context, and hand Keith a daily report so he can run outreach himself.** Contact selection, tiered targeting, and automated outreach are intentionally left to AU Group's team. The full Schedule F long-tail, historical exposure database, and automated sequences remain the strategic Phase 2+ roadmap (see *Deferred to Phase 2+*) — descoped to ship Phase 1 fast, not abandoned.

**The MVP pipeline (each business day):**
1. **PACER** — pull new Chapter 11 filings in target states; extract the top-20 unsecured creditors (Form 204) + debtor metadata (Form 201).
2. **ZoomInfo** — match each **creditor company** and classify its size **tier** (company-level only; no contact selection).
3. **Salesforce** — create/update the **creditor** as an Account, log the bankruptcy in the Bankruptcy section (`Bankruptcy_Event__c`), store the company tier, and populate the email merge variables.
4. **Daily report (Slack)** — list the creditors grouped by bankrupt company, with state, claim amount, tier, a ZoomInfo link, and a Salesforce-recency flag so Keith decides generic vs. custom email.

> **Entity note:** the **creditor** company (the lead AU Group sells to) is what gets enriched and becomes the Salesforce Account. The **debtor** (bankrupt company) is the grouping and is logged as the bankruptcy event on that account. The report's recency flag is about the *creditor's* footprint in Salesforce.

---

## Project Overview

An AI-powered lead generation platform that turns federal bankruptcy filings into enriched, Salesforce-ready sales leads with a daily decision-support report.

The platform monitors federal court filings via PACER, extracts the top-20 unsecured creditors from each new Chapter 11 filing, matches each creditor company in ZoomInfo, and delivers it to Salesforce with the bankruptcy event logged and email variables populated. Each day it produces a report — grouped by bankrupt company — that shows every creditor with its state, claim amount, ZoomInfo link, and whether the creditor already has recent activity in Salesforce. AU Group's team uses that report to choose the right contact and the right email.

**Business Impact:** Replaces a ~$75K/year prospecting hire with a 24/7 AI pipeline at roughly half the annual cost, eliminating the manual PACER → ZoomInfo → Salesforce copy-paste workflow and giving the sales team a single daily, decision-ready creditor list.

**Strategic roadmap (Phase 2+):** the long tail of mid-sized creditors on full Schedule F documents (released 1–3 months post-filing) and historical bankruptcy-exposure messaging remain the differentiated play competitors miss — sequenced after the Phase 1 daily pipeline proves out.

---

## Business Goals

### Primary Objectives (MVP)

1. **Automate creditor extraction** — Process 100% of daily Chapter 11 filings in target states within 24 hours, extracting the top-20 creditors (Form 204) per filing.
2. **Eliminate manual data entry** — Match each creditor company in ZoomInfo and deliver it to Salesforce with the bankruptcy event logged and email variables populated — no manual copy-paste.
3. **Deliver a daily decision-ready report** — Give Keith a daily Slack report of creditors grouped by bankruptcy, with state, claim amount, ZoomInfo link, and a Salesforce-recency flag.
4. **Surface Salesforce context** — Flag whether each creditor already has recent Salesforce activity so the team chooses generic vs. custom outreach.

### Phase 2+ Objectives (deferred)

5. **Capture Schedule F opportunities** — Detect full creditor lists (Schedule F) within 48 hours of publication to reach the mid-sized creditors competitors miss.
6. **Enable differentiated outreach** — Build a historical creditor-bankruptcy database to message prospects with exposure data (e.g., "You've appeared in 13 bankruptcies over 5 years").
7. **Automate outreach** — Trigger templated sequences (ZoomInfo Engage/SalesLoft) with do-not-contact and active-engagement suppression.

---

## Core Problem Being Solved

AU Group's team currently performs bankruptcy-driven lead generation manually. The MVP targets the two bottlenecks that cost the most time today:

### 1. Data Entry Consumes Half the Day
The manual copy-paste process of moving creditor data from PACER PDFs to ZoomInfo to Salesforce eats hours that should be spent selling. The MVP automates that entire path and hands back a daily list.

### 2. No Single Daily View with Salesforce Context
The team has no consolidated, daily, decision-ready list of new creditors that also tells them which companies they already have activity with — so they waste time re-checking Salesforce per company before deciding how to reach out.

*Phase 2+ problems (Schedule F timing disadvantage, missing the mid-sized long tail, no historical exposure context, PACER cost friction on document purchases) remain real and are carried into the deferred roadmap below.*

---

## Target Users

### Primary User: Keith Woods (U.S. Sales Lead)
- **Current workflow:** Manually logs into PACER daily, downloads documents, extracts creditor lists, searches ZoomInfo, enters data into Salesforce, decides outreach.
- **Pain points:** Spends hours/day on data entry; no consolidated daily list with Salesforce context.
- **MVP needs:** An automated PACER → ZoomInfo → Salesforce pipeline and a daily report that lets him pick the contact and the email himself.

### Secondary Users: Territory Reps (Mike, Frazier, et al.)
- **Current workflow:** Receive lead lists from Keith, follow up on bankruptcy prospects in assigned states.
- **MVP needs:** Creditors visible in Salesforce with full bankruptcy context; territory routing and automated outreach are Phase 2+.

---

## Main Features

### MVP

#### 1. PACER Filing Monitor
- Daily polling of federal court filings for new Chapter 11 bankruptcies in target states
- Extraction of the top-20 unsecured creditors (Form 204) per filing
- Debtor metadata capture (Form 201): name, location, industry, estimated assets/liabilities, creditor count

#### 2. ZoomInfo Company Enrichment (company-level only)
- Match each **creditor company** in ZoomInfo by name + location
- Capture the company's ZoomInfo profile URL (for the daily report) and firmographics needed for Salesforce
- **Classify the company's size tier** (Enterprise / Mid-Market / SMB) as an attribute — stored on the Salesforce account and shown in the report
- **No decision-maker contact selection in MVP** — tier does not drive automated contact-title targeting; AU Group picks contacts manually (see *Deferred*)

#### 3. Salesforce Integration
- **Account create/update:** match existing accounts by name/address; create or update the **creditor** company
- **Bankruptcy logging:** record the bankruptcy event (`Bankruptcy_Event__c`) — debtor name, filing date, claim amount, case number, court district — on the creditor account
- **Email variables:** populate the merge fields the team's email templates need
- **Recent-activity lookup:** determine whether the creditor already has recent Salesforce activity (open opportunities or activity within 90 days) — surfaced as the report's status flag

#### 4. Daily Creditor Report (Slack)
- Delivered each business day to the project Slack channel
- **Grouped by bankrupt company (debtor)**; under each debtor, a table of its creditors
- Columns: **Creditor · City · State · Claim ($) · Tier · Status · ZoomInfo URL**
- **Status** = the Salesforce-recency flag — e.g. *"New Salesforce account"* vs *"Existing activity in Salesforce"* — so Keith decides generic vs. custom email at a glance
- The team handles contact selection and outreach from the report

### Deferred to Phase 2+

These remain the strategic roadmap — descoped from MVP, not dropped.

#### Schedule F Monitoring Queue
- Active-case monitoring, weekly docket scans for Schedule F publication, keyword detection, PACER-favorites purchase-approval workflow, alert within 48 hours. **This long-tail of mid-sized creditors is the competitive differentiator** competitors miss on day one.

#### Multi-Format Document Parsing Engine
- Structured Schedule E/F (Form 206E/F), simple creditor lists, handwritten/scanned OCR with manual review, company-vs-individual classification, intra-filing dedup. (MVP needs only Form 201/204.)

#### ZoomInfo Decision-Maker Contact Retrieval
- Ranked decision-maker contacts, engagement scoring, and automated **tier → target-title** mapping with title-fallback logic. Deferred — AU Group selects contacts manually in MVP. (Tier *classification* is in MVP as a company attribute; mapping tier → titles for automated contact retrieval is the Phase 2 part.)

#### Automated Outreach Triggering
- Templated sequences via ZoomInfo Engage/SalesLoft, T+1 timing, do-not-contact + active-engagement suppression, territory routing.

#### Historical Creditor Database
- Import AU Group's ~25K-row historical dataset, track cumulative exposure, repeat-exposure flagging for differentiated messaging.

---

## Success Metrics (MVP)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily filings processed | 100% of target-state Chapter 11 filings | Daily count vs. PACER |
| Time-to-Salesforce (top-20 creditors) | **<24 hours** from filing | Timestamp delta: filing → Salesforce |
| ZoomInfo company match rate | **80%+** | (Creditors matched) / (Total creditors) |
| Daily report delivered | Every business day, by 8:00 AM local | Slack post timestamp |
| Salesforce data accuracy | Zero duplicate accounts; correct bankruptcy logging | Spot audit |
| Manual data-entry time reduction | **50%+** | Time-tracking before/after |

*Phase 2+ metrics (Schedule F coverage, outreach response rate, historical exposure messaging lift) attach to their respective deferred features.*

---

## Constraints and Requirements

### Technical Constraints

**PACER Integration**
- Document costs: $0.10/page, max $4.50/document. MVP works from the free/low-cost docket + Form 201/204; bulk document purchase (Schedule F) is Phase 2 with human approval.
- API rate limits and access restrictions apply.

**ZoomInfo API**
- Rate limits on lookup volume (confirm API tier and throughput)
- Company match rate limited by ZoomInfo database coverage (contact-level scope is deferred)

**Salesforce Integration**
- Must work with existing field structure and territory mapping
- Recent-activity detection depends on current data hygiene (definition: open opportunities or activity within 90 days)
- Custom object/fields for bankruptcy logging (`Bankruptcy_Event__c`)

### Scope Constraints

**In Scope (MVP — Phase 1)**
- PACER daily filing monitor + top-20 (Form 204) extraction + Form 201 debtor metadata
- ZoomInfo **company** match + profile URL + **size-tier classification** (no contact selection)
- Salesforce: creditor account create/update, bankruptcy logging, tier attribute, email variables, recent-activity flag
- Daily Slack report (creditors grouped by debtor; state, claim, tier, ZoomInfo link, recency status)

**Deferred to Phase 2+**
- Schedule F monitoring queue + PACER purchase-approval workflow
- Multi-format document parsing (Schedule E/F, OCR, page classification)
- ZoomInfo decision-maker contact retrieval + automated tier→title targeting
- Automated outreach (sequences, T+1, territory routing, DNC/active-engagement suppression)
- Historical creditor database + repeat-exposure flagging

**Out of Scope (all phases, unless re-scoped)**
- Automated PACER document purchasing without human approval
- Claims agent portal scraping (Kroll, Epiq, Stretto)
- Multi-signal prospecting (job postings, press releases)
- AI-personalized outreach composition
- Bankruptcy payout/recovery tracking

### Data Quality Requirements (MVP)

- 95%+ extraction accuracy on Form 204 top-20 creditor lists
- 90%+ company-vs-individual classification accuracy
- 80%+ ZoomInfo company match rate
- 95%+ correct Salesforce account match/no-match; zero duplicate account creation
- Correct, auditable bankruptcy-event logging on each creditor account

### Processing Requirements

| Process | Frequency | SLA |
|---------|-----------|-----|
| New filing detection | Daily | Results by 8:00 AM local time |
| Top-20 creditor extraction | Daily (per filing) | Within 24 hours of filing |
| ZoomInfo enrichment | On-demand (per batch) | Within 4 hours of extraction |
| Salesforce push | On-demand (per batch) | Immediately after enrichment |
| Daily report | Daily | By 8:00 AM local time |

---

## Phased Build Plan

| Phase | Scope | Est. Duration |
|-------|-------|---------------|
| **Phase 1 (MVP)** | Daily pipeline: PACER → top-20 → ZoomInfo company → Salesforce (bankruptcy + email vars + recency flag) → daily Slack report | 3–4 weeks |
| **Phase 2** | Schedule F monitoring queue + multi-format parsing + human-in-the-loop purchase approval | 3–4 weeks |
| **Phase 3** | Tier-based targeting + contact retrieval + automated outreach | 2–3 weeks |
| **Phase 4** | Historical data import + repeat-exposure flagging; claims-agent portals, multi-signal prospecting | Ongoing |

---

## Open Questions

| # | Question | Owner | Impact |
|---|----------|-------|--------|
| **Q1** | Exact target states for initial rollout? | Keith | Scope of daily monitoring + cost |
| **Q2** | Salesforce field structure for bankruptcy data — does `Bankruptcy_Event__c` (or equivalent) exist, and which email merge variables are required? | Keith | Salesforce integration design |
| **Q3** | Definition of "recent activity" for the status flag — confirm the 90-day / open-opportunity rule and which Salesforce objects count. | Keith | Recency-flag logic |
| **Q4** | ZoomInfo API access level + rate limits (production key for automated use)? | Keith / Eng | Enrichment throughput |
| **Q5** | Chapter 7 in addition to Chapter 11? Subchapter V? | Keith | Filing scope and volume |
| **Q6** | Should government entities / major financial institutions be auto-excluded from the creditor list? | Keith | Creditor filtering |
| **Q7** | Daily report — exact column order/labels confirmed against the client's example; any additional fields (e.g. industry, claim status)? | Keith | Report spec |

---

## Next Steps

1. Confirm the daily-report columns against the client's example and lock the recency-flag definition.
2. Salesforce audit — bankruptcy object/fields, email merge variables, recent-activity rule.
3. ZoomInfo + PACER production credentials (tracked in KD-53 — blocks the enrichment + Salesforce stages).
4. Finalize the simplified Phase 1 pipeline against the revised Jira board.

---

**Document Status:** MVP scope revised per client (May 2026)
**Revision History:**
- v1.0 (March 12, 2026) — Initial project brief, standardized section format
- v2.0 (May 29, 2026) — **MVP simplification per client:** company-level ZoomInfo only (contacts/tiering manual); Salesforce company export + bankruptcy logging + email variables + recent-activity flag; daily Slack creditor report as the primary deliverable. Schedule F, multi-format parsing, tier targeting, automated outreach, and historical DB carried forward as Phase 2+ deferred.
