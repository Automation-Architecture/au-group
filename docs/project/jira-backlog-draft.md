# Jira Backlog Draft — Bankruptcy Creditor Intelligence Platform

**Project:** KD — Keith discovery
**Board:** https://automationarchitecture.atlassian.net/jira/software/projects/KD/boards/451
**Source:** [prd.md](prd.md)
**Card structure (mandatory on every Task):** User Story + Description + Acceptance Criteria

---

## Label scheme

Every Task carries up to three labels:
- **Phase:** `phase-1` | `phase-2` | `phase-3` | `phase-4-deferred`
- **FR ref:** `fr-1` | `fr-2` | ... | `fr-6` (skipped on cross-cutting tasks)
- **US ref:** `us-1` ... `us-12` (skipped where not applicable)

Every Epic carries the matching phase label plus `epic`.

---

## Epics

### E1 — Foundation & Salesforce Schema
- **Maps to PRD:** §FR-5 (schema bits), §3 US-12, §NFR-7.1 (configuration management)
- **Phase label:** `phase-1`
- **Scope:** Create Salesforce custom objects, fields, page layouts, territory mapping, DNC field, and admin-configurable target-states list. Unblocks every downstream integration Epic.
- **Child task count:** 6

### E2 — PACER Filing Monitor & Top 20 Extraction
- **Maps to PRD:** §FR-1 (FR-1.1..1.4), US-1, US-2
- **Phase label:** `phase-1`
- **Scope:** Daily polling of PACER for new Chapter 11 filings in target states; parse Form 201 (debtor metadata) and Form 204 (top 20 unsecured creditors); classify company vs individual; emit daily summary.
- **Child task count:** 5

### E3 — ZoomInfo Enrichment with Tier-Based Targeting
- **Maps to PRD:** §FR-4 (FR-4.1..4.5), US-6
- **Phase label:** `phase-1`
- **Scope:** ZoomInfo company lookup, tier classification (Enterprise/Mid-Market/SMB), decision-maker retrieval with fallback logic, company name normalization.
- **Child task count:** 5

### E4 — Salesforce Integration & Automated Outreach
- **Maps to PRD:** §FR-5 (FR-5.1..5.6), US-7, US-8, US-9, US-11
- **Phase label:** `phase-1`
- **Scope:** Account match/create, bankruptcy event logging, territory routing, do-not-contact suppression, active-engagement detection, outreach trigger via ZoomInfo Engage/SalesLoft at T+1, territory-filtered Salesforce views for reps.
- **Child task count:** 7

### E5 — Schedule F Monitoring Queue & Purchase Approval
- **Maps to PRD:** §FR-2 (FR-2.1..2.4), US-3, US-4
- **Phase label:** `phase-2`
- **Scope:** Active-case monitoring queue, weekly docket scanning for Schedule F keywords, Schedule F alert generation, PACER favorites approval workflow.
- **Child task count:** 4

### E6 — Multi-Format Document Parsing Engine
- **Maps to PRD:** §FR-3 (FR-3.1..3.5), US-5
- **Phase label:** `phase-2`
- **Scope:** Parse structured Schedule E/F (Form 206E/F), simple creditor lists, OCR for scanned/handwritten; page classification for multi-document filings; fuzzy-match deduplication within a filing.
- **Child task count:** 5

### E7 — Historical Creditor Database & Repeat-Exposure Flagging
- **Maps to PRD:** §FR-6 (FR-6.1..6.4), US-10
- **Phase label:** `phase-3`
- **Scope:** Import Keith's 25K-row historical dataset; creditor exposure scoring (number of filings, total claim amounts, date range); two-tier email logic suppressing auto-send for repeat creditors; geographic filtering recommendations on Schedule F purchases.
- **Child task count:** 4

### E8 — Observability, Reliability & Compliance
- **Maps to PRD:** §5 NFR cross-cutting (NFR-3, NFR-5, NFR-7, NFR-8, NFR-9), §4 FR-7 deferral
- **Phase label:** `phase-1` (foundational)
- **Scope:** Error handling + retry framework, audit trail, credential management, daily processing summary, PACER spend tracking, CAN-SPAM + data retention compliance, Phase-4 parking lot.
- **Child task count:** 7

**Totals:** 8 Epics, 43 Tasks.

---

## Tasks

### Under E1 — Foundation & Salesforce Schema

#### T1.1 — Create Salesforce custom objects for bankruptcy data
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `fr-5`
- **User Story**
  As Keith Woods, I want dedicated Salesforce custom objects for bankruptcy events and creditor records, so that bankruptcy data is structured, queryable, and reportable.
- **Description**
  Create `Bankruptcy_Event__c` (junction object linking Account to a filing) and `Creditor__c` (master record for a creditor entity). Define record types if needed for Chapter 11 vs Subchapter V. Confirm object names with Keith before deploying.
- **Dependencies:** Discovery answer to Q3 (existing field structure)
- **Acceptance Criteria**
  - [ ] `Bankruptcy_Event__c` custom object created in Salesforce sandbox
  - [ ] `Creditor__c` custom object created in Salesforce sandbox
  - [ ] Objects deployed to production after Keith approves schema
  - [ ] Object-level permissions granted to integration user and territory rep profiles

