# Salesforce Audit — AU Group (Bankruptcy Creditor Intelligence)

**Date:** May 29, 2026 (live-schema discovery + API introspection added June 12, 2026)
**Status:** **✅ ACCESS RESTORED 2026-06-12** — the client reset and shared the security token; API login + REST introspection now work. The live org's actual schema is fully mapped in **§1c** (confirmed API names — supersedes both the §1 designed schema and the §1b inferences). Remaining open items are client *decisions* (§3), not access.
**Scope basis:** the simplified MVP (Brief v2.0 / PRD v3.0). See the MVP Scope banner in [prd.md](prd.md).

This audit reconciles the **designed** Salesforce schema (built into the backlog + the SYS-04 Salesforce Push workflow) against the **re-scoped MVP**, and defines exactly what must be confirmed against the client's live org once access lands.

---

## 0. Access status

| | |
|---|---|
| Salesforce production credentials | ✅ username + password + **security token** (token added 2026-06-12) — all in 1Password |
| Current live access | ✅ **working** — SOAP `login()` with password+token succeeds; REST (limits, SOQL, describe) verified 2026-06-12 |
| Org | **Professional Edition, production** (org id `00D3h000003TLQcEAO`); 13,562 Accounts; ~101k daily API requests available |
| Auth model | username-password + security token (no Connected App / OAuth yet — acceptable for MVP via simple-salesforce; a Connected App + integration user remains the §4 hardening item) |
| `sf`/`sfdx` CLI on this machine | ❌ not installed/authed (not needed so far — REST direct works) |

**History:** access was blocked May 29 → June 12 by Salesforce's untrusted-IP policy (`LOGIN_MUST_USE_SECURITY_TOKEN`); resolved by the client resetting and sharing the security token. ⚠️ The login is the client's personal user — fine for MVP, but pushes will appear as him in record history, and a password change invalidates the token.

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
5. Exact API names, field types, required-ness, and the Creditor object's full field list go on the §4 checklist — introspect once the security token lands. *(Done — see §1c.)*

---

## 1c. ✅ CONFIRMED live schema — API introspection results (2026-06-12)

