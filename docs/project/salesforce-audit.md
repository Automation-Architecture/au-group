# Salesforce Audit — AU Group (Bankruptcy Creditor Intelligence)

**Date:** May 29, 2026
**Status:** Started — **design audit complete; live-org introspection blocked by a Salesforce login-IP/VPN lockout** (credentials exist; access tripped a network restriction).
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
4. 🔵 **Org context** — Salesforce **edition** (custom objects need Enterprise-class), **sandbox** availability for smoke tests, and **name conflicts** with any existing `Bankruptcy_Event__c`-like objects/fields or existing assignment rules.

---

## 4. Live-org confirmation checklist (run once KD-53 lands)

Once an integration user + OAuth creds exist (`/prod/salesforce/oauth`), introspect the org and confirm:

- [ ] Connected App + integration user has **API Enabled** + object CRUD
- [ ] `Bankruptcy_Event__c` and the MVP Account fields **exist or are created** (per §1, minus Phase-2 rows, plus §2 new fields)
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
