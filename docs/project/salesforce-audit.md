# Salesforce Audit — AU Group (Bankruptcy Creditor Intelligence)

**Date:** May 29, 2026 (live-schema discovery added June 12, 2026)
**Status:** Started — **design audit complete; live-org introspection blocked by a Salesforce login-IP/VPN lockout** (credentials exist; access tripped a network restriction). **Update 2026-06-12:** API smoke test confirmed the blocker is a missing **security token** (`LOGIN_MUST_USE_SECURITY_TOKEN` — untrusted IP); Keith has been asked to reset/share it. Separately, client-provided artifacts revealed the org's **existing live schema** — see §1b, which supersedes parts of §1.
**Scope basis:** the simplified MVP (Brief v2.0 / PRD v3.0). See the MVP Scope banner in [prd.md](prd.md).

This audit reconciles the **designed** Salesforce schema (built into the backlog + the SYS-04 Salesforce Push workflow) against the **re-scoped MVP**, and defines exactly what must be confirmed against the client's live org once access lands.

---

## 0. Access status

| | |
|---|---|
| Salesforce production credentials | ✅ **exist** (login/Connected App access obtained) |
| Current live access | ⚠️ **locked out** — a login over **VPN** tripped Salesforce's login-IP / network-access restriction and the session was kicked |
| `sf`/`sfdx` CLI on this machine | ❌ not installed/authed (separate from the lockout) |
| Net blocker for the live audit | **Restore Salesforce access** (the IP/login restriction) — **not** missing credentials |

**Therefore:** the credentials half of KD-53 is effectively in hand; the live-org parts of this audit (🔵 items below) are blocked only by the **Salesforce IP/login restriction**, which is quick to resolve — see §5. Salesforce blocks logins from untrusted IPs; a VPN changes the apparent source IP, which triggers a security challenge or lockout.

---

## 1. Designed schema (current target)

### Custom object: `Bankruptcy_Event__c` (child of Account)
| Field | Type | Notes |
|---|---|---|
| `Account__c` | Lookup → Account | links the event to the **creditor** account |
| `Debtor_Name__c` | Text(255) | the **bankrupt company** |
| `Filing_Date__c` | Date | |
| `Claim_Amount__c` | Currency | the creditor's claim |
| `Case_Number__c` | Text(50), unique | |
| `Court_District__c` | Text(100) | |
| `Chapter_Type__c` | Picklist | `11` / `7` / `11-Subchapter-V` |
| `PACER_URL__c` | URL | |

### Account custom fields (designed)
| Field | Type | MVP? |
|---|---|---|
| `Email_Template_Recommendation__c` | Picklist `generic`/`custom` | ✅ MVP (KD-29 — the report status flag) |
| `Has_Recent_SF_Activity__c` | Checkbox | ✅ MVP |
| `Activity_Summary__c` | Text | ✅ MVP |
| `Outreach_Status__c` | Picklist (`ready_generic`/`review_custom`/`suppressed_dnc`) | ✅ MVP (status only; no auto-send) |
| `Do_Not_Contact__c` / `Do_Not_Contact_Reason__c` | Checkbox / Text | ✅ MVP (flag check, KD-28) |
| `Territory_Rep__c` (+ `OwnerId` routing) | Lookup/User | 🟡 Phase 2 (routing deferred) |
| `Bankruptcy_Exposure_Count__c` | Number | 🟡 Phase 2 (historical DB) |
| `Total_Claim_Amount__c` | Currency | 🟡 Phase 2 |
| `First_Bankruptcy_Date__c` / `Most_Recent_Bankruptcy_Date__c` | Date | 🟡 Phase 2 |
| `Repeat_Exposure_Flag__c` | Checkbox (≥4 in 18mo) | 🟡 Phase 2 |
| `Suggested_Messaging__c` | Text | 🟡 Phase 2 |

### Other
- `Creditor__c` custom object also referenced in the backlog (KD-1).
- Standard **Account** = the **creditor** company (name/address/BillingState used for matching + territory).

---

## 1b. ✅ Discovered live schema (2026-06-12) — the org already has the data model

