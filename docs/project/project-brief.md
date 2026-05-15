# Bankruptcy Creditor Intelligence Platform
## Project Brief

**Version:** 1.0  
**Date:** March 12, 2026  
**Client:** Keith Woods  
**Prepared by:** Automation Architecture

---

## Project Overview

An AI-powered lead generation platform that automates the process of identifying unsecured creditors from federal bankruptcy filings and converting them into enriched, actionable sales leads with automated outreach capabilities.

The platform monitors federal court filings via PACER, extracts creditor data from bankruptcy schedules, enriches companies with decision-maker contacts through ZoomInfo, and delivers qualified leads directly to Salesforce — eliminating manual data entry and ensuring zero missed opportunities.

**Competitive Differentiation:** Targets the long tail of mid-sized creditors on full Schedule F documents (released 1–3 months post-filing) that competitors miss, combined with historical bankruptcy exposure data to enable highly differentiated outreach messaging.

**Business Impact:** Replaces a ~$75K/year prospecting hire with a 24/7 AI agent at roughly half the annual cost, delivering 10x improvement in daily lead extraction, 50%+ reduction in rep admin time, and zero missed opportunities.

---

## Business Goals

### Primary Objectives

1. **Automate creditor extraction** — Process 100% of daily bankruptcy filings in target states within 24 hours, extracting top 20 creditors on day one
2. **Capture Schedule F opportunities** — Detect 100% of full creditor lists (Schedule F) within 48 hours of publication, capturing hundreds of mid-sized creditors competitors miss
3. **Eliminate manual data entry** — Deliver enriched leads directly to Salesforce with territory routing and outreach triggering, removing manual copy-paste workflows
4. **Enable differentiated outreach** — Build historical creditor-bankruptcy database to message prospects with exposure data (e.g., "You've appeared in 13 bankruptcies over 5 years")
5. **Control costs intelligently** — Human-in-the-loop approval for PACER document purchases ($0.10/page) to balance opportunity capture with budget discipline

### Success Criteria

- **10x improvement** in daily creditor leads extracted vs. manual baseline
- **<24 hours** time-to-lead for top 20 creditors from new filings
- **80%+ contact enrichment match rate** via ZoomInfo
- **50%+ reduction** in rep prospecting admin time
- **5–10x monthly lead volume** vs. pre-automation baseline

---

## Core Problem Being Solved

Keith Woods and his team currently perform bankruptcy-driven lead generation entirely manually, creating five critical bottlenecks:

### 1. Missed Opportunities
The volume of filings exceeds manual processing capacity. Schedule F documents (containing hundreds of mid-sized creditors) that drop 1–3 months after initial filing are frequently missed because there is no systematic way to monitor thousands of active dockets for new creditor lists.

### 2. Data Entry Consumes Half the Day
Even when creditor data is found, the manual copy-paste process of moving it from PDFs to ZoomInfo to Salesforce eats up hours that should be spent on actual selling and relationship building.

### 3. No Historical Context
The team has no centralized database of creditor bankruptcy exposure over time. They cannot tell a prospect they have been impacted by multiple bankruptcies, which is a powerful talking point that would differentiate their outreach.

### 4. Competitive Timing Disadvantage
Everybody sees the top 20 creditors on day one. The mid-sized creditors on the full Schedule F are the valuable targets, but by the time the team manually finds them, the window of relevance has often closed.

### 5. PACER Cost Friction
Documents cost $0.10/page (max $4.50/document). Downloading the wrong documents wastes money. The team needs intelligent recommendations on what's worth purchasing.

---

## Target Users

### Primary User: Keith Woods (U.S. Sales Lead)
- **Current workflow:** Manually logs into PACER daily, downloads bankruptcy documents, extracts creditor lists, searches ZoomInfo for contacts, enters data into Salesforce, triggers email sequences
- **Pain points:** Cannot keep up with filing volume, spends 4+ hours/day on data entry, frequently misses Schedule F publications
- **Needs:** Automated daily pipeline from PACER to enriched leads in Salesforce with intelligent purchase recommendations and outreach triggering

### Secondary Users: Territory Reps (Mike, Frazier, et al.)
- **Current workflow:** Receive manual lead lists from Keith, follow up on bankruptcy-related prospects in their assigned states
- **Pain points:** Leads arrive slowly and incompletely, lack context on bankruptcy events, no historical exposure data for messaging
- **Needs:** Filtered daily lead lists for assigned territories with full bankruptcy context visible in Salesforce, automated outreach for qualified prospects

---

## Main Features

### 1. PACER Filing Monitor
- Daily polling of federal court filings for new Chapter 11 bankruptcies in target states
- Automatic extraction of top 20 unsecured creditors (Form 204) on day one
- Debtor metadata capture: name, location, industry, estimated assets/liabilities, creditor count

### 2. Schedule F Monitoring Queue
- Active case monitoring with weekly docket scans for Schedule F publication
- Keyword detection: "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F"
- Purchase approval workflow: system flags documents with cost estimates, Keith approves/rejects via PACER favorites
- Alert delivery within 48 hours of Schedule F filing