#### T1.2 — Configure bankruptcy event custom fields
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `fr-5`, `us-12`
- **User Story**
  As a territory rep, I want bankruptcy context (debtor name, filing date, claim amount, case number, court district) visible on the account page, so that I can reference it on calls without looking it up separately.
- **Description**
  Add fields to `Bankruptcy_Event__c`: Debtor Name (text), Filing Date (date), Claim Amount (currency), Case Number (text), Court District (picklist), Filing Type (picklist: Chapter 11 / Subchapter V / Chapter 7 if enabled), Source (picklist: Form 204 / Schedule F / Amended Schedule F), Contingent flag (checkbox), Unliquidated flag (checkbox), Disputed flag (checkbox).
- **Dependencies:** T1.1
- **Acceptance Criteria**
  - [ ] All required fields created with correct types
  - [ ] Picklist values match PRD §FR-3.1 fields and §FR-5.2 fields
  - [ ] Custom Lightning page layout includes all fields in a "Bankruptcy Context" section visible at a glance
  - [ ] FR-5.2 satisfied: 100% of bankruptcy-sourced leads have these fields populated

#### T1.3 — Configure state-to-rep territory mapping
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `fr-5`, `us-8`
- **User Story**
  As Keith Woods, I want leads routed to the correct rep based on creditor geography, so that Mike, Frazier, and other reps only see leads in their territories.
- **Description**
  Audit existing Salesforce territory configuration. If state-to-rep mapping exists, document it; if not, create a `Territory_Assignment__mdt` custom metadata table or a configured Apex map. Mapping must be admin-editable.
- **Dependencies:** Discovery answer to Q4 (state-to-rep mapping in Salesforce)
- **Acceptance Criteria**
  - [ ] State-to-rep mapping documented or created
  - [ ] 100% correct rep assignment verified across all 50 US states for test cases
  - [ ] Mapping editable by Keith without code changes (NFR-7.1)
  - [ ] Rep field populated on `Account` record on every creditor write

#### T1.4 — Configure Do-Not-Contact field/status
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `fr-5`
- **User Story**
  As Keith Woods, I want a clear Do-Not-Contact flag on Salesforce accounts, so that outreach automation can be reliably suppressed for sensitive accounts.
- **Description**
  Audit existing DNC field. If absent, add `Do_Not_Contact__c` (checkbox) and `Do_Not_Contact_Reason__c` (text) on `Account`. Wire field history tracking so the audit trail captures who set the flag and when.
- **Dependencies:** Discovery answer to Q5
- **Acceptance Criteria**
  - [ ] DNC field exists on Account with history tracking
  - [ ] FR-5.4 suppression logic can read this field via API
  - [ ] EC-3.3 supported: DNC flag checked at outreach send time, not only at enrichment time

#### T1.5 — Build Lightning page layout for bankruptcy context
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `us-12`, `us-11`
- **User Story**
  As a territory rep, I want a single Salesforce account view that surfaces bankruptcy events, decision-maker contacts, and historical exposure data, so that I can prepare for a call in under 60 seconds.
- **Description**
  Design and deploy a custom Lightning page for `Account` records flagged as bankruptcy-sourced. Include components: Bankruptcy Events related list, Contacts (top 3 from ZoomInfo) with engagement-likelihood rank, Historical Exposure summary (FR-6.2), and outreach status banner (DNC / active engagement / repeat exposure).
- **Dependencies:** T1.1, T1.2
- **Acceptance Criteria**
  - [ ] Custom Lightning page assigned to bankruptcy-sourced accounts
  - [ ] Bankruptcy context fields visible above the fold
  - [ ] Up to 3 contacts visible with rank
  - [ ] Historical exposure section renders when data exists, hides gracefully when not

#### T1.6 — Admin-configurable target states list
- **Issue type:** Task
- **Parent Epic:** E1
- **Labels:** `phase-1`, `fr-1`
- **User Story**
  As Keith Woods, I want to add or remove target states without code changes, so that I can expand coverage as the platform scales.
- **Description**
  Implement target-states configuration as either a Salesforce `Target_States__mdt` custom metadata table or a JSON/YAML config file managed by the backend. Default seed list resolved during discovery (Q2).
- **Dependencies:** Discovery answer to Q2 (initial target states)
- **Acceptance Criteria**
  - [ ] Target states configurable without redeploying code
  - [ ] PACER polling job (T2.1) reads from this config
  - [ ] State changes audit-logged (NFR-7.2)

---

### Under E2 — PACER Filing Monitor & Top 20 Extraction

#### T2.1 — FR-1.1 Daily PACER polling for Chapter 11 filings
- **Issue type:** Task
- **Parent Epic:** E2
- **Labels:** `phase-1`, `fr-1`, `us-1`
- **User Story**
  As Keith Woods, I want the system to poll PACER overnight and surface all new Chapter 11 filings in my target states by 8:00 AM, so that I never miss a filing.
- **Description**
  Build the Celery beat job that authenticates against PACER, queries new Chapter 11 (and optionally Subchapter V per Q7) filings in target states from the previous day, deduplicates against the case database, and queues each new case for downstream processing.
- **Dependencies:** T1.6, Discovery answers to Q1/Q2/Q7
- **Acceptance Criteria**
  - [ ] Job runs nightly and completes before 8:00 AM local time (NFR-1.1)
  - [ ] Zero missed filings in configured states verified for 7 consecutive days
  - [ ] FR-1.1 satisfied
  - [ ] EC-5.3 handled: transient network failures retry with exponential backoff (NFR-3.2)