On 2026-06-12 the client provided two artifacts from the **live org**: a record-page screenshot of an existing **"Bankrupt Company"** custom object, and a Salesforce report export of that object (82 rows, filings April 2022 → February 2025). Raw artifacts are preserved outside the repo at `client_projects/au-group/resources/salesforce-schema/` (client data — not committed).

**Key finding: the org is already debtor-centric.** One "Bankrupt Company" record per filing, with a **Creditors related list** linking creditor Accounts to the filing with a claim amount. This answers §3.4's conflict question — an equivalent of our designed `Bankruptcy_Event__c` already exists, shaped differently (parent record per debtor rather than child events per creditor account). **The pipeline should push into the existing objects, not create a parallel schema.** This is exactly the structure the PACER intake must capture per filing.

### Custom object: "Bankrupt Company" (API names unconfirmed until org access is restored)

| Field (label) | Type (inferred) | Observed values / notes |
|---|---|---|
| Bankrupt Company (Name) | Text | debtor legal name |
| Address | Text/compound | street + city/state/zip (e.g. Newark, NJ) |
| Chapter | Picklist | `Chapter 11` (78/82), `Chapter 7` (4/82) |
| File Date | Date | range seen 2022-04 → 2025-02 |
| Claims Admin | Picklist/Text | `Pacer`, `Stretto`, `Kroll`, `Omni`, `Donlin`, `KCC`, `Epiq`, `Prime Clerk`, blank (41/82) — which claims administrator hosts the case docs, or `Pacer` for direct PACER |
| Schedule F | Picklist | `Pending` (55) / `Available` (27) — whether the full creditor schedule is out yet |
| Scrubbed | Checkbox | manual workflow state (list cleaned) |
| Master List | Checkbox | manual workflow state (added to master list) |
| Comments | Long text | free-text recovery/payout notes |

### Related list: Creditors (likely the `Creditor__c` object KD-1 referenced — confirmed to exist)

| Field (label) | Type (inferred) | Notes |
|---|---|---|
| Account | Lookup → Account | the creditor company |
| Amount | Currency | the creditor's claim (e.g. $110,917) |
| File Date | Date | denormalized from the filing |
| Chapter | Picklist | denormalized from the filing |
| (parent link) | Master-detail/Lookup → Bankrupt Company | implied by the related list; confirm via API |

### Implications for the build

1. **KD-68 push targets the existing schema:** upsert Bankrupt Company (debtor) → upsert Account (creditor) → upsert Creditor row (Account + Amount + parent filing). Retire the plan to create `Bankruptcy_Event__c`.
2. **PACER capture set per filing** = debtor name, address, chapter, file date — plus case number, court district, and PACER URL, which the existing object does **not** have fields for. Propose adding those three (from the §1 designed schema) to Bankrupt Company so filings are unambiguously keyed (debtor name alone is not a reliable upsert key).
3. **Claims Admin** can be auto-populated where the pipeline knows it; **Scrubbed / Master List / Comments are Keith's manual workflow state** — the pipeline must not overwrite them.
4. The §2 re-scope fields (`Company_Tier__c`, `ZoomInfo_URL__c` on Account, KD-10) are unchanged by this discovery.
5. Exact API names, field types, required-ness, and the Creditor object's full field list go on the §4 checklist — introspect once the security token lands.

---

## 2. ⚠️ Schema gaps introduced by the MVP re-scope

The May-2026 re-scope added two things the original designed schema does **not** cover:

| Gap | Why | Proposed field |
|---|---|---|
| **Company tier** (Enterprise/MM/SMB) | FR-4.2 reframed — tier is now an MVP **account attribute** + a daily-report column | **NEW** `Company_Tier__c` (Picklist: Enterprise / Mid-Market / SMB) on Account |
| **ZoomInfo profile URL** | FR-4.1/FR-5.7 — the report's "ZoomInfo URL" column; useful on the account too | **NEW** `ZoomInfo_URL__c` (URL) on Account *(or store in pipeline DB only and join at report time — decision needed)* |