### 3. Multi-Format Document Parsing Engine
- **Structured Schedule E/F (Form 206E/F):** Tabular format with creditor name, address, claim date, nature, amount, status flags
- **Simple creditor lists:** Name-and-address-only format from smaller filings or Subchapter V cases
- **Handwritten/scanned documents:** OCR processing with manual review queue for low-confidence extractions
- Automatic classification: company vs. individual creditors
- Deduplication: fuzzy matching to consolidate duplicate entries within a single filing

### 4. ZoomInfo Enrichment with Tier-Based Targeting

| Company Tier | Size Indicator | Target Roles |
|--------------|----------------|--------------|
| **Enterprise** | $1B+ revenue or 5,000+ employees | VP of Finance, Treasurer, Director of Credit, VP of Credit Risk |
| **Mid-Market** | $100M–$1B revenue or 500–5,000 employees | CFO, Controller, Director of Finance, Credit Manager |
| **SMB** | <$100M revenue or <500 employees | CFO, AP/AR Manager, Accounting Manager, Office Manager, Owner |

- Returns up to 3 ranked contacts per company
- Engagement likelihood scoring
- Fallback logic: tier 1 → tier 2 → tier 3 until match found

### 5. Salesforce Integration
- **Account creation/update:** Check for existing accounts by name/address, create new or update existing with bankruptcy event data
- **Territory routing:** Assign leads to reps based on creditor state using existing territory mapping
- **Do-not-contact suppression:** Check flags before outreach triggering
- **Active engagement detection:** Flag leads with open opportunities or recent activity (90 days) for manual review instead of auto-send
- **Bankruptcy event logging:** Debtor name, filing date, claim amount, case number, court district

### 6. Automated Outreach Triggering
- **Net-new qualified leads:** Trigger email sequences via ZoomInfo Engage/SalesLoft using configured templates
- **Flagged leads:** Alert assigned rep with context (active engagement, do-not-contact, repeat exposure)
- **T+1 timing:** Outreach triggered next business day from creditor extraction to avoid same-day sends

### 7. Historical Creditor Database
- Import Keith's existing 25K-row Excel dataset as seed data
- Track cumulative bankruptcy exposure: number of filings, total claim amounts, date range
- Enable differentiated outreach messaging referencing creditor history
- Repeat-exposure flagging: suppress auto-send for creditors with multiple recent bankruptcies, suggest alternate messaging

---

## Success Metrics

### Leading Indicators (Weeks 1–4)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Creditors extracted per day | **10x improvement** vs. manual baseline | Daily count comparison |
| Time-to-lead (top 20 creditors) | **<24 hours** from PACER filing | Timestamp delta: filing → Salesforce |
| Time-to-lead (Schedule F) | **<48 hours** from detection | Timestamp delta: Schedule F filing → Salesforce |
| ZoomInfo contact match rate | **80%+** | (Companies with ≥1 contact) / (Total companies) |
| Schedule F detection coverage | **Zero missed filings** | 100% of monitored cases detected |

### Lagging Indicators (Months 1–3)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Rep admin time reduction | **50%+** | Time tracking survey before/after |
| Email response rate | **Equal or better** vs. manual | Response % comparison over 90 days |
| Monthly lead volume | **5–10x** vs. pre-automation | Monthly lead count comparison |
| Pipeline contribution | **Measurable within 60 days** | Attribution tracking in Salesforce |
| PACER cost per qualified lead | **Establish baseline, optimize** | Total PACER spend / Qualified leads |

---

## Constraints and Requirements

### Technical Constraints

**PACER Integration**
- Document costs: $0.10/page, max $4.50/document
- Monthly budget ceiling requires human-in-the-loop purchase approval
- API rate limits and access restrictions apply

**ZoomInfo API**
- Rate limits on lookup volume (TBD: confirm API tier and throughput)
- Engagement likelihood scoring availability dependent on data quality
- Contact match rate limited by ZoomInfo database coverage

**Salesforce Integration**
- Must work with existing field structure and territory mapping
- Do-not-contact and active engagement detection depends on current data hygiene
- Custom objects or fields may need creation for bankruptcy event logging

### Scope Constraints

