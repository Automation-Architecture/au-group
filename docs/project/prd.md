# Product Requirements Document
## Bankruptcy Creditor Intelligence Platform
### AI-Powered Lead Generation from Bankruptcy Filings

**Prepared for:** Keith Woods  
**Prepared by:** Automation Architecture  
**Date:** March 12, 2026  
**Version:** 2.0  
**Status:** Draft

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | March 12, 2026 | Automation Architecture | Initial draft |
| 2.0 | March 12, 2026 | Automation Architecture | Restructured with standardized PRD format |

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [User Personas](#2-user-personas)
3. [User Stories](#3-user-stories)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [User Flows](#6-user-flows)
7. [Acceptance Criteria](#7-acceptance-criteria)
8. [Edge Cases](#8-edge-cases)
9. [Milestones](#9-milestones)

---

## 1. Product Vision

### Vision Statement

Transform bankruptcy-driven lead generation from a manual, time-consuming process into an automated, scalable intelligence platform that captures opportunities competitors miss and enables highly differentiated outreach messaging through historical exposure data.

### Problem We're Solving

Sales teams targeting companies affected by bankruptcy filings currently face five critical bottlenecks:

1. **Missed opportunities** — Schedule F documents containing hundreds of mid-sized creditors drop 1-3 months post-filing and are frequently missed
2. **Manual data entry** — 4+ hours per day copying data from PDFs to ZoomInfo to Salesforce
3. **No historical context** — No centralized database to message prospects with their bankruptcy exposure history
4. **Competitive timing disadvantage** — By the time teams manually find Schedule F creditors, the window has closed
5. **PACER cost friction** — $0.10/page document costs require intelligent purchase decisions

### Our Solution

An AI-powered platform that:

- **Monitors PACER daily** for new Chapter 11 filings in target states, extracting top 20 creditors within 24 hours
- **Detects Schedule F publications** via active docket monitoring, alerting for purchase approval within 48 hours
- **Parses multi-format documents** (structured, simple lists, OCR for scanned) to extract all unsecured creditors
- **Enriches with ZoomInfo** using tier-based targeting rules to find the right decision-maker
- **Delivers to Salesforce** with territory routing, do-not-contact logic, and automated outreach triggering
- **Tracks historical exposure** across all filings to enable differentiated messaging

### Competitive Advantage

**Speed-to-contact on the long tail of creditors.** While competitors target only the top 20 creditors visible at filing time, we monitor dockets for the full Schedule F that drops months later, capturing hundreds of mid-sized creditors nobody else reaches. Combined with historical bankruptcy exposure data, sales teams can message prospects with:

> *"You've appeared as a creditor in 13 bankruptcies over the past five years."*

This creates a value proposition that cannot be replicated by competitors working from public top-20 lists alone.

### Business Impact

- Replaces ~$75K/year prospecting hire with 24/7 AI agent at roughly half the cost
- **10x improvement** in daily creditor lead extraction
- **50%+ reduction** in rep admin time
- **Zero missed opportunities** on Schedule F filings
- Scalable parallel processing capacity

### Success Definition

The product succeeds when:

1. 100% of daily filings in target states are processed within 24 hours
2. Zero Schedule F filings are missed in monitored cases
3. 80%+ of creditor companies are enriched with decision-maker contacts
4. Manual data entry is eliminated for standard-path leads
5. Sales teams consistently use historical exposure data in outreach messaging

---

## 2. User Personas

### Primary Persona: Keith Woods — U.S. Sales Lead

**Role & Responsibilities**
- U.S. Sales Lead managing bankruptcy-driven prospecting strategy
- Responsible for identifying creditors from bankruptcy filings and converting them to qualified leads
- Manages PACER account, ZoomInfo licenses, and Salesforce data quality
- Oversees territory reps (Mike, Frazier, et al.) and lead distribution

**Current Workflow**
1. Logs into PACER daily to check new bankruptcy filing alerts
2. Downloads court documents (Form 201 petitions, Form 204 top 20 lists)
3. Manually reads documents to find unsecured creditor lists
4. Searches ZoomInfo for each creditor company to find decision-maker contacts
5. Manually enters data into Salesforce (company, contacts, bankruptcy event details)
6. Triggers email outreach sequences through ZoomInfo Engage/SalesLoft
7. Occasionally checks dockets for Schedule F publications (but frequently misses them)

**Pain Points**
- Cannot keep up with filing volume — estimates only 30-40% of opportunities captured
- Spends 4+ hours per day on manual data entry instead of actual selling
- Schedule F documents (with hundreds of creditors) drop 1-3 months post-filing and are systematically missed
- No systematic way to monitor thousands of active dockets
- PACER document costs ($0.10/page) require careful purchase decisions but no intelligence to guide them
- Cannot leverage historical bankruptcy exposure in messaging because tracking is too time-consuming

**Goals & Motivations**
- Capture 100% of bankruptcy-driven opportunities in target states
- Reduce time spent on data entry from 4+ hours to near-zero
- Be first to contact Schedule F creditors (competitive timing advantage)
- Enable differentiated outreach messaging using historical exposure data
- Control PACER costs while maximizing opportunity capture

**Technical Proficiency**
- Comfortable with PACER interface, ZoomInfo, Salesforce
- Uses PACER favorites feature for bookmarking cases
- Can configure ZoomInfo Engage/SalesLoft email templates
- Prefers approval workflows over fully automated purchasing

**Quote**
> "We're leaving money on the table every day. The Schedule F is where the gold is, but by the time I find them manually, three other firms have already called."

---

### Secondary Persona: Territory Reps (Mike, Frazier, et al.)

**Role & Responsibilities**
- Regional sales representatives assigned to specific states
- Follow up on bankruptcy-related prospects provided by Keith
- Manage existing client relationships and close deals in their territories
- Report back to Keith on lead quality and conversion rates

**Current Workflow**
1. Receive manual lead lists from Keith (typically via email or Salesforce view)
2. Review lead details in Salesforce before making contact
3. Reference bankruptcy context (debtor name, filing date, claim amount) in outreach
4. Follow up on inbound responses from automated email sequences
5. Provide feedback to Keith on lead quality and territory coverage

**Pain Points**
- Leads arrive slowly and incompletely due to Keith's manual process
- Often lack full bankruptcy context when viewing leads in Salesforce
- Must manually research bankruptcy details when preparing for calls
- No visibility into historical bankruptcy exposure of prospects
- Receive leads outside their territory (filtering issues)

**Goals & Motivations**
- Receive daily filtered lead lists for assigned territories only
- Have full bankruptcy context visible in Salesforce at a glance
- Spend time selling, not researching bankruptcy filings
- Leverage historical exposure data in conversations to build credibility

**Technical Proficiency**
- Proficient with Salesforce (viewing leads, logging activities)
- Comfortable with email and basic CRM workflows
- Not directly interacting with PACER or ZoomInfo

**Quote**
> "I need to see the bankruptcy details right in Salesforce so I can reference them on calls. If I have to go hunting for context, I just skip it."

---

## 3. User Stories

### Keith Woods — U.S. Sales Lead

**US-1: Daily Filing Summary**  
**As** Keith,  
**I want** to receive a daily summary of new bankruptcy filings in my target states,  
**So that** I am aware of every relevant case without logging into PACER manually.

*Acceptance:* Summary delivered by 8:00 AM local time with debtor names, filing dates, estimated creditor counts, and links to extracted top 20 creditors.

*Note from Keith: This may not be needed if we are triggering emails automatically. I would want to be notified of names not emailed due to existing engagement.*

---

**US-2: Automatic Top 20 Extraction**  
**As** Keith,  
**I want** the system to automatically extract the top 20 unsecured creditors (Form 204) from each new filing,  
**So that** I have immediate leads on day one without manual document review.

*Acceptance:* All top 20 creditors extracted with name, address, and claim amount; available in Salesforce within 24 hours of PACER filing.

---

**US-3: Schedule F Monitoring Queue**  
**As** Keith,  
**I want** active cases placed into a monitoring queue that scans dockets for the full Schedule F,  
**So that** I am alerted the moment the complete creditor list becomes available.

*Acceptance:* All new Chapter 11 cases enter queue; weekly docket scans detect Schedule F within 7 days of actual filing date; alert includes case context and cost estimate.

---

**US-4: Purchase Approval Workflow**  
**As** Keith,  
**I want** to review flagged Schedule F documents and approve or reject them for purchase,  
**So that** I control PACER costs while ensuring I capture all high-value creditor lists.

*Acceptance:* Flagged documents show debtor name, estimated creditor count, page count, and PACER cost estimate; approval via PACER favorites (unfavorite = reject); zero manual data entry in approval workflow.

---

**US-5: Automated Document Parsing**  
**As** Keith,  
**I want** the system to parse approved Schedule F documents, extract all unsecured creditors, and store them in a structured format,  
**So that** no manual data entry is required.

*Acceptance:* Structured, simple list, and OCR formats supported; 95%+ extraction accuracy on structured documents; company vs. individual classification applied; duplicate creditors consolidated.

---

**US-6: ZoomInfo Enrichment with Targeting Rules**  
**As** Keith,  
**I want** each creditor company enriched with decision-maker contacts from ZoomInfo, using role-based targeting rules,  
**So that** I have the right person to contact (CFO for large companies, AP/AR for smaller ones).

*Acceptance:* Tier-based rules applied (Enterprise/Mid-Market/SMB); up to 3 contacts returned per company ranked by engagement likelihood; 80%+ match rate achieved.

*Note from Keith: I can provide a hierarchy of target contacts based on company size.*

---

**US-7: Automatic Salesforce Push**  
**As** Keith,  
**I want** enriched leads automatically pushed to Salesforce with the bankruptcy event details attached,  
**So that** our CRM is always current without manual input.

*Acceptance:* New accounts created or existing accounts updated; bankruptcy event fields populated (debtor name, filing date, claim amount, case number, court district); 95%+ correct match/no-match determination.

---

**US-8: Territory-Based Lead Routing**  
**As** Keith,  
**I want** leads routed to the correct rep based on creditor geography (state-based territory assignments),  
**So that** Mike, Frazier, and other reps only see leads in their territories.

*Acceptance:* State-to-rep mapping applied; 100% correct territory assignment; reps see only their assigned leads in Salesforce views.

*Note from Keith: When new accounts are added to Salesforce, they would be tagged to a specific rep based on geography. From there, the system would work the same for them as for me, with some automatic actions or notifications depending on the company's existing factors.*

---

**US-9: Smart Outreach Triggering**  
**As** Keith,  
**I want** automatic outreach emails sent via ZoomInfo Engage/SalesLoft for net-new companies with no existing Salesforce activity, and flagged-only (no auto-send) for companies with active engagements,  
**So that** we never disrupt ongoing conversations.

*Acceptance:* Do-not-contact flag checked; active engagement detection (open opportunities, recent activity within 90 days) applied; auto-send only for net-new qualified leads; flagged leads alert assigned rep with context; email triggered within 24 hours.

---

**US-10: Historical Bankruptcy Exposure**  
**As** Keith,  
**I want** to see a creditor's full bankruptcy exposure history (how many times they've appeared as a creditor, total dollar amounts, across all filings since 2020),  
**So that** I can craft a differentiated outreach message.

*Acceptance:* Historical database seeded with existing 25K-row dataset; creditor history visible on Salesforce account page; cumulative exposure calculated (number of filings, total claim amounts, date range); repeat-exposure flagging active.

*Note from Keith: This is already built into Salesforce, but not being fully utilized due to it being too time-consuming.*

---

### Territory Reps (Mike, Frazier, et al.)

**US-11: Filtered Lead Lists**  
**As** a territory rep,  
**I want** to receive a filtered daily lead list containing only creditors in my assigned states,  
**So that** I can focus on actionable leads without sorting through irrelevant data.

*Acceptance:* Territory-based Salesforce views configured; daily lead lists filtered by rep's assigned states; no out-of-territory leads visible to reps.

---

**US-12: Bankruptcy Context in Salesforce**  
**As** a territory rep,  
**I want** to see the bankruptcy context (debtor name, filing date, claim amount if available) alongside each lead in Salesforce,  
**So that** I can reference it in conversations without looking it up separately.

*Acceptance:* Bankruptcy event fields visible on account page; custom layout includes debtor name, filing date, court district, claim amount; data populated for 100% of bankruptcy-sourced leads.

---

## 4. Functional Requirements

### FR-1: PACER Filing Monitor

**FR-1.1: Daily Filing Polling**  
The system shall poll PACER daily for new Chapter 11 bankruptcy filings in configurable target states.

- State list is admin-configurable
- Polling runs overnight; results ready by 8:00 AM local time
- System retrieves all new filings from previous day

**FR-1.2: Voluntary Petition Parsing**  
The system shall parse the initial voluntary petition (Form 201) to extract debtor metadata.

- Debtor name
- Location (city, state, court district)
- Industry code
- Estimated assets and liabilities
- Estimated creditor count

**FR-1.3: Top 20 Creditor Extraction**  
The system shall extract the top 20 unsecured creditors from Form 204 (List of Creditors Holding 20 Largest Unsecured Claims).

- Creditor name
- Mailing address
- Claim amount (if available)
- Available within 24 hours of PACER filing

**FR-1.4: Creditor Classification**  
The system shall classify extracted creditors as company or individual based on name patterns, entity suffixes (LLC, Inc., Corp.), and address type.

- Company creditors proceed to ZoomInfo enrichment
- Individual creditors are stored but not enriched
- Ambiguous cases are flagged for manual review

---

### FR-2: Schedule F Monitoring Queue

**FR-2.1: Active Case Queue Management**  
The system shall add all new Chapter 11 cases to an active monitoring queue after initial filing is processed.

- Cases remain in queue until Schedule F is detected or case is dismissed/converted
- Queue status visible to Keith

**FR-2.2: Weekly Docket Scanning**  
The system shall scan dockets weekly for each active case looking for Schedule F publication keywords.

- Keywords: "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F"
- Detection within 7 days of actual filing date
- Continuous background scan

**FR-2.3: Schedule F Alert Generation**  
When Schedule F is detected, the system shall extract docket entry metadata and present it to Keith for purchase approval.

- Docket entry number
- Filing date
- Page count
- Estimated PACER cost
- Case context: debtor name, filing date, estimated creditor count

**FR-2.4: PACER Favorites Integration**  
The system shall integrate with PACER favorites feature for purchase approval workflow.

- System adds flagged dockets to Keith's PACER favorites
- Keith removes from favorites to reject purchase
- Remaining favorites are automatically purchased and processed
- Zero manual data entry in approval workflow

---

### FR-3: Document Parsing Engine

**FR-3.1: Structured Schedule E/F Parsing**  
The system shall parse structured Schedule E/F documents (Form 206E/F tabular format) to extract all unsecured creditors.

- Creditor name
- Mailing address
- Date debt was incurred
- Nature of claim
- Claim amount
- Contingent/unliquidated/disputed flags

**FR-3.2: Simple Creditor List Parsing**  
The system shall parse simple creditor lists (name and address only, no amounts or dates) from text-based attachments.

- All creditor names and addresses extracted
- Missing data fields marked as null
- Handles non-standard formatting

**FR-3.3: OCR for Scanned Documents**  
The system shall apply OCR to scanned/handwritten Schedule F documents and extract creditor data where possible.

- OCR attempts made on all scanned documents
- Low-confidence results flagged for manual review rather than auto-processed
- Handwritten filings from small cases flagged as low-priority

**FR-3.4: Page Classification**  
The system shall identify and extract only creditor list pages from multi-document filings.

- Handles 200+ page dockets with Schedule F buried in the middle
- Non-creditor pages excluded from parsing
- Extracts only relevant creditor data pages

**FR-3.5: Creditor Deduplication**  
The system shall deduplicate creditor entries within a single filing.

- Fuzzy matching on normalized company name and address (RapidFuzz `token_set_ratio`; default threshold 85%)
- Consolidates same company listed multiple times (Union-Find clustering)
- Total claim amounts summed for duplicates
- Audit: `raw_extraction.dedup_stats`, per-row `dedup_audit` and `source_line_numbers` (document-parser, before ZoomInfo / `merge_creditors`)

---

### FR-4: ZoomInfo Enrichment

**FR-4.1: Company Lookup**  
The system shall look up each creditor company in ZoomInfo using company name and address.

- Retrieve firmographic data: revenue, employee count, industry, headquarters location
- Return company match confidence score

**FR-4.2: Tier-Based Targeting Rule Application**  
The system shall apply tier-based targeting rules to select appropriate contact titles based on company size.

- **Tier 1 (Enterprise):** $1B+ revenue or 5,000+ employees → VP of Finance, Treasurer, Director of Credit, VP of Credit Risk
- **Tier 2 (Mid-Market):** $100M–$1B revenue or 500–5,000 employees → CFO, Controller, Director of Finance, Credit Manager
- **Tier 3 (SMB):** <$100M revenue or <500 employees → CFO, AP/AR Manager, Accounting Manager, Office Manager, Owner

**FR-4.3: Decision-Maker Contact Retrieval**  
For each creditor company, the system shall retrieve up to 3 decision-maker contacts ranked by ZoomInfo engagement likelihood score.

- Contacts match tier-based targeting rules
- Ranked by likelihood to respond
- At least 1 contact returned for 80%+ of matched companies

**FR-4.4: Targeting Rule Fallback Logic**  
If no contacts match the tier 1 targeting rule, the system shall fall back to tier 2, then tier 3.

- Prevents creditors from being skipped due to strict title matching
- Companies with no matches flagged as "no contact found"

**FR-4.5: Company Name Normalization**  
The system shall apply company name normalization using common trade names and business abbreviations.

- Example: International Business Systems Incorporated → IBM
- Uses ZoomInfo canonical names
- Applies common business abbreviations (Corp, Inc, LLC)

---

### FR-5: Salesforce Integration

**FR-5.1: Account Match/Create Logic**  
For each enriched creditor company, the system shall check if an account already exists in Salesforce by matching on company name and address.

- If account exists: update with new bankruptcy event
- If account does not exist: create new account
- No duplicate accounts created

**FR-5.2: Bankruptcy Event Logging**  
The system shall log bankruptcy event details on the Salesforce account.

- Debtor name
- Filing date
- Claim amount (if available)
- Case number
- Court district
- Filing type (Chapter 11, Subchapter V, etc.)

**FR-5.3: Territory Routing**  
The system shall route leads to territory reps based on creditor state using existing Salesforce territory mapping.

- State-to-rep assignment applied
- 100% correct territory assignment
- Rep field populated on account record

**FR-5.4: Do-Not-Contact Suppression**  
The system shall check do-not-contact flag/status on account before triggering outreach.

- If flagged: suppress outreach trigger and alert assigned rep
- No emails sent to do-not-contact accounts
- Rep receives flagged lead notification

**FR-5.5: Active Engagement Detection**  
The system shall check for active engagements on account (open opportunities, recent activity within 90 days).

- If present: suppress auto-send and flag for manual review
- No emails sent to accounts with active engagements
- Rep receives context for manual decision

**FR-5.6: Automated Outreach Triggering**  
For net-new accounts with no active engagement and no do-not-contact flag, the system shall trigger outreach email via ZoomInfo Engage/SalesLoft using configured template.

- Email triggered within 24 hours of lead creation
- Email sequence launched automatically
- T+1 timing (next business day) to avoid same-day sends

---

### FR-6: Historical Creditor Database (P1 — Nice-to-Have)

**FR-6.1: Historical Data Import**  
The system shall import Keith's existing ~25,000-row Excel database of historical creditor-bankruptcy records into Salesforce as the seed dataset.

*Note from Keith: I can likely do this outside of this project.*

**FR-6.2: Creditor Exposure Scoring**  
The system shall calculate and display a creditor's cumulative bankruptcy exposure on the Salesforce account page.

- Number of filings as a creditor
- Total claim amounts across all filings
- Date range of exposure
- Most recent filing date

*Note from Keith: This is already in place.*

**FR-6.3: Two-Tier Email Logic for Repeat Exposure**  
For repeat-exposure creditors (e.g., fourth bankruptcy in 18 months), the system shall suppress auto-send and flag with suggested alternate messaging.

- Detect repeat exposure threshold (configurable)
- Suppress auto-send for repeat creditors
- Flag with suggested messaging that references history

*Note from Keith: This is when we would flag them rather than auto-email them. We can craft a new message for multiple recent filings rather than sending the same template multiple times for each filing.*

**FR-6.4: Geographic Filtering on Schedule F Purchases**  
The system shall pre-screen debtor location and estimated creditor geography to recommend whether a Schedule F is worth purchasing.

- Low-value geography flagged (e.g., New Mexico mom-and-pop filings)
- Recommendations provided; final decision remains with Keith

---

### FR-7: Future Capabilities (P2 — Out of Scope for MVP)

The following functional requirements are **explicitly deferred** to Phase 4:

**FR-7.1: Claims Agent Portal Integration**  
Scrape Kroll, Epiq, Stretto, and Omni restructuring portals for large-case creditor lists not available through PACER alone.

**FR-7.2: Multi-Signal Prospecting Engine**  
Add parallel data feeds: job posting scraping (credit manager, AR specialist, doubtful account reserve mentions), press release monitoring, acquisition tracking, client buyer list cross-referencing.

**FR-7.3: AI-Generated Personalized Outreach**  
Replace static templates with AI-composed emails that reference specific bankruptcy events, exposure history, and company context.

**FR-7.4: Recovery/Payout Tracking**  
Track actual distributions to unsecured creditors through final court reports to enable ROI comparisons.

**FR-7.5: Full Historical PACER Backfill (2020–Present)**  
Systematic extraction of all Schedule F/E creditor data from 2020 through present.

**FR-7.6: Intelligent Signal Aggregation**  
AI agent that cross-references all signals and proactively recommends priority accounts.

---

## 5. Non-Functional Requirements

### NFR-1: Performance

**NFR-1.1: Processing Latency**
- **Daily filing detection:** Results ready by 8:00 AM local time
- **Top 20 creditor extraction:** Within 24 hours of PACER filing
- **Schedule F detection:** Within 7 days of actual filing date
- **ZoomInfo enrichment:** Within 4 hours of creditor extraction
- **Salesforce push:** Immediately after enrichment (within minutes)
- **Outreach trigger:** T+1 (next business day from creditor extraction)

**NFR-1.2: Throughput**
- Support processing of 50+ new bankruptcy filings per day
- Handle Schedule F documents with 500+ creditors each
- Process ZoomInfo lookups for 1,000+ companies per day
- Support concurrent processing of multiple filings

**NFR-1.3: System Responsiveness**
- PACER favorites synchronization: within 1 hour of Keith's action
- Alert generation: within 15 minutes of Schedule F detection
- Dashboard/reporting queries: <3 seconds response time

---

### NFR-2: Accuracy

**NFR-2.1: Data Extraction Accuracy**
- **Structured documents (Form 206E/F):** 95%+ extraction accuracy
- **Debtor metadata extraction:** 95%+ accuracy
- **Creditor classification (company vs. individual):** 90%+ accuracy
- **Page classification (multi-document filings):** 90%+ accuracy

**NFR-2.2: Data Matching Accuracy**
- **ZoomInfo company match:** 80%+ successful match rate
- **Salesforce account match/no-match determination:** 95%+ accuracy
- **Territory assignment:** 100% correct (based on state mapping)
- **Tier identification (company size):** 95%+ correct tier assignment

**NFR-2.3: Data Quality**
- Zero duplicate accounts created in Salesforce for existing companies
- Fuzzy matching consolidates duplicate creditors within a single filing
- Missing data fields explicitly marked as null (not left blank or guessed)

---

### NFR-3: Reliability

**NFR-3.1: Uptime**
- Daily polling and processing: 99%+ success rate
- Schedule F monitoring queue: continuous operation with weekly scans
- Alert delivery: 99%+ delivery rate

**NFR-3.2: Error Handling**
- API rate limits: retry logic with exponential backoff
- Transient failures: automatic retry (3 attempts)
- Persistent failures: flagged for manual review with detailed error context
- OCR low-confidence results: flagged instead of auto-processed
- Ambiguous creditor classification: flagged for manual review

**NFR-3.3: Data Integrity**
- No data loss on parsing failures (raw documents retained)
- Audit trail for all bankruptcy event creates/updates in Salesforce
- Historical data preserved on account updates (no overwriting)

---

### NFR-4: Scalability

**NFR-4.1: Volume Scalability**
- Support expansion from initial target states to full U.S. coverage
- Handle 10x increase in daily filing volume without architecture changes
- Support historical data import of 100K+ creditor records

**NFR-4.2: Processing Scalability**
- Parallel processing of multiple filings simultaneously
- Batch processing for ZoomInfo enrichment (configurable batch size)
- Queue-based architecture for Schedule F monitoring (scales horizontally)

---

### NFR-5: Security

**NFR-5.1: Credential Management**
- PACER credentials stored securely (encrypted at rest)
- ZoomInfo API keys rotated quarterly
- Salesforce OAuth tokens with appropriate scopes only

**NFR-5.2: Data Privacy**
- Do-not-contact flags respected 100% of the time
- No emails sent to suppressed accounts
- PII handling compliant with sales data best practices

**NFR-5.3: Access Control**
- Territory-based data access in Salesforce (reps see only their leads)
- Keith has admin access to all configurations and approval queues
- Audit logging for all system actions

---

### NFR-6: Usability

**NFR-6.1: Purchase Approval Workflow**
- Zero manual data entry in approval process
- PACER favorites as approval mechanism (familiar to Keith)
- Clear cost estimates and case context in alerts

**NFR-6.2: Salesforce User Experience**
- Bankruptcy context visible at a glance on account page
- Custom fields/layout configured for optimal viewing
- Territory-based views pre-configured for reps

**NFR-6.3: Alert Clarity**
- Schedule F alerts include all decision-relevant context
- Flagged lead notifications include reason for flagging
- Error notifications include actionable next steps

---

### NFR-7: Maintainability

**NFR-7.1: Configuration Management**
- Target states configurable via admin interface (no code changes)
- Tier-based targeting rules configurable and version-tracked
- Email templates managed in ZoomInfo Engage/SalesLoft (no hardcoding)

**NFR-7.2: Monitoring & Logging**
- Daily processing summary (filings processed, creditors extracted, errors)
- Alert on processing failures or degraded accuracy
- Audit trail for all PACER document purchases

**NFR-7.3: Documentation**
- System architecture documented
- API integration points documented
- Troubleshooting playbook for common failure modes

---

### NFR-8: Cost Efficiency

**NFR-8.1: PACER Cost Control**
- Human-in-the-loop approval required for all Schedule F purchases
- Cost estimates provided before purchase decision
- Monthly PACER spend tracking and reporting
- Geographic filtering recommendations to avoid low-value purchases

**NFR-8.2: API Cost Optimization**
- ZoomInfo API calls batched to minimize overhead
- Caching of company lookups for duplicate creditors across filings
- Rate limit awareness to avoid overage charges

---

### NFR-9: Compliance

**NFR-9.1: CAN-SPAM Compliance**
- Automated emails include unsubscribe mechanism
- Do-not-contact flags respected
- Company identification and physical address in email footer

**NFR-9.2: Data Retention**
- Raw PACER documents retained for audit purposes
- Salesforce data retained per company retention policy
- Historical bankruptcy event data retained indefinitely for exposure tracking

---

## 6. User Flows

### Flow 1: Daily Top 20 Creditor Processing (Happy Path)

**Trigger:** Daily PACER polling runs overnight

1. **System polls PACER** for new Chapter 11 filings in target states (overnight job)
2. **System downloads Form 201** (voluntary petition) for each new filing
3. **System parses debtor metadata** (name, location, industry, estimated assets/liabilities, creditor count)
4. **System downloads Form 204** (List of Creditors Holding 20 Largest Unsecured Claims)
5. **System extracts top 20 creditors** (name, address, claim amount)
6. **System classifies creditors** as company or individual (name patterns, entity suffixes)
7. **For each company creditor:**
   - System looks up company in ZoomInfo (firmographics)
   - System applies tier-based targeting rules (Enterprise/Mid-Market/SMB)
   - System retrieves up to 3 decision-maker contacts ranked by engagement likelihood
8. **System checks Salesforce** for existing account (match on company name + address)
9. **If account exists:**
   - System updates account with new bankruptcy event (debtor, filing date, claim amount, case number, district)
10. **If account does not exist:**
    - System creates new account with firmographics + bankruptcy event data
11. **System applies territory routing** (state-to-rep mapping)
12. **System checks do-not-contact flag**
13. **System checks for active engagement** (open opportunities, recent activity within 90 days)
14. **If net-new qualified lead (no DNC, no active engagement):**
    - System triggers outreach email via ZoomInfo Engage/SalesLoft (T+1 timing)
15. **If flagged (DNC or active engagement):**
    - System alerts assigned rep with context
16. **Keith reviews daily summary** (8:00 AM): debtor names, filing dates, creditor counts, extracted leads

**Result:** Top 20 creditors from new filings processed within 24 hours; enriched leads in Salesforce; automated outreach launched for qualified leads.

---

### Flow 2: Schedule F Detection and Purchase Approval

**Trigger:** Weekly docket scan runs for all active cases in monitoring queue

1. **System scans dockets** for all active Chapter 11 cases (weekly job)
2. **System searches for Schedule F keywords** ("Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F")
3. **When Schedule F is detected:**
   - System extracts docket entry number, filing date, page count
   - System estimates PACER cost ($0.10/page, max $4.50)
   - System retrieves case context (debtor name, original filing date, estimated creditor count)
4. **System generates alert** with all decision-relevant context
5. **System adds docket to Keith's PACER favorites**
6. **Keith reviews flagged dockets** in PACER favorites list
7. **Keith evaluates purchase decision** based on:
   - Estimated creditor count
   - Page count and cost estimate
   - Debtor location and industry
   - Geographic relevance (are creditors likely in target territories?)
8. **For documents Keith rejects:**
   - Keith removes from PACER favorites
   - Case remains in monitoring queue (no further action)
9. **For documents Keith approves:**
   - Keith leaves in PACER favorites (or explicitly marks approved)
10. **System detects approval** (sync with PACER favorites, 1-hour polling)
11. **System downloads approved Schedule F document** from PACER
12. **System parses document** (structured/simple list/OCR based on format)
13. **System extracts all unsecured creditors** (name, address, claim amount, etc.)
14. **System deduplicates creditors** within the filing (fuzzy matching)
15. **System classifies creditors** as company or individual
16. **For each company creditor:**
    - [Continue to Flow 1, step 7: ZoomInfo enrichment → Salesforce → outreach]

**Result:** Schedule F detected within 7 days; Keith approves/rejects with zero manual data entry; approved documents fully processed and enriched.

---

### Flow 3: Historical Exposure Flagging (Repeat Creditor)

**Trigger:** Enriched lead about to be pushed to Salesforce

1. **System checks Salesforce** for existing account (match on company name + address)
2. **Account exists** with historical bankruptcy event data
3. **System queries bankruptcy event history:**
   - Count of previous filings where company appeared as creditor
   - Total claim amounts across all filings
   - Date range of exposure (earliest to most recent)
4. **System calculates repeat exposure threshold:**
   - Example: 4+ filings in past 18 months
5. **If threshold exceeded:**
   - System flags account as "repeat-exposure creditor"
   - System suppresses auto-send for outreach email
   - System generates suggested alternate messaging: "Your company has been affected by [N] bankruptcies since [date], totaling $[amount] in claims."
   - System alerts assigned rep with context and suggested messaging
6. **If threshold not exceeded:**
   - System proceeds with standard outreach logic (Flow 1, steps 12-15)
7. **Rep reviews flagged lead:**
   - Rep decides whether to send alternate messaging or skip outreach
   - Rep manually triggers outreach if desired (with custom message)

**Result:** Repeat-exposure creditors flagged for differentiated messaging; no duplicate template sends; historical context leveraged in outreach.

---

### Flow 4: Territory Rep Daily Workflow

**Trigger:** Territory rep logs into Salesforce in the morning

1. **Rep navigates to "My Leads" view** (filtered by assigned territory)
2. **Rep sees daily lead list** (only creditors in assigned states)
3. **For each lead, rep views:**
   - Company name and firmographics
   - Decision-maker contacts (up to 3, ranked)
   - Bankruptcy context: debtor name, filing date, claim amount, case number, court district
   - Historical exposure data (if available): number of previous filings, total claims
4. **Rep reviews lead prioritization:**
   - Flagged leads (DNC, active engagement, repeat exposure) at top with alerts
   - Net-new leads with auto-sent emails below
5. **For flagged leads:**
   - Rep reads alert context (why flagged, suggested action)
   - Rep decides whether to reach out manually with custom messaging
6. **For net-new leads with auto-sent emails:**
   - Rep monitors for inbound responses
   - Rep follows up on replies per standard sales cadence
7. **Rep logs activity in Salesforce** (calls, meetings, outcomes)
8. **Rep provides feedback to Keith** (lead quality, conversion rates, territory coverage)

**Result:** Reps have filtered, actionable lead lists with full context; no time wasted on out-of-territory leads or research; differentiated messaging for repeat-exposure creditors.

---

## 7. Acceptance Criteria

### AC-1: PACER Filing Monitor

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-1.1 | System retrieves all new Chapter 11 filings from target states from previous day by 8:00 AM local time; state list is admin-configurable; zero missed filings in configured states |
| FR-1.2 | Debtor metadata correctly extracted from 95%+ of filings; fields include debtor name, location, industry code, estimated assets/liabilities, creditor count |
| FR-1.3 | All top 20 creditors extracted with name, address, and claim amount; available in Salesforce within 24 hours of PACER filing |
| FR-1.4 | 90%+ classification accuracy for company vs. individual creditors; ambiguous cases flagged for manual review (not skipped or guessed) |

---

### AC-2: Schedule F Monitoring Queue

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-2.1 | All new Chapter 11 cases enter monitoring queue after initial processing; cases remain in queue until Schedule F detected or case dismissed/converted; queue status visible to Keith |
| FR-2.2 | System detects Schedule F within 7 days of actual filing date; keywords: "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F"; continuous background scan runs weekly |
| FR-2.3 | Alert includes debtor name, filing date, estimated creditor count, document page count, PACER cost estimate; all decision-relevant context visible in single alert |
| FR-2.4 | Purchase approval workflow completes with zero manual data entry; PACER favorites used as approval mechanism (unfavorite = reject); remaining favorites auto-purchased |

---

### AC-3: Document Parsing Engine

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-3.1 | 95%+ extraction accuracy on structured Schedule E/F documents (Form 206E/F); fields extracted: name, address, claim date, nature, amount, contingent/unliquidated/disputed flags |
| FR-3.2 | All creditor names and addresses extracted from simple creditor lists; missing data fields marked as null (not blank or guessed); non-standard formatting handled |
| FR-3.3 | OCR attempts made on all scanned/handwritten documents; low-confidence results flagged for manual review (not auto-processed); handwritten filings from small cases flagged as low-priority |
| FR-3.4 | Page classification correctly identifies creditor pages in 90%+ of cases; non-creditor pages excluded from parsing; handles 200+ page dockets |
| FR-3.5 | Duplicate creditors consolidated using fuzzy matching on normalized company name and address (default threshold 85%); same company listed multiple times with variations is consolidated; total claim amounts summed; `dedup_stats`, per-row `dedup_audit`, and `source_line_numbers` persisted for deduplicated records |

---

### AC-4: ZoomInfo Enrichment

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-4.1 | 80%+ successful company match rate in ZoomInfo; firmographic data retrieved: revenue, employee count, industry, headquarters location; match confidence score returned |
| FR-4.2 | Correct tier identified for 95%+ of matched companies; Tier 1 (Enterprise): $1B+; Tier 2 (Mid-Market): $100M–$1B; Tier 3 (SMB): <$100M |
| FR-4.3 | At least 1 contact returned for 80%+ of matched companies; up to 3 contacts per company ranked by ZoomInfo engagement likelihood score; contacts match tier-based targeting rules |
| FR-4.4 | Fallback logic correctly applied (tier 1 → tier 2 → tier 3); no creditor skipped due to strict title matching; companies with no matches flagged as "no contact found" |
| FR-4.5 | Company names shortened using ZoomInfo canonical names and common abbreviations; example: International Business Systems Incorporated → IBM |

---

### AC-5: Salesforce Integration

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-5.1 | 95%+ correct match/no-match determination on company name + address; existing accounts updated (no duplicates created); new accounts created with all required fields |
| FR-5.2 | Bankruptcy event fields populated: debtor name, filing date, claim amount, case number, court district, filing type; data visible on account page; historical events preserved (not overwritten) |
| FR-5.3 | Correct rep assigned for 100% of leads based on state-to-rep territory mapping; rep field populated on account record; territory assignment logic auditable |
| FR-5.4 | No emails sent to do-not-contact accounts; rep receives flagged lead notification; DNC flag checked before every outreach trigger; 100% suppression rate |
| FR-5.5 | No emails sent to accounts with active engagements (open opportunities, recent activity within 90 days); rep receives context for manual decision; active engagement detection runs before every outreach trigger |
| FR-5.6 | Email triggered within 24 hours of lead creation for net-new qualified leads; email sequence launched automatically via ZoomInfo Engage/SalesLoft; T+1 timing (next business day) applied to avoid same-day sends |

---

### AC-6: Historical Creditor Database

| Requirement ID | Acceptance Criteria |
|----------------|---------------------|
| FR-6.2 | Creditor exposure visible on Salesforce account page; fields: number of filings, total claim amounts, date range, most recent filing date; cumulative calculation across all historical events |
| FR-6.3 | Repeat-exposure threshold detected (configurable, e.g., 4+ filings in 18 months); auto-send suppressed for repeat creditors; suggested alternate messaging generated referencing history; rep alerted with context |
| FR-6.4 | Low-value geography flagged (e.g., New Mexico mom-and-pop filings); recommendations provided in Schedule F alert; final decision remains with Keith (no auto-rejection) |

---

## 8. Edge Cases

### EC-1: Document Format Variations

**EC-1.1: Handwritten Schedule F on Scanned Form**  
**Scenario:** Small business files Chapter 11 with handwritten Schedule F submitted as scanned image.

**System Behavior:**
- OCR engine attempts extraction
- Low OCR confidence score triggers manual review flag
- Document added to manual review queue (not auto-processed)
- Keith receives alert: "Low-confidence OCR extraction — manual review recommended"
- Case remains in monitoring queue for potential amended filing

**Acceptance:** Low-confidence handwritten filings flagged for manual review; no incorrect data auto-processed into Salesforce.

---

**EC-1.2: Schedule F Split Across Multiple Docket Entries**  
**Scenario:** Large bankruptcy with 1,000+ creditors; Schedule F split into Part 1 (entries 1-500) and Part 2 (entries 501-1000) filed as separate docket entries.

**System Behavior:**
- System detects first docket entry with "Schedule F Part 1" keyword
- System flags case for multi-part filing review
- System scans next 5 docket entries for "Schedule F Part 2" (or similar)
- If found, system flags both parts for purchase approval together
- Keith approves/rejects as a bundle
- System downloads and parses both parts, consolidates creditor list

**Acceptance:** Multi-part Schedule F filings detected and bundled for purchase approval; no partial processing with missing creditors.

---

**EC-1.3: Amended Schedule F Filed After Initial Processing**  
**Scenario:** Debtor files Schedule F; system processes it; debtor files amended Schedule F 2 weeks later with corrected creditor list.

**System Behavior:**
- System detects amended Schedule F via docket monitoring (keywords: "Amended Schedule F", "Amended Schedule E/F")
- System flags case for re-processing
- Keith receives alert: "Amended Schedule F detected for [debtor name] — original processed on [date]"
- Keith approves/rejects amended document purchase
- If approved, system re-processes amended document and updates Salesforce (preserves original data in history)

**Acceptance:** Amended filings detected and flagged for re-processing; original bankruptcy event data preserved; updated data appended to account history.

---

### EC-2: ZoomInfo Enrichment Edge Cases

**EC-2.1: No ZoomInfo Match Found**  
**Scenario:** Creditor company not found in ZoomInfo database (small local business, outdated name, etc.).

**System Behavior:**
- ZoomInfo API returns no match or low-confidence match
- System flags company as "no contact found"
- System creates Salesforce account with company name and address from bankruptcy filing (no firmographics)
- Keith receives summary of no-match companies in daily report
- Rep sees lead in Salesforce with alert: "No ZoomInfo contacts found — manual research required"

**Acceptance:** No-match companies not skipped; basic account created in Salesforce; flagged for manual research; no incorrect firmographics applied.

---

**EC-2.2: Multiple ZoomInfo Matches for Same Company**  
**Scenario:** ZoomInfo returns multiple company matches (e.g., "ABC Corp" in Texas vs. "ABC Corp" in California).

**System Behavior:**
- System compares address from bankruptcy filing with ZoomInfo company headquarters locations
- System selects closest geographic match
- If no clear geographic match, system flags for manual review
- Keith reviews flagged matches and selects correct company
- System proceeds with enrichment using Keith's selection

**Acceptance:** Geographic matching logic selects correct company 90%+ of the time; ambiguous matches flagged for manual review; no incorrect company firmographics applied.

---

**EC-2.3: Tier Boundary Edge Case (Company Exactly at Threshold)**  
**Scenario:** Company has exactly $100M revenue (boundary between Tier 2 Mid-Market and Tier 3 SMB).

**System Behavior:**
- System applies inclusive boundary logic: $100M is Tier 2 (Mid-Market)
- System selects Tier 2 targeting rules (CFO, Controller, Director of Finance, Credit Manager)
- If Tier 2 contacts not found, fallback to Tier 3 (CFO, AP/AR Manager, Accounting Manager)

**Acceptance:** Boundary companies consistently assigned to higher tier (more conservative targeting); fallback logic prevents no-contact scenarios.

---

### EC-3: Salesforce Integration Edge Cases

**EC-3.1: Account Match on Company Name But Different Address**  
**Scenario:** Salesforce account exists for "XYZ Corporation" in New York; bankruptcy filing shows "XYZ Corporation" as creditor with Texas address (branch office or subsidiary).

**System Behavior:**
- System flags fuzzy match: same company name, different address
- Keith receives alert: "Potential account match — different address"
- Keith reviews and confirms: same company (branch office) vs. different company (coincidental name match)
- If same company: system updates existing account with new bankruptcy event
- If different company: system creates new account

**Acceptance:** Address mismatches flagged for manual review; no incorrect account merging; branch offices linked to parent accounts when confirmed.

---

**EC-3.2: Duplicate Creditor Across Multiple Bankruptcies (Same Month)**  
**Scenario:** Same creditor company appears in 3 different bankruptcy filings processed on the same day.

**System Behavior:**
- System processes Filing A: creates/updates Salesforce account, logs bankruptcy event A
- System processes Filing B: detects existing account, logs bankruptcy event B (appends to history)
- System processes Filing C: detects existing account, logs bankruptcy event C (appends to history)
- System calculates cumulative exposure: 3 filings, total claim amounts summed
- Outreach trigger evaluates repeat-exposure threshold: if 3 filings in 1 day exceeds threshold, flag for manual review

**Acceptance:** Multiple bankruptcy events logged on same account; no duplicate account creation; cumulative exposure calculated correctly; repeat-exposure logic triggers if threshold exceeded.

---

**EC-3.3: Do-Not-Contact Flag Added After Enrichment But Before Outreach**  
**Scenario:** Lead enriched and ready for outreach trigger; rep manually adds do-not-contact flag to account before outreach runs.

**System Behavior:**
- Outreach trigger job runs (T+1 timing)
- System checks do-not-contact flag immediately before sending email
- DNC flag detected (added since enrichment)
- System suppresses email send
- System logs: "Outreach suppressed — DNC flag detected at send time"
- Rep receives notification: "Lead flagged DNC after enrichment — no email sent"

**Acceptance:** DNC flag checked at send time (not only at enrichment time); no emails sent to accounts flagged between enrichment and outreach; rep notified of suppression.

---

### EC-4: PACER Cost Control Edge Cases

**EC-4.1: Schedule F Page Count Exceeds Cost Estimate**  
**Scenario:** System estimates Schedule F is 30 pages ($3.00); actual download is 42 pages ($4.20).

**System Behavior:**
- System downloads document based on Keith's approval (approved based on estimate)
- Actual cost exceeds estimate but remains under PACER $4.50 max per document
- System logs actual cost vs. estimated cost variance
- Keith receives monthly summary of cost variances
- If variances consistently high, system refines page count estimation logic

**Acceptance:** Document downloaded despite cost variance (Keith approved purchase); actual cost logged and reported; estimation logic improved over time based on variance tracking.

---

**EC-4.2: Keith Rejects Schedule F Purchase, Then Changes Mind**  
**Scenario:** Keith removes docket from PACER favorites (rejects purchase); later decides the case is valuable and wants to purchase.

**System Behavior:**
- Initial rejection: system removes case from purchase queue
- Keith manually re-adds docket to PACER favorites
- System detects re-addition during next sync (1-hour polling)
- System flags case for purchase with note: "Previously rejected, now approved"
- System proceeds with download and processing

**Acceptance:** Keith can reverse rejection decision by re-adding to favorites; system detects re-addition and processes accordingly; no duplicate purchase attempts.

---

### EC-5: Processing Failures and Retries

**EC-5.1: ZoomInfo API Rate Limit Exceeded**  
**Scenario:** Daily processing volume exceeds ZoomInfo API rate limit; enrichment requests start failing.

**System Behavior:**
- ZoomInfo API returns rate limit error (HTTP 429)
- System pauses enrichment queue for 15 minutes
- System retries failed requests with exponential backoff
- If rate limit persists, system batches remaining creditors for next day
- Keith receives alert: "ZoomInfo rate limit reached — [N] creditors queued for tomorrow"

**Acceptance:** Rate limit errors handled gracefully; no data loss; remaining creditors queued for next day; Keith notified of delay.

---

**EC-5.2: Salesforce API Downtime During Push**  
**Scenario:** Salesforce API unavailable during lead push (maintenance window or outage).

**System Behavior:**
- Salesforce API returns error (HTTP 503 Service Unavailable)
- System retries with exponential backoff (3 attempts over 30 minutes)
- If still unavailable, system queues leads for retry in 1 hour
- System continues processing other leads (does not block entire pipeline)
- Keith receives alert: "Salesforce API unavailable — [N] leads queued for retry"
- When Salesforce API restored, system automatically retries queued leads

**Acceptance:** Salesforce downtime does not block entire pipeline; leads queued for automatic retry; no data loss; Keith notified of delay and resolution.

---

**EC-5.3: PACER Document Download Fails (Network Timeout)**  
**Scenario:** Approved Schedule F document download times out due to network issue.

**System Behavior:**
- PACER document download times out after 2 minutes
- System retries download (3 attempts with exponential backoff)
- If all retries fail, system flags document for manual download
- Keith receives alert: "Document download failed for [debtor name] — manual download required"
- System keeps case in monitoring queue (does not mark as processed)

**Acceptance:** Network failures handled with retry logic; persistent failures flagged for manual intervention; case not marked as processed until successful download; Keith notified of failure.

---

## 9. Milestones

### Phase 1: Daily Pipeline Foundation (Weeks 1–4)

**Scope:** PACER monitoring, top 20 extraction, ZoomInfo enrichment, Salesforce push with territory routing

**Key Deliverables:**
- Daily PACER polling functional for configured target states
- Top 20 creditor extraction from Form 204 with 95%+ accuracy
- ZoomInfo enrichment with tier-based targeting rules operational
- Salesforce integration: account creation/update, territory routing, do-not-contact logic
- Automated outreach triggering via ZoomInfo Engage/SalesLoft
- Daily processing summary dashboard for Keith

**Success Criteria:**
- 100% of daily filings processed within 24 hours
- 80%+ ZoomInfo contact match rate
- Zero duplicate accounts created in Salesforce
- 100% correct territory assignment
- Net-new qualified leads receive automated outreach within 24 hours (T+1 timing)

**Dependencies:**
- PACER API access and credentials
- ZoomInfo API key and rate limits confirmed
- Salesforce field structure and territory mapping finalized
- Target states list finalized

**Exit Criteria:**
- Daily pipeline running in production for 1 week with no critical failures
- Keith approves data quality and processing accuracy
- Reps confirm leads are correctly filtered by territory

---

### Phase 2: Schedule F Monitoring Queue (Weeks 5–7)

**Scope:** Docket scanning, purchase approval flow, full creditor extraction from Schedule F documents

**Key Deliverables:**
- Active case monitoring queue operational
- Weekly docket scans detect Schedule F within 7 days of filing
- PACER favorites integration for purchase approval workflow
- Multi-format document parsing engine: structured, simple list, OCR
- Page classification for multi-document filings
- Creditor deduplication logic
- Schedule F alert generation with cost estimates

**Success Criteria:**
- Zero missed Schedule F filings in monitored cases
- 95%+ extraction accuracy on structured documents
- 90%+ page classification accuracy on multi-document filings
- Purchase approval workflow completes with zero manual data entry
- Keith receives alerts within 48 hours of Schedule F detection

**Dependencies:**
- Phase 1 complete and stable
- PACER favorites synchronization mechanism tested
- Monthly PACER budget ceiling confirmed

**Exit Criteria:**
- Schedule F monitoring queue running in production for 2 weeks
- At least 3 Schedule F documents successfully detected, approved, purchased, and processed
- Keith approves purchase approval workflow usability

---

### Phase 3: Historical Database and Repeat Exposure Flagging (Weeks 8–9)

**Scope:** Import existing Excel data, build creditor exposure views, enable two-tier email logic

**Key Deliverables:**
- Historical database import script (Keith's 25K-row Excel dataset)
- Creditor exposure scoring: number of filings, total claim amounts, date range
- Salesforce custom fields/layout for historical exposure visibility
- Repeat-exposure threshold detection (configurable)
- Two-tier email logic: suppress auto-send for repeat creditors, flag with suggested messaging
- Historical exposure visible on Salesforce account page

**Success Criteria:**
- 100% of historical data imported into Salesforce with no data loss
- Creditor history available on 80%+ of outreach targets
- Repeat-exposure threshold correctly identifies creditors above threshold
- Flagged repeat creditors receive suggested alternate messaging
- Reps confirm historical exposure data is useful and accurate

**Dependencies:**
- Phase 1 and 2 complete and stable
- Keith's Excel database format analyzed and import mapping finalized
- Repeat-exposure threshold defined (e.g., 4+ filings in 18 months)

**Exit Criteria:**
- Historical data import complete and validated
- Repeat-exposure flagging operational for 1 week
- At least 2 repeat-exposure creditors flagged with alternate messaging
- Keith and reps approve historical exposure views and usability

---

### Phase 4: Expanded Data Sources and Intelligence (Ongoing)

**Scope:** Claims agent portals, multi-signal prospecting, AI-personalized outreach, PACER backfill

**Key Capabilities (TBD — Scoped Separately):**
- Claims agent portal integration (Kroll, Epiq, Stretto) for large-case creditor lists
- Multi-signal prospecting engine: job posting scraping, press release monitoring, acquisition tracking
- AI-generated personalized outreach: custom emails referencing bankruptcy events and exposure history
- Full historical PACER backfill (2020–present): systematic extraction of all Schedule F/E data
- Intelligent signal aggregation: AI agent recommending priority accounts based on cross-referenced signals

**Trigger for Phase 4:**
- Phase 3 complete and running smoothly for 4+ weeks
- Keith requests expanded data sources or AI capabilities
- Business case demonstrated for additional investment

**Exit Criteria:**
- Phase 4 scope defined and approved by Keith
- ROI demonstrated on Phase 1-3 capabilities before proceeding

---

### Open Questions for Discovery (Pre-Phase 1)

The following questions must be resolved before Phase 1 kickoff:

| # | Question | Owner | Impact on Phase |
|---|----------|-------|-----------------|
| **Q1** | What specific PACER alert configuration does Keith use today? Email alerts by state, or PACER Case Locator RSS, or manual browsing? | Keith | Phase 1 — determines trigger mechanism for daily pipeline |
| **Q2** | What are the exact target states for the initial rollout? Full U.S. coverage or a subset? | Keith | Phase 1 — scope of daily monitoring and cost projections |
| **Q3** | What is the current Salesforce field structure for bankruptcy data? Does a custom object or field set already exist? | Keith | Phase 1 — Salesforce integration design |
| **Q4** | What is the state-to-rep territory mapping? Does this already exist in Salesforce? | Keith | Phase 1 — lead routing logic |
| **Q5** | What is the existing do-not-contact tag/status field in Salesforce? Does it need to be created? | Keith | Phase 1 — outreach suppression logic |
| **Q6** | What is the ZoomInfo API access level and rate limits? Is there a separate API key for automated use? | Engineering | Phase 1 — enrichment throughput and cost |
| **Q7** | Does Keith want Chapter 7 filings in addition to Chapter 11? What about Chapter 11 Subchapter V (small business)? | Keith | Phase 1 — filing scope and volume |
| **Q8** | What is the budget ceiling for monthly PACER document costs? | Keith / Management | Phase 2 — purchase approval thresholds |
| **Q9** | Should government entities (IRS, state tax authorities) and major financial institutions (JP Morgan, Wells Fargo) be automatically excluded from the outreach pipeline? | Keith | Phase 1 — creditor filtering rules |
| **Q10** | What format is Keith's existing 25K-row historical Excel database? What columns does it contain? | Keith | Phase 3 — historical data import mapping |

---

### Success Metrics by Milestone

| Phase | Leading Indicators (First 30 Days) | Lagging Indicators (Months 1–3) |
|-------|------------------------------------|---------------------------------|
| **Phase 1** | • 100% daily filing processing within 24hrs<br>• 80%+ ZoomInfo match rate<br>• Zero Salesforce duplicate accounts<br>• 100% correct territory assignment | • Time saved: 50%+ reduction in rep admin time<br>• Lead volume: 5–10x vs. manual baseline<br>• Email response rate: equal or better than manual |
| **Phase 2** | • Zero missed Schedule F filings<br>• 95%+ structured doc extraction accuracy<br>• <48hrs Schedule F detection to alert<br>• Zero manual data entry in approval workflow | • Schedule F creditor capture: 100% of monitored cases<br>• Competitive timing: first-to-contact on Schedule F creditors<br>• PACER cost per qualified lead: baseline established |
| **Phase 3** | • 100% historical data import accuracy<br>• 80%+ targets have creditor history available<br>• Repeat-exposure threshold correctly identifies flagged creditors | • Differentiated messaging adoption: reps consistently use historical exposure in outreach<br>• Conversion rate lift on repeat-exposure messaging (A/B test) |

---

**End of Document**