#### T2.2 — FR-1.2 Voluntary petition (Form 201) parsing
- **Issue type:** Task
- **Parent Epic:** E2
- **Labels:** `phase-1`, `fr-1`
- **User Story**
  As Keith Woods, I want each new filing's Form 201 parsed automatically to extract debtor metadata, so that downstream enrichment has the full context.
- **Description**
  Parse Form 201 to extract: debtor name, location (city/state/court district), industry code, estimated assets, estimated liabilities, estimated creditor count. Use pdfplumber for structured fields; flag malformed petitions for manual review.
- **Dependencies:** T2.1
- **Acceptance Criteria**
  - [ ] All Form 201 fields per FR-1.2 extracted
  - [ ] 95%+ extraction accuracy on debtor metadata (NFR-2.1)
  - [ ] Malformed petitions flagged for manual review, not silently failed

#### T2.3 — FR-1.3 Top 20 creditor extraction from Form 204
- **Issue type:** Task
- **Parent Epic:** E2
- **Labels:** `phase-1`, `fr-1`, `us-2`
- **User Story**
  As Keith Woods, I want the system to automatically extract the top 20 unsecured creditors (Form 204) from each new filing, so that I have immediate leads on day one without manual document review.
- **Description**
  For every new case from T2.1, download Form 204, extract creditor name, mailing address, and claim amount. Output feeds T2.4 classification then T3.1 enrichment.
- **Dependencies:** T2.1
- **Acceptance Criteria**
  - [ ] All top 20 creditors extracted with name, address, claim amount
  - [ ] Records available in Salesforce within 24 hours of PACER filing (NFR-1.1)
  - [ ] Missing claim amount nulled, not guessed (NFR-2.3)
  - [ ] 95%+ extraction accuracy (NFR-2.1)

#### T2.4 — FR-1.4 Creditor classification (company vs individual)
- **Issue type:** Task
- **Parent Epic:** E2
- **Labels:** `phase-1`, `fr-1`
- **User Story**
  As Keith Woods, I want each extracted creditor classified as company or individual, so that only company creditors are sent for ZoomInfo enrichment and outreach.
- **Description**
  Classification logic uses entity-suffix rules (LLC, Inc., Corp., LP, Ltd.) plus name-pattern heuristics and address-type signals. spaCy entity recognition as a tiebreaker. Ambiguous cases flagged for manual review rather than auto-routed.
- **Dependencies:** T2.3
- **Acceptance Criteria**
  - [ ] 90%+ classification accuracy verified on labeled test set (NFR-2.1)
  - [ ] Company creditors flow to T3 enrichment
  - [ ] Individual creditors stored but not enriched
  - [ ] Ambiguous cases queued for manual review with reason recorded