Access restored; full `describe` run against the production org. **This section is authoritative** — build `salesforce.py` (KD-68) against these names. Org: **Professional Edition, production** (no sandbox flag), 6 custom objects total (the other three — `Policy__c`, `Policy_Revenue__c`, `Puts__c` — are unrelated lines of business; don't touch).

### `Bankrupt_Companies__c` (label "Bankrupt Company") — 82 rows

| API name | Type | Notes |
|---|---|---|
| `Name` | Text(80) | debtor name — ⚠️ only 80 chars (truncation risk for long legal names) |
| `Address__c` | TextArea(255) | |
| `Chapter__c` | Picklist | `Chapter 7` / `Chapter 11` / `Chapter 15` — ⚠️ no `11-Subchapter-V` value (designed schema assumed one) |
| `File_Date__c` | Date | |
| `Claims_Admin__c` | Picklist | `Donlin` / `Epiq` / `KCC` / `Kroll` / `Omni` / `Pacer` / `Prime Clerk` / `Stretto` — **restricted set**; pipeline must map or skip unknown admins |
| `Schedule_F__c` | Picklist | `Available` / `Pending` |
| `Scrubbed__c` | Checkbox | manual — do not write |
| `Master_List__c` | Checkbox | manual — do not write |
| `Comments__c` | LongTextArea(32768) | manual — do not overwrite |

**No external-ID field, no case number / court district / PACER URL.** `Name` (80-char debtor name) is the only natural key → the §2 proposal to add `Case_Number__c` (external ID) + `Court_District__c` + `PACER_URL__c` stands, now targeted at this object.

### `Bankruptcy__c` (label "Bankruptcy") — the "Creditors" related list — 562 rows

| API name | Type | Notes |
|---|---|---|
| `Name` | Text(80) | |
| `Bankrupt_Company__c` | Lookup → `Bankrupt_Companies__c` | ⚠️ **not required** (orphan rows possible); child relationship name is `Bankrutpcies__r` — **misspelled in-org; use the typo in SOQL subqueries** |
| `Account__c` | Lookup → Account | **required** — the creditor company |
| `Amount__c` | Currency | the claim |
| `File_Date__c` | Date | denormalized |
| `Chapter__c` | Picklist | same 7/11/15 set |
| `Comments__c` | LongTextArea | manual |

No external-ID field here either → creditor-row upsert key must be composite (Account + Bankrupt Company) in code, or a new external-ID field.

### `Claim__c` — 5 rows — downstream claims workflow (Status: InProgress/Waiting on Info/Disputed/Rejected/Settled, settlement amount/date). Out of MVP scope; do not write.

### Account custom fields — what already exists vs. what's still missing

| Designed/proposed field | Live org reality |
|---|---|
| `ZoomInfo_URL__c` (proposed §2) | ✅ **already exists as `ZoomInfo__c` (URL)** — use it; §3.3 decision resolved, no new field |
| `Company_Tier__c` (proposed §2) | ❌ still missing — create (KD-10) |
| `Email_Template_Recommendation__c`, `Outreach_Status__c`, `Has_Recent_SF_Activity__c`, `Activity_Summary__c` | ❌ none exist — create the MVP subset (KD-10) or persist pipeline-side only (decision) |
| `Do_Not_Contact__c` | ❌ doesn't exist — confirm with client how they mark do-not-contact today |
| Phase-2 exposure fields | ✅ partially exist already: `Number_of_Bankruptcies__c` (Number), `Sum_of_Bankruptcies__c` (Currency), plus a string field confusingly named `Bankruptcy__c` **on Account** (same API name as the creditor-row object — beware in code) |
| Email merge variables (§3.1 / OD-4) | ✅ **likely answered: the `Engage_*` field family** — `Engage_Company_Name__c`, `Engage_Amount__c`, `Engage_Add_on__c`, `Engage_Signature__c` / `Engage_Signature_Address__c` / `Engage_Closing__c` (picklists with canned text). These look exactly like mail-merge inputs; confirm with the client that these drive his templates, then KD-68 populates them on push |
| Also present | `LinkedIn__c` (URL), `Trigger_Event__c` (multipicklist), `Former_Euler_Client__c`/`_Prospect__c`, `Current_AR_Solution__c`, `Carrier__c`, broker/partner fields |

### Build consequences (KD-68)

1. Push flow confirmed: upsert `Bankrupt_Companies__c` → upsert Account (creditor) → upsert `Bankruptcy__c` row (`Account__c` + `Bankrupt_Company__c` + `Amount__c`).
2. **No external IDs exist anywhere** → either add `Case_Number__c` (external ID) to `Bankrupt_Companies__c` (preferred, resolves OD-6) or implement query-then-insert/update in code.
3. **Professional Edition constraints:** API access works (verified), but PE has no custom profiles/permission-set granularity to create a least-privilege integration user, and record types/automation options are limited. Field creation is fine.
4. The recency flag (FR-5.5) can be computed from standard objects (Opportunity/Task/Event) as designed — and note `EmailMessage`/`Task`/`Event` child relationships exist on both custom objects.
5. Picklists are restricted sets — pipeline writes must map to exact existing values (`Chapter 11`, not `11`).

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

1. 🔵 **Email merge variables (FR-5.6b).** Which Account/standard fields do AU Group's email templates actually reference? We populate those on push. **2026-06-12: introspection strongly suggests the answer is the `Engage_*` Account field family (§1c)** — needs only a yes/no confirmation from the client now. — feeds KD-29 / new KD-5 field list.
2. 🔵 **"Recent activity" definition (FR-5.5).** Designed logic (from the backlog) = a relevant **Opportunity** on the account **OR** a Task/Event with `CreatedDate > NOW()-90d`. ⚠️ The backlog lists Opportunity stages `Open` / `Negotiation` / **`Closed-Won`** — note `Closed-Won` is *not* an "open" opp, so **confirm which stages actually count** (any non-Closed-Lost? only open? recently-won within N days?). Also confirm: which **objects** count (add `EmailMessage`? logged calls?), and whether a prior `Bankruptcy_Event__c` on the account also flips it to `custom` (KD-29 currently says yes). *Needs Keith.*
3. ✅ **Tier + ZoomInfo URL storage** — **half-resolved 2026-06-12 (§1c):** `ZoomInfo__c` (URL) already exists on Account — use it, create nothing. `Company_Tier__c` still needs creating (KD-10).
4. ✅ **Org context** — **answered 2026-06-12 (§1c):** **Professional Edition, production org** (`00D3h000003TLQcEAO`), API access verified working. No sandbox introspected — integration tests will hit production, so use clearly-marked test records + cleanup (or ask whether a sandbox exists). Conflicts: build against the existing `Bankrupt_Companies__c`/`Bankruptcy__c`; don't create `Bankruptcy_Event__c`. ⚠️ One naming trap: Account has a *string field* `Bankruptcy__c` with the same API name as the creditor-row *object*.

---

## 4. Live-org confirmation checklist (run once KD-53 lands)

Once an integration user + OAuth creds exist (`/prod/salesforce/oauth`), introspect the org and confirm:

- [ ] Connected App + integration user has **API Enabled** + object CRUD *(API verified working 2026-06-12 via the client user + security token; Connected App/integration user still outstanding as hardening)*
- [x] **Introspect the existing objects** — ✅ done 2026-06-12, results in §1c (`Bankrupt_Companies__c`, `Bankruptcy__c`, `Claim__c`; lookup relationship, no external IDs, relationship name `Bankrutpcies__r`)
- [ ] MVP Account fields **created**: `Company_Tier__c` + the KD-29/FR-5.5 status fields (decide in-org vs pipeline-only); add `Case_Number__c` (external ID) / `Court_District__c` / `PACER_URL__c` to `Bankrupt_Companies__c` (§1c consequence 2)
- [x] ZoomInfo-URL handling decided — ✅ existing `ZoomInfo__c` field (§1c); `Company_Tier__c` still to create
- [ ] Email-template merge variables confirmed with the client — candidate set found: the `Engage_*` family (§1c)
- [ ] Recent-activity object/stage rules confirmed (§3.2)
- [ ] Account **page layout** shows the MVP fields (status flag, tier, bankruptcy section)
- [x] Edition supports custom objects — ✅ Professional Edition, confirmed; **sandbox availability still unknown** (ask the client; otherwise test against production with marked records)
- [x] No conflicting existing objects — ✅ resolved by building against the existing schema (§1c); beware the Account field/object `Bankruptcy__c` name collision

**Credentials to collect** (from [production-credentials-client-checklist.md](production-credentials-client-checklist.md), secret path `/prod/salesforce/oauth`): Connected App **client_id**, **client_secret**, **refresh_token**, **instance_url** — never in repo/chat.

---

## 5. Next steps

1. ✅ ~~Restore Salesforce access~~ — **done 2026-06-12** (security token route; token in 1Password alongside the login).
2. ✅ ~~Introspect the org~~ — **done 2026-06-12** (§1c).
3. **Client confirmations needed (one short conversation):** (a) do the `Engage_*` fields drive his email templates? (§3.1); (b) recent-activity stage/object rules (§3.2); (c) OK to add `Case_Number__c` / `Court_District__c` / `PACER_URL__c` to `Bankrupt_Companies__c` and `Company_Tier__c` to Account? (d) does a sandbox exist, or do we test in production with marked records? (e) how is do-not-contact tracked today (no `Do_Not_Contact__c` field exists)?
4. **Create the agreed fields** (KD-10) — small, reversible metadata changes.
5. **Update KD-68** (summary/description/acceptance criteria) to the §1c schema and unblock the `salesforce.py` build.
