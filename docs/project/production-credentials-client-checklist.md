# Production credentials — client checklist (Salesforce & ZoomInfo)

**Project:** AU Group — Bankruptcy Creditor Intelligence  
**Jira Cloud project:** `KD` (logical backlog labels: `AU_GROUP-*`)  
**Tracking issue:** [KD-53 — Gather Production Credentials for Salesforce and ZoomInfo](https://automationarchitecture.atlassian.net/browse/KD-53) (assigned; **blocks** [KD-3](https://automationarchitecture.atlassian.net/browse/KD-3) ZoomInfo epic and [KD-4](https://automationarchitecture.atlassian.net/browse/KD-4) Salesforce epic; **relates to** [KD-1](https://automationarchitecture.atlassian.net/browse/KD-1) Foundation).  
**Purpose:** Trials are blocked (Salesforce: “Something went wrong”; ZoomInfo: sales-led). Use this checklist to gather **production** access from the client’s existing accounts before engineering stores secrets and wires Epics **AU_GROUP-4** (ZoomInfo) and **AU_GROUP-5** (Salesforce).

**Related backlog:** [jira-backlog.md](jira-backlog.md) — Epic AU_GROUP-4, Epic AU_GROUP-5, Story AU_GROUP-1.6  
**Secrets layout:** [final-tech-stack.md](../architecture/final-tech-stack.md) (AWS Secrets Manager paths)

---

## Why we need these platforms

| Platform | Role in the pipeline |
|----------|----------------------|
| **ZoomInfo** | Enrich creditor **companies** from filings with firmographics and **decision-maker contacts** (titles, email/phone, scores) so outreach targets real people, not names alone. |
| **Salesforce** | **CRM of record** for reps: create/update **Accounts**, log **Bankruptcy_Event__c** (and related) data, **territory routing**, exposure history, and (later) sequences via Engage/SalesLoft per backlog. |

---

## ZoomInfo — information to collect

**Credentials**

1. **Production API key** (or the auth mechanism your ZoomInfo contract provides for the Enrich/Data APIs you will use).

**Operational / contract**

2. **Rate limits** — requests per day/month (or credit pool), and any hard caps that would block batch enrichment.
3. **Capabilities confirmation** (must match [AU_GROUP-4](jira-backlog.md) scope):
   - Company lookup by **name + address** (or equivalent match fields).
   - **Contact retrieval** with **job title** filtering.
   - Access to **engagement / likelihood** scores (if part of your SKU).
   - **Batch** or bulk endpoints (if available and licensed).

**Integration**

4. **Base URL / environment** — default or custom API endpoint for your tenant.
5. **Per-company contact limits** — max contacts returned per company (product design assumes up to ~3 ranked contacts; confirm contract allows this).
6. **IP allowlisting** — whether ZoomInfo requires static egress IPs (document for DevOps / network).
7. **API documentation** — link or PDF for the **exact API version** licensed (auth header format, endpoints).

**Cost / policy**

8. **Pricing model** — per-call, credits, or bundle; monthly quota.
9. **Caching policy** — confirm **short-term caching** (e.g. 7-day Redis TTL per tech stack) is acceptable under contract.

---

## Salesforce — information to collect

**OAuth / API integration** (stored as JSON in Secrets Manager; see paths below.)

1. **Connected App — Client ID**  
2. **Connected App — Client Secret**  
3. **Refresh token** (OAuth refresh token for the integration user, with appropriate scopes)  
4. **Instance URL** — e.g. `https://your-domain.my.salesforce.com` (must match the org where data will land)

**Administrative / configuration** (client admin or partner)

5. **Permission to create or approve** backlog objects/fields:
   - Custom object **`Bankruptcy_Event__c`** and fields (see [AU_GROUP-5.1](jira-backlog.md)).
   - Custom **Account** fields for bankruptcy exposure / history (per backlog).
   - **Page layouts** for territory reps.
   - **Territory / visibility** — list views or sharing so reps see the right records.

6. **Territory mapping**
   - State → rep ownership (e.g. which states each rep owns).
   - Rep **Salesforce usernames** or **18-character user IDs** for routing automation.
   - Any **existing assignment rules** that could conflict with new Accounts or leads.

7. **API usage**
   - Integration user has **API Enabled** and object CRUD where needed.
   - Org **API request limits** (e.g. daily cap) and any **org-wide** API restrictions.

8. **Org context**
   - **Edition** (custom objects need Enterprise-class edition or equivalent).
   - **Sandbox** availability for smoke tests (recommended even if prod is primary).
   - Name conflicts: existing objects/fields similar to `Bankruptcy_Event__c`.
   - Current **Account** page layout (where new fields should live).

---

## Where credentials will be stored (after receipt)

| Secret path (AWS Secrets Manager) | Payload shape |
|-----------------------------------|----------------|
| `/prod/zoominfo/api-key` | `{"api_key": "..."}` |
| `/prod/salesforce/oauth` | `{"client_id": "...", "client_secret": "...", "refresh_token": "...", "instance_url": "..."}` |

Populate secrets under Story **AU_GROUP-1.6** ([jira-backlog.md](jira-backlog.md)). Application code must **never** embed these in repo or chat.

---

## Security — how to transmit

- **Do not** send secrets in email, Slack, or tickets as plain text.
- Prefer **encrypted channel**: 1Password (or similar) shared vault, **AWS Secrets Manager** console upload by client-side admin with least privilege, or **SFTP** / signed URL agreed with client security.
- Align with **90-day rotation** policy where possible ([AU_GROUP-1.6](jira-backlog.md)).
- Ensure **IAM** for the workload can call `secretsmanager:GetSecretValue` before pasting live secrets.

---

## Jira tracking (`KD`)

**Created:** [KD-53 — Gather Production Credentials for Salesforce and ZoomInfo](https://automationarchitecture.atlassian.net/browse/KD-53)  

- **Issue links:** KD-53 **blocks** [KD-3](https://automationarchitecture.atlassian.net/browse/KD-3) (ZoomInfo) and [KD-4](https://automationarchitecture.atlassian.net/browse/KD-4) (Salesforce); **relates to** [KD-1](https://automationarchitecture.atlassian.net/browse/KD-1) (Foundation).  
- Full description, acceptance criteria, and GitHub links to this checklist and backlog live on the issue.

---

## References

- [docs/project/jira-backlog.md](jira-backlog.md) — Epics AU_GROUP-4, AU_GROUP-5; Story AU_GROUP-1.6  
- [docs/architecture/final-tech-stack.md](../architecture/final-tech-stack.md) — Secrets Manager paths and integration stack  