#### T2.5 — US-1 Daily filing summary report
- **Issue type:** Task
- **Parent Epic:** E2
- **Labels:** `phase-1`, `us-1`
- **User Story**
  As Keith Woods, I want a daily summary of new filings and exception cases (per Keith's note, only names not auto-emailed due to existing engagement), so that I can intervene on the edge cases without reviewing every filing.
- **Description**
  Generate daily exception report listing: new filings detected, top-20 leads created, leads suppressed (DNC, active engagement, repeat exposure), enrichment failures, OCR low-confidence flags. Delivery channel TBD with Keith (email vs Salesforce dashboard).
- **Dependencies:** T2.1, T2.2, T2.3, T2.4, T4.4, T4.5
- **Acceptance Criteria**
  - [ ] Summary generated by 8:00 AM local time
  - [ ] Includes exception-only view per Keith's note on US-1
  - [ ] Delivered to Keith's chosen channel
  - [ ] Links to Salesforce records for fast triage

---

### Under E3 — ZoomInfo Enrichment with Tier-Based Targeting

#### T3.1 — FR-4.1 ZoomInfo company lookup
- **Issue type:** Task
- **Parent Epic:** E3
- **Labels:** `phase-1`, `fr-4`, `us-6`
- **User Story**
  As Keith Woods, I want each creditor company looked up in ZoomInfo using name and address, so that I get firmographic data needed for tier classification and contact selection.
- **Description**
  Call ZoomInfo company-match API with creditor name + address. Capture revenue, employee count, industry, headquarters. Persist match confidence score. Cache lookups by canonical name to avoid duplicate calls across filings (NFR-8.2).
- **Dependencies:** T2.4, Discovery answer to Q6 (ZoomInfo rate limits)
- **Acceptance Criteria**
  - [ ] 80%+ successful match rate (NFR-2.2)
  - [ ] Cache hit short-circuits redundant lookups
  - [ ] EC-2.1 handled: no-match companies flagged "no contact found", Salesforce account still created with bankruptcy data
  - [ ] EC-2.2 handled: multiple-match cases resolved via address proximity, ambiguous cases flagged
  - [ ] EC-5.1 handled: rate-limit (HTTP 429) errors trigger backoff and next-day batching

#### T3.2 — FR-4.2 Tier-based targeting rule engine
- **Issue type:** Task
- **Parent Epic:** E3
- **Labels:** `phase-1`, `fr-4`, `us-6`
- **User Story**
  As Keith Woods, I want a configurable tier-based targeting rule engine (Enterprise / Mid-Market / SMB) that picks decision-maker titles based on company size, so that I get the right contact for each creditor.
- **Description**
  Implement tier identification using revenue and employee thresholds per PRD §FR-4.2. Encode tier→title mappings as configurable rules (DB or YAML), not hardcoded constants. Inclusive boundary handling at threshold values (EC-2.3 — boundary = higher tier).
- **Dependencies:** T3.1
- **Acceptance Criteria**
  - [ ] Tier assignment matches PRD spec for Enterprise / Mid-Market / SMB
  - [ ] 95%+ correct tier identification on test set (NFR-2.2)
  - [ ] Boundary companies consistently assigned to higher tier (EC-2.3)
  - [ ] Rules editable without code changes (NFR-7.1)

#### T3.3 — FR-4.3 Decision-maker contact retrieval
- **Issue type:** Task
- **Parent Epic:** E3
- **Labels:** `phase-1`, `fr-4`, `us-6`
- **User Story**
  As Keith Woods, I want up to 3 decision-maker contacts per company ranked by ZoomInfo engagement likelihood, so that I can prioritize the most reachable contact.
- **Description**
  Query ZoomInfo contacts API filtered by titles from the tier rule. Return up to 3 contacts sorted by engagement-likelihood score. Persist contact details + rank on `Creditor__c` related records.
- **Dependencies:** T3.2
- **Acceptance Criteria**
  - [ ] At least 1 contact returned for 80%+ of matched companies (NFR-2.2)
  - [ ] Up to 3 contacts returned, ranked by score
  - [ ] Contacts match the tier's title rule

#### T3.4 — FR-4.4 Fallback tier logic
- **Issue type:** Task
- **Parent Epic:** E3
- **Labels:** `phase-1`, `fr-4`
- **User Story**
  As Keith Woods, I want the system to fall back from Tier 1 to Tier 2 to Tier 3 if no decision-maker contact matches at the primary tier, so that creditors are not skipped due to strict title matching.
- **Description**
  Implement cascading fallback: if Tier N yields zero contacts, retry at Tier N+1 using that tier's title set. Companies with zero contacts at any tier flagged as "no contact found" (folds into EC-2.1 handling).
- **Dependencies:** T3.3
- **Acceptance Criteria**
  - [ ] Tier 1 → Tier 2 → Tier 3 fallback verified
  - [ ] Zero creditors skipped due to strict title matching
  - [ ] "no contact found" flag set when all tiers exhausted

#### T3.5 — FR-4.5 Company name normalization
- **Issue type:** Task
- **Parent Epic:** E3
- **Labels:** `phase-1`, `fr-4`
- **User Story**
  As Keith Woods, I want full legal names normalized to canonical trade names (e.g., "International Business Systems Incorporated" → "IBM"), so that match rates improve and duplicates collapse.
- **Description**
  Normalize using ZoomInfo's canonical company names plus a configurable rule set for common business abbreviations (Corp, Inc, LLC, Ltd). Apply before lookup (T3.1) and before Salesforce account matching (T4.1).
- **Dependencies:** none
- **Acceptance Criteria**
  - [ ] Normalization rules editable without code changes (NFR-7.1)
  - [ ] Lookup match rate measurably higher than baseline pre-normalization
  - [ ] Same normalization used in both ZoomInfo lookup and Salesforce match path

---

### Under E4 — Salesforce Integration & Automated Outreach

#### T4.1 — FR-5.1 Account match/create logic
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-7`
- **User Story**
  As Keith Woods, I want each enriched creditor matched against existing Salesforce accounts and created only when no match exists, so that we never end up with duplicate accounts.
- **Description**
  Match on normalized company name + address. If match → update with new bankruptcy event. If no match → create new account with firmographics. EC-3.1 (same name different address): flag for manual review, do not auto-merge.
- **Dependencies:** T3.5, T1.1
- **Acceptance Criteria**
  - [ ] 95%+ correct match/no-match determination (NFR-2.2)
  - [ ] Zero duplicate accounts created on test corpus
  - [ ] EC-3.1 handled: address mismatches flagged for review
  - [ ] EC-3.2 handled: same creditor across multiple filings appends events to same account

#### T4.2 — FR-5.2 Bankruptcy event logging
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-7`
- **User Story**
  As Keith Woods, I want every bankruptcy event logged to Salesforce with full filing details, so that historical events are preserved and queryable.
- **Description**
  On every match/create, insert a `Bankruptcy_Event__c` child record with debtor name, filing date, claim amount, case number, court district, filing type, source (Form 204 / Schedule F / Amended). Historical events never overwritten.
- **Dependencies:** T4.1, T1.2
- **Acceptance Criteria**
  - [ ] All FR-5.2 fields populated for 100% of bankruptcy-sourced events
  - [ ] Historical events preserved on account updates (NFR-3.3)
  - [ ] Audit trail via Salesforce field history captures every write

#### T4.3 — FR-5.3 Territory routing on write
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-8`
- **User Story**
  As a territory rep, I want each new lead automatically assigned to the rep covering the creditor's state, so that I only work leads in my territory.
- **Description**
  On account create/update, look up the rep from T1.3 mapping using the creditor's state. Write rep to the Account `Owner` (or a custom `Territory_Rep__c` field if the owner field is reserved). Apply on every account write, not only on create.
- **Dependencies:** T4.1, T1.3
- **Acceptance Criteria**
  - [ ] 100% correct territory assignment based on state-to-rep mapping
  - [ ] Rep field populated on Account record
  - [ ] Logic auditable: every assignment includes the input state and matched rep

#### T4.4 — FR-5.4 Do-Not-Contact suppression
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-9`
- **User Story**
  As Keith Woods, I want outreach automatically suppressed for accounts with the DNC flag, so that we never email a do-not-contact account.
- **Description**
  Before any outreach trigger (T4.6), check `Do_Not_Contact__c` on the account. If set, suppress send and route a flagged-lead notification to the assigned rep with context. Re-check immediately before send (EC-3.3).
- **Dependencies:** T1.4, T4.6
- **Acceptance Criteria**
  - [ ] 100% suppression rate on DNC accounts
  - [ ] Rep receives flagged-lead notification with reason
  - [ ] EC-3.3 verified: DNC added between enrichment and send is honored
  - [ ] Compliance with NFR-5.2 and NFR-9.1 (CAN-SPAM)

#### T4.5 — FR-5.5 Active engagement detection
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-9`
- **User Story**
  As Keith Woods, I want outreach suppressed for accounts with open opportunities or activity in the last 90 days, so that we never disrupt an in-flight conversation.
- **Description**
  Query Salesforce for open `Opportunity` records and any `Task`/`Event`/email activity within 90 days. If any found, suppress auto-send and route flagged-lead notification with context.
- **Dependencies:** T4.1, T4.6
- **Acceptance Criteria**
  - [ ] No emails sent to accounts with active engagement
  - [ ] Rep receives the lead with active-engagement context
  - [ ] Detection runs before every outreach trigger, not just on create

#### T4.6 — FR-5.6 Automated outreach trigger (T+1)
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `fr-5`, `us-9`
- **User Story**
  As Keith Woods, I want net-new qualified leads to receive automated outreach via ZoomInfo Engage/SalesLoft on a T+1 cadence, so that we engage prospects fast without same-day overlaps.
- **Description**
  After T4.4 and T4.5 clear, enroll the contact in the configured Engage/SalesLoft sequence with T+1 scheduling (next business day). Email template name is configured externally, not hardcoded (NFR-7.1).
- **Dependencies:** T4.4, T4.5, Discovery on template selection
- **Acceptance Criteria**
  - [ ] Outreach launched within 24 hours of lead creation for qualified leads
  - [ ] T+1 timing applied (no same-day sends)
  - [ ] Template name configurable
  - [ ] EC-5.2 handled: Salesforce/Engage API outages queue retries without blocking pipeline

#### T4.7 — US-11 Territory-filtered Salesforce views
- **Issue type:** Task
- **Parent Epic:** E4
- **Labels:** `phase-1`, `us-11`
- **User Story**
  As a territory rep, I want a "My Bankruptcy Leads" Salesforce view filtered by my assigned states, so that I never see out-of-territory leads.
- **Description**
  Configure Salesforce list views and reports filtered by `Territory_Rep__c = $User`. Sort by filing date desc with flagged leads pinned to top. Provide both a list view and a Lightning report.
- **Dependencies:** T4.3
- **Acceptance Criteria**
  - [ ] Each rep sees only their territory's leads
  - [ ] Flagged leads (DNC, active engagement, repeat exposure) pinned to top
  - [ ] View accessible from rep's home page

---

### Under E5 — Schedule F Monitoring Queue & Purchase Approval

#### T5.1 — FR-2.1 Active case queue management
- **Issue type:** Task
- **Parent Epic:** E5
- **Labels:** `phase-2`, `fr-2`, `us-3`
- **User Story**
  As Keith Woods, I want every new Chapter 11 case placed in a Schedule F monitoring queue after initial processing, so that I never miss the Schedule F drop weeks or months later.
- **Description**
  After T2.x completes for a case, write the case ID + monitoring-start timestamp to the `monitoring_queue` table. Cases stay in the queue until Schedule F is detected, case is dismissed, or case is converted to another chapter. Queue status visible to Keith via dashboard or query.
- **Dependencies:** T2.1
- **Acceptance Criteria**
  - [ ] 100% of new Chapter 11 cases enter monitoring queue after initial processing
  - [ ] Cases exit queue only on Schedule F detection, dismissal, or conversion
  - [ ] Queue contents queryable by Keith

#### T5.2 — FR-2.2 Weekly docket scanning for Schedule F keywords
- **Issue type:** Task
- **Parent Epic:** E5
- **Labels:** `phase-2`, `fr-2`, `us-3`
- **User Story**
  As Keith Woods, I want a weekly job that scans the docket of every active case for Schedule F publication keywords, so that detection happens within 7 days of filing.
- **Description**
  Weekly Celery beat job iterates every case in the queue, fetches docket entries since last scan, regex-matches keywords: "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F". EC-1.2 multi-part: also flag "Schedule F Part 1/2" and scan next 5 entries for the companion. EC-1.3 amended: also flag "Amended Schedule F" / "Amended Schedule E/F".
- **Dependencies:** T5.1
- **Acceptance Criteria**
  - [ ] Detection within 7 days of actual filing date (NFR-1.1)
  - [ ] Zero missed Schedule F filings in test corpus
  - [ ] EC-1.2 multi-part bundling implemented
  - [ ] EC-1.3 amended detection implemented

#### T5.3 — FR-2.3 Schedule F alert generation
- **Issue type:** Task
- **Parent Epic:** E5
- **Labels:** `phase-2`, `fr-2`, `us-3`, `us-4`
- **User Story**
  As Keith Woods, I want every detected Schedule F to generate an alert containing the decision-relevant context (docket entry, filing date, page count, cost estimate, debtor name, estimated creditor count), so that I can decide whether to approve the purchase.
- **Description**
  On detection from T5.2, package alert with all FR-2.3 fields. Cost estimate computed from page count (handled in code; never display the dollar rate in the ticket per global rule, but show total estimate to Keith). Include geographic-filtering recommendation from FR-6.4 once Phase 3 is live.
- **Dependencies:** T5.2
- **Acceptance Criteria**
  - [ ] Alert includes all FR-2.3 fields
  - [ ] Alert delivered within 15 minutes of detection (NFR-1.3)
  - [ ] Alert generated within 48 hours of Schedule F filing (PRD success criteria)

#### T5.4 — FR-2.4 PACER favorites approval workflow
- **Issue type:** Task
- **Parent Epic:** E5
- **Labels:** `phase-2`, `fr-2`, `us-4`
- **User Story**
  As Keith Woods, I want flagged Schedule F documents added to my PACER favorites for approve/reject (unfavorite = reject), so that approval requires zero manual data entry.
- **Description**
  System adds flagged dockets to Keith's PACER favorites. Hourly sync (NFR-1.3) checks favorites list. Items remaining in favorites for >X hours = approved → trigger download. Items unfavorited = rejected → drop from queue but keep case under monitoring. EC-4.2 (Keith re-favorites after rejecting): system detects re-addition and re-queues for purchase.
- **Dependencies:** T5.3
- **Acceptance Criteria**
  - [ ] Approved documents auto-downloaded (input to E6)
  - [ ] Rejected documents drop without further action
  - [ ] EC-4.1 handled: actual vs estimated cost variance logged
  - [ ] EC-4.2 handled: re-favorite reverses prior rejection
  - [ ] EC-5.3 handled: download network failures retry then flag for manual download
  - [ ] Zero manual data entry across approve/reject path

---

### Under E6 — Multi-Format Document Parsing Engine

#### T6.1 — FR-3.1 Structured Schedule E/F parsing
- **Issue type:** Task
- **Parent Epic:** E6
- **Labels:** `phase-2`, `fr-3`, `us-5`
- **User Story**
  As Keith Woods, I want structured Schedule E/F documents (Form 206E/F tabular format) parsed automatically to extract every unsecured creditor, so that I never enter that data manually.
- **Description**
  Use pdfplumber tabular extraction to pull: creditor name, address, debt-incurred date, nature of claim, claim amount, contingent/unliquidated/disputed flags. Validate column alignment using header detection. Output to staging table for T6.5 dedup, then T2.4 classification, T3 enrichment.
- **Dependencies:** T5.4
- **Acceptance Criteria**
  - [ ] 95%+ extraction accuracy on structured documents (NFR-2.1)
  - [ ] All FR-3.1 fields extracted per row
  - [ ] Missing values nulled, not guessed (NFR-2.3)

#### T6.2 — FR-3.2 Simple creditor list parsing
- **Issue type:** Task
- **Parent Epic:** E6
- **Labels:** `phase-2`, `fr-3`, `us-5`
- **User Story**
  As Keith Woods, I want simple creditor lists (name and address only, no amounts or dates) parsed automatically, so that smaller filings and Subchapter V cases are not skipped.
- **Description**
  Detect simple-list format (no tabular structure) and apply line-based parsing to extract creditor name and address pairs. Mark amount, date, nature, flags as null.
- **Dependencies:** T5.4
- **Acceptance Criteria**
  - [ ] All creditor names and addresses extracted from simple lists
  - [ ] Missing fields null, not blank or guessed
  - [ ] Non-standard formatting handled (multi-line addresses, inconsistent spacing)

#### T6.3 — FR-3.3 OCR for scanned and handwritten documents
- **Issue type:** Task
- **Parent Epic:** E6
- **Labels:** `phase-2`, `fr-3`, `us-5`
- **User Story**
  As Keith Woods, I want OCR applied to scanned and handwritten Schedule F documents, with low-confidence results flagged for manual review rather than silently passed through, so that no bad data lands in Salesforce.
- **Description**
  Tesseract OCR with confidence scoring. If average confidence below threshold (configurable), the document is routed to manual review queue with the OCR output as a starting point. EC-1.1 handwritten-small-case: flagged as low-priority.
- **Dependencies:** T5.4
- **Acceptance Criteria**
  - [ ] OCR attempts made on every scanned/handwritten document
  - [ ] Low-confidence results flagged, never auto-processed (NFR-3.2)
  - [ ] EC-1.1 handled: handwritten small-case filings flagged as low-priority
  - [ ] Reviewer can edit OCR output and re-submit

#### T6.4 — FR-3.4 Page classification for multi-document filings
- **Issue type:** Task
- **Parent Epic:** E6
- **Labels:** `phase-2`, `fr-3`, `us-5`
- **User Story**
  As Keith Woods, I want page classification that identifies which pages contain creditor lists in a 200+ page docket, so that only relevant pages are parsed and noise is excluded.
- **Description**
  Train or rule-engineer a page classifier: header keywords ("Schedule E/F", "Creditors Holding"), table-structure detection, page-numbering heuristics. Output: page-range subset that gets parsed.
- **Dependencies:** T6.1, T6.2
- **Acceptance Criteria**
  - [ ] 90%+ page classification accuracy (NFR-2.1)
  - [ ] Handles 200+ page dockets with Schedule F buried mid-doc
  - [ ] Non-creditor pages excluded from parsing

#### T6.5 — FR-3.5 Creditor deduplication within a filing
- **Issue type:** Task
- **Parent Epic:** E6
- **Labels:** `phase-2`, `fr-3`, `us-5`
- **User Story**
  As Keith Woods, I want duplicate creditors within a single filing consolidated via fuzzy matching, so that one company listed multiple times becomes one record with summed claim amounts.
- **Description**
  Use RapidFuzz on normalized name + address. Consolidate matches above threshold; sum claim amounts; preserve source line numbers for audit. Run before the records hit Salesforce.
- **Dependencies:** T6.1, T6.2, T6.3
- **Acceptance Criteria**
  - [ ] Fuzzy matches consolidated within configurable threshold
  - [ ] Total claim amounts summed correctly
  - [ ] Source line numbers preserved for audit

---

### Under E7 — Historical Creditor Database & Repeat-Exposure Flagging

#### T7.1 — FR-6.1 Historical Excel data import
- **Issue type:** Task
- **Parent Epic:** E7
- **Labels:** `phase-3`, `fr-6`, `us-10`
- **User Story**
  As Keith Woods, I want my existing ~25K-row historical Excel database imported into Salesforce as the seed dataset, so that exposure calculations include pre-platform data.
- **Description**
  Build a one-shot ETL job: read Keith's Excel, map columns to `Bankruptcy_Event__c` + `Creditor__c`, normalize company names (T3.5), match-or-create accounts (T4.1), insert events. Per Keith's note, he may run this externally — coordinate before building.
- **Dependencies:** T4.1, T4.2, Discovery answer to Q10
- **Acceptance Criteria**
  - [ ] 100% rows imported or explicitly errored with reason
  - [ ] No duplicate accounts created during import
  - [ ] Import idempotent (re-runs do not duplicate events)
  - [ ] Source-of-truth column in event record identifies "historical-import" vs platform-generated

#### T7.2 — FR-6.2 Creditor exposure scoring
- **Issue type:** Task
- **Parent Epic:** E7
- **Labels:** `phase-3`, `fr-6`, `us-10`
- **User Story**
  As Keith Woods, I want each Salesforce account to show its cumulative bankruptcy exposure (number of filings, total claim amounts, date range, most recent filing), so that I can craft differentiated outreach.
- **Description**
  Per Keith's note, this is already built in Salesforce but underutilized. Audit the existing fields/rollups; rebuild only what's missing. Expose on Lightning page from T1.5.
- **Dependencies:** T4.2, T1.5
- **Acceptance Criteria**
  - [ ] Number of filings, total claim amounts, date range, most recent filing visible on Account
  - [ ] Cumulative calculation correct across all historical events
  - [ ] Available on 80%+ of outreach targets after import (PRD §9 Phase 3 success criteria)

#### T7.3 — FR-6.3 Two-tier email logic for repeat exposure
- **Issue type:** Task
- **Parent Epic:** E7
- **Labels:** `phase-3`, `fr-6`, `us-10`
- **User Story**
  As Keith Woods, I want auto-send suppressed for repeat-exposure creditors (e.g., 4+ filings in 18 months) and replaced with a flagged-lead notification carrying suggested alternate messaging, so that repeat targets never receive the same template multiple times.
- **Description**
  Threshold configurable. On every outreach trigger, evaluate the repeat-exposure rule. If exceeded, suppress send and generate a flagged-lead notification with suggested copy referencing N filings since date X totaling amount Y.
- **Dependencies:** T7.2, T4.6
- **Acceptance Criteria**
  - [ ] Threshold configurable without code changes
  - [ ] Auto-send suppressed for repeat creditors above threshold
  - [ ] Flagged-lead notification includes suggested messaging
  - [ ] Verified against historical dataset: at least 2 repeat creditors flagged correctly

#### T7.4 — FR-6.4 Geographic filtering on Schedule F purchases
- **Issue type:** Task
- **Parent Epic:** E7
- **Labels:** `phase-3`, `fr-6`
- **User Story**
  As Keith Woods, I want a recommendation on whether to purchase a Schedule F based on debtor location and estimated creditor geography, so that I avoid low-value purchases.
- **Description**
  Rules engine evaluates debtor state, industry, and estimated creditor count to recommend Buy / Skip / Keith Decides. Recommendation surfaced in T5.3 alert. Final decision always with Keith — never auto-rejects.
- **Dependencies:** T5.3
- **Acceptance Criteria**
  - [ ] Recommendation included in Schedule F alert
  - [ ] Recommendation rules editable without code changes (NFR-7.1)
  - [ ] No auto-rejection — Keith always decides

---

### Under E8 — Observability, Reliability & Compliance

#### T8.1 — NFR-3.2 Error handling and retry framework
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-3`
- **User Story**
  As Keith Woods, I want every external API call (PACER, ZoomInfo, Salesforce, SalesLoft) wrapped in retry logic with exponential backoff, so that transient failures never lose data.
- **Description**
  Standard Celery retry decorator + custom backoff for 429 / 503 / network timeouts. After 3 attempts, persistent failures land in a `failed_jobs` table with full error context and surface in T8.4 daily summary.
- **Dependencies:** none
- **Acceptance Criteria**
  - [ ] All external calls go through the retry wrapper
  - [ ] EC-5.1, EC-5.2, EC-5.3 handled
  - [ ] Failed jobs surfaced for manual review with actionable error context
  - [ ] Zero data loss on transient failures

#### T8.2 — NFR-3.3 Audit trail and raw document retention
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-3`
- **User Story**
  As Keith Woods, I want every PACER document and every Salesforce write preserved with full audit trail, so that we can reconstruct any decision.
- **Description**
  Raw PACER PDFs persisted to S3 with case ID + docket entry. Salesforce field history tracking enabled on key fields. Application-level audit log captures every bankruptcy-event create/update with actor and source.
- **Dependencies:** T1.1
- **Acceptance Criteria**
  - [ ] Raw documents retained per NFR-9.2 retention policy
  - [ ] Field history on `Bankruptcy_Event__c` and `Account` key fields
  - [ ] Application audit log queryable by case ID and date range

#### T8.3 — NFR-5 Credential management and access control
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-5`
- **User Story**
  As Keith Woods, I want all credentials (PACER, ZoomInfo, Salesforce, SalesLoft) stored encrypted in a single secrets store with rotation tracking, so that we meet basic security hygiene.
- **Description**
  AWS Secrets Manager for all credentials. ZoomInfo API key rotation tracked. Salesforce uses OAuth with least-privilege scopes. PACER credentials encrypted at rest. Territory-based Salesforce permissions enforced (reps only see their leads).
- **Dependencies:** none
- **Acceptance Criteria**
  - [ ] Credentials in Secrets Manager, none in code or env files
  - [ ] ZoomInfo key rotation tracked quarterly
  - [ ] Salesforce OAuth scopes documented and minimized
  - [ ] Rep-level data access verified: reps cannot see out-of-territory accounts

#### T8.4 — NFR-7.2 Daily processing summary and monitoring
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-7`
- **User Story**
  As Keith Woods, I want a daily processing summary (filings processed, creditors extracted, enrichment rate, errors, OCR low-confidence flags) plus alerts on degraded accuracy or failures, so that I can see system health at a glance.
- **Description**
  Persist daily metrics. Generate summary delivered alongside T2.5 daily report. Set thresholds for accuracy degradation (e.g., extraction accuracy <90%) and processing failures (e.g., >5% failed jobs) that trigger an alert.
- **Dependencies:** T8.1, T2.5
- **Acceptance Criteria**
  - [ ] Daily metrics persisted and reportable
  - [ ] Accuracy degradation triggers alert
  - [ ] Processing-failure rate above threshold triggers alert
  - [ ] All system actions audit-logged (NFR-5.3)

#### T8.5 — NFR-8.1 PACER spend tracking and reporting
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-8`
- **User Story**
  As Keith Woods, I want monthly PACER spend tracked and reported with per-document and per-lead cost breakdown, so that I can manage budget and refine purchase decisions.
- **Description**
  Log every PACER purchase with case ID, document, pages, and cost. Monthly summary tracks total spend, average per lead, variance vs estimate (EC-4.1). Alert when monthly spend exceeds configured ceiling.
- **Dependencies:** T5.4
- **Acceptance Criteria**
  - [ ] Every purchase logged with pages and cost
  - [ ] Monthly summary generated automatically
  - [ ] Estimated vs actual cost variance tracked (EC-4.1)
  - [ ] Spend-ceiling alert configurable

#### T8.6 — NFR-9 CAN-SPAM compliance and data retention
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-1`, `nfr-9`
- **User Story**
  As Keith Woods, I want every automated email to satisfy CAN-SPAM (unsubscribe link, physical address, sender identity) and historical bankruptcy data retained per policy, so that we remain compliant.
- **Description**
  Audit ZoomInfo Engage/SalesLoft templates for CAN-SPAM elements. Document data-retention policy for raw PACER documents, Salesforce data, and historical bankruptcy events. Confirm DNC respect 100% of the time (ties into T4.4).
- **Dependencies:** T4.6, T8.2
- **Acceptance Criteria**
  - [ ] Every template carries unsubscribe, physical address, sender identity
  - [ ] DNC respected 100% (ties to T4.4 acceptance)
  - [ ] Retention policy documented for raw PACER docs, Salesforce data, historical events

#### T8.7 — Phase 4 parking lot (FR-7.x deferred)
- **Issue type:** Task
- **Parent Epic:** E8
- **Labels:** `phase-4-deferred`
- **User Story**
  As Keith Woods, I want the Phase 4 capability set captured as a single placeholder so the deferral is visible on the board without polluting the active backlog.
- **Description**
  Tracks FR-7.1 Claims agent portals, FR-7.2 Multi-signal prospecting, FR-7.3 AI-personalized outreach, FR-7.4 Recovery/payout tracking, FR-7.5 Full PACER backfill, FR-7.6 Intelligent signal aggregation. Not in MVP scope.
- **Dependencies:** none
- **Acceptance Criteria**
  - [ ] Ticket parked, no work assigned
  - [ ] Triggered for scoping only after Phase 3 is stable for 4+ weeks (per PRD §9 Phase 4 trigger)
