# Keith Woods — Discovery Checkpoint

- **Date:** 2026-05-21
- **Duration:** 56 min
- **Attendees:** Brad Wilcox (AAA), Keith Woods (AU Group)
- **Fireflies ID:** `01KS5DEHCPMNR6TWA5QQZ2D8SV`
- **Full transcript:** stored externally per repo convention (see `references/step-01-read-transcripts.md`). The raw transcript and Fireflies recording are not committed here.

## Purpose

Lock the open scope and access decisions before build begins. Driven from an HTML deck of the engineer's (Yanji's) open questions on credentials, target scope, match logic, and exclusions.

## Decisions

| Area | Decision |
|---|---|
| **Initial target states** | NY, NJ, PA, FL, MI (top 5 by current pipeline; expand after first 30 days) |
| **Claim-amount floor** | $10K minimum to qualify a creditor as a lead |
| **Contact selection** | Prioritize decision-makers; rank by company size |
| **Exclusion strategy** | Maintain a global suppression list (lenders + keyword-based filters); Keith to supply seed list |
| **Email outreach** | Templated, with localized regional signatures; Keith to share signature samples |

## Action items

**Keith Woods**
- Provide keyword + lender exclusion list to filter irrelevant leads from the feed
- Share email-signature samples with regional abbreviations
- Send Salesforce + ZoomInfo credentials (API keys if available) to enable integration
- Supply sample Salesforce export schema + fully-filled bankruptcy lead example
- Optional: screen recording of current manual bankruptcy data-processing workflow

**Brad Wilcox**
- Investigate ZoomInfo API availability + Salesforce integration capabilities (duplicate detection, enrichment)
- Build initial bankruptcy lead ingestion + enrichment pipeline against the schema Keith provides
- Develop a Salesforce dashboard for consolidated lead screening, prioritization, filtering
- Fine-tune email-sending logic after pipeline lands; coordinate with Keith on regional signature requirements
- Share integration architecture + data schema doc back to Keith