These should be added to the KD-4 / KD-5.1.2 field set (and to KD-21 / KD-19 acceptance) before the Salesforce build resumes.

---

## 3. Open decisions (needed to complete the MVP build)

1. 🔵 **Email merge variables (FR-5.6b).** Which Account/standard fields do AU Group's email templates actually reference? We populate those on push. *Needs Keith + the live template.* — feeds KD-29 / new KD-5 field list.
2. 🔵 **"Recent activity" definition (FR-5.5).** Designed logic (from the backlog) = a relevant **Opportunity** on the account **OR** a Task/Event with `CreatedDate > NOW()-90d`. ⚠️ The backlog lists Opportunity stages `Open` / `Negotiation` / **`Closed-Won`** — note `Closed-Won` is *not* an "open" opp, so **confirm which stages actually count** (any non-Closed-Lost? only open? recently-won within N days?). Also confirm: which **objects** count (add `EmailMessage`? logged calls?), and whether a prior `Bankruptcy_Event__c` on the account also flips it to `custom` (KD-29 currently says yes). *Needs Keith.*
3. 🔵 **Tier + ZoomInfo URL storage** (see §2) — create the two new Account fields, or keep ZoomInfo URL in the pipeline DB only.
4. 🔵 **Org context** — Salesforce **edition** (custom objects exist, so the edition supports them — ✅ answered 2026-06-12), **sandbox** availability for smoke tests, and ~~name conflicts with any existing `Bankruptcy_Event__c`-like objects~~ ✅ **answered 2026-06-12: a debtor-centric "Bankrupt Company" object + Creditors related list already exist (§1b) — build against them, don't create `Bankruptcy_Event__c`.**

---

## 4. Live-org confirmation checklist (run once KD-53 lands)

Once an integration user + OAuth creds exist (`/prod/salesforce/oauth`), introspect the org and confirm:

- [ ] Connected App + integration user has **API Enabled** + object CRUD
- [ ] **Introspect the existing "Bankrupt Company" + Creditor objects (§1b):** exact API names, field API names/types, required fields, upsert keys, and the Creditor→Bankrupt Company relationship type
- [ ] MVP Account fields **exist or are created** (per §1 Account rows, minus Phase-2, plus §2 new fields); add Case Number / Court District / PACER URL to Bankrupt Company (§1b implication 2)
- [ ] `Company_Tier__c` + ZoomInfo-URL handling created/decided (§2)
- [ ] Email-template merge variables enumerated and mapped (§3.1)
- [ ] Recent-activity object/stage rules confirmed (§3.2)
- [ ] Account **page layout** shows the MVP fields (status flag, tier, bankruptcy section)
- [ ] Edition supports custom objects; sandbox available for smoke tests
- [ ] No conflicting existing objects/fields/assignment rules

**Credentials to collect** (from [production-credentials-client-checklist.md](production-credentials-client-checklist.md), secret path `/prod/salesforce/oauth`): Connected App **client_id**, **client_secret**, **refresh_token**, **instance_url** — never in repo/chat.

---

## 5. Next steps

1. **Restore Salesforce access** (the live blocker — creds exist). Options, fastest first:
   - **Log in from a trusted IP** — disconnect the VPN (or use an exit node whose IP is already trusted) and log in from the IP the org expects.
   - **Append the security token** on API logins from a new IP (`password` + `securityToken`); reset the token if needed (Setup → reset security token).
   - **Admin relaxes / allowlists the IP** — add the IP (or range) to the integration user **profile's Login IP Ranges**, or to **Setup → Network Access (Trusted IP Ranges)**, so logins from it skip verification.
   - First determine whether it's a **user** lockout (a "verify your identity" email) or an **org IP policy** — the fix differs.
2. ✅ `Company_Tier__c` + `ZoomInfo_URL__c` added to the field set (KD-10).
3. Get Keith's answers to §3.1 (email merge variables) and §3.2 (recent-activity object/stage rules).
4. Once access is restored: run the §4 checklist against the org (or a sandbox), then re-test the **SYS-04 Salesforce Push** build (currently erroring — re-run now that creds are usable).