**In Scope (Phases 1–3)**
- PACER daily filing monitor and top 20 extraction
- Schedule F monitoring queue with human approval workflow
- Document parsing engine (structured, simple list, OCR formats)
- ZoomInfo enrichment with tier-based targeting (admin-configurable)
- Salesforce integration with territory routing and outreach triggering
- Historical database import (Keith's 25K-row dataset)
- Creditor exposure views and repeat-flagging logic

**Out of Scope (MVP)**
- Automated PACER document purchasing (human approval required)
- Claims agent portal scraping (Kroll, Epiq, Stretto) — Phase 4
- Multi-signal prospecting (job postings, press releases) — Phase 4
- AI-personalized outreach composition — Phase 4
- Full PACER historical backfill (2020–present) — Phase 4
- Bankruptcy payout/recovery tracking — Future consideration

### Data Quality Requirements

**Document Parsing Accuracy**
- 95%+ extraction accuracy on structured documents (Form 206E/F)
- 90%+ classification accuracy on company vs. individual creditors
- OCR low-confidence results flagged for manual review rather than auto-processed
- 90%+ page classification accuracy on multi-document filings

**Enrichment Quality**
- 80%+ successful company match rate in ZoomInfo
- 95%+ correct tier identification based on company size
- At least 1 contact returned for 80%+ of matched companies
- Fallback logic prevents creditors from being skipped due to strict title matching

**Integration Reliability**
- 95%+ correct account match/no-match determination in Salesforce
- Zero duplicate account creation for existing companies
- 100% correct territory assignment based on state mapping
- Do-not-contact and active engagement checks before every outreach trigger

### Processing Requirements

**Cadence**

| Process | Frequency | SLA |
|---------|-----------|-----|
| New filing detection | Daily | Results by 8:00 AM local time |
| Top 20 creditor extraction | Daily (per filing) | Within 24 hours of filing |
| Schedule F docket monitoring | Weekly per active case | Detection within 7 days of filing |
| ZoomInfo enrichment | On-demand (per batch) | Within 4 hours of extraction |
| Salesforce push | On-demand (per batch) | Immediately after enrichment |
| Outreach trigger | Next business day | T+1 from extraction |

### Risk Mitigation Requirements

**PACER Cost Control**
- Cost estimation provided before every purchase decision
- Geographic filtering to skip low-value filings (configurable)
- PACER favorites integration for simple approve/reject workflow
- Monthly spend tracking and alerts

**Data Quality Safeguards**
- Multi-format parsing with OCR fallback
- Company vs. individual classification with ambiguous case flagging
- ZoomInfo match verification before Salesforce push
- Manual review queue for edge cases

**Integration Safety**
- Do-not-contact flag validation before outreach
- Active engagement detection to prevent message conflicts
- Existing account detection to prevent duplicates
- Retry logic for API rate limits and transient failures

---

## Phased Build Plan

| Phase | Scope | Est. Duration |
|-------|-------|---------------|
| **Phase 1** | Daily pipeline: PACER → top 20 → ZoomInfo → Salesforce | 3–4 weeks |
| **Phase 2** | Schedule F monitoring queue + human-in-the-loop purchase approval | 2–3 weeks |
| **Phase 3** | Historical data import + repeat-exposure flagging | 2 weeks |
| **Phase 4** | Claims agent portals, multi-signal prospecting, AI outreach | Ongoing |

---

## Open Questions for Discovery

| # | Question | Owner | Impact |
|---|----------|-------|--------|
| **Q1** | What specific PACER alert configuration is used today? Email alerts by state, or PACER Case Locator RSS, or manual browsing? | Keith | Determines trigger mechanism for daily pipeline |
| **Q2** | What are the exact target states for the initial rollout? Full U.S. coverage or a subset? | Keith | Scope of daily monitoring and cost projections |
| **Q3** | What is the current Salesforce field structure for bankruptcy data? Does a custom object or field set already exist? | Keith | Salesforce integration design |
| **Q4** | What is the state-to-rep territory mapping? Does this already exist in Salesforce? | Keith | Lead routing logic |
| **Q5** | What is the existing do-not-contact tag/status field in Salesforce? Does it need to be created? | Keith | Outreach suppression logic |
| **Q6** | What is the ZoomInfo API access level and rate limits? Is there a separate API key for automated use? | Engineering | Enrichment throughput and cost |
| **Q7** | Does Keith want Chapter 7 filings in addition to Chapter 11? What about Chapter 11 Subchapter V (small business)? | Keith | Filing scope and volume |
| **Q8** | What is the budget ceiling for monthly PACER document costs? | Keith / Management | Purchase approval thresholds |
| **Q9** | Should government entities (IRS, state tax authorities) and major financial institutions (JP Morgan, Wells Fargo) be automatically excluded from the outreach pipeline? | Keith | Creditor filtering rules |
| **Q10** | What format is Keith's existing 25K-row historical Excel database? What columns does it contain? | Keith | Historical data import mapping |

---

## Next Steps

1. **Discovery Session** — Resolve open questions (Q1–Q10) with Keith
2. **Salesforce Audit** — Map existing fields, territory structure, do-not-contact logic
3. **PACER Configuration** — Confirm alert setup, target states, API credentials
4. **ZoomInfo API Access** — Validate API key, rate limits, contact hierarchy rules
5. **Historical Data Review** — Analyze 25K-row Excel format for import mapping
6. **Phase 1 Kickoff** — Begin daily pipeline build (PACER → ZoomInfo → Salesforce)

---

**Document Status:** Draft for Discovery Phase Review  
**Revision History:**  
- v1.0 (March 12, 2026) — Restructured project brief with standardized section format
