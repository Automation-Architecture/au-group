# AU Group — PACER Data Source Re-Scope Discovery

> **✅ OD-8 RESOLVED (2026-06-14):** discovery now runs via the **CourtListener Search API** (`pipeline/discovery.py`, built + verified live — 60 real Chapter 11 cases discovered across njb+nysb in a 14-day window), using the same Free Law Project token as RECAP retrieval and **needing no standard PACER account**. This is the "automated discovery, no PACER" path (an upgrade of this doc's Option C discovery leg with CourtListener as the source). Form 204 retrieval is **RECAP-first** (`pipeline/retrieval.py`, PR #81). A standard-PACER **PCL** path is a deferred *authoritative* add — `intake.py` auto-selects PCL when PACER creds are configured, else CourtListener; the paid PACER CM/ECF Form-204 fallback also activates only with PACER creds. **Caveats:** CourtListener's `q=chapter:11` misses ~13% of brand-new filings that arrive chapter-blank (mitigation deferred); CourtListener is RSS-fed and same-day-ish but is not the authoritative PACER index. The analysis below stands as the rationale; the live REST rate limit is **5,000/hr** (an earlier "5/min" note was wrong), though bursts can 429 (handled by backoff).

**Prepared:** 2026-06-02
**Author:** Technical Business Analyst (discovery)
**Engagement stage:** Mid-build re-scope — OD-8 decision is dead, options analysis before any further intake build
**Decision this informs:** Which data source(s) the `intake.py` pipeline uses for (1) daily Chapter 11 discovery and (2) Form 204 retrieval — and what to ask Keith to unblock the build.
**Confidence level:** Medium-High on the *mechanics* (PACER fees, RECAP Fetch behaviour, ToS, court districts — all source-grounded below). Low on two business facts that only Keith can resolve: whether he has/will get a **standard** PACER account, and the actual Form 204 download flow against a live account.

**Supersedes:** OD-8 in [`n8n-to-code-native-migration.md`](./n8n-to-code-native-migration.md) (PACER Monitor API "Option A" is dead — confirmed unavailable to Keith).
**Related:** [`adr-001-rss-vs-pacer-intake.md`](./adr-001-rss-vs-pacer-intake.md), [`prd.md`](../project/prd.md) (MVP scope banner), `services/document-parser/pipeline/intake.py` (built `PacerClient`), [`courtlistener-recap-api-reference.md`](./courtlistener-recap-api-reference.md) (RECAP adapter contract).

---

## 2026-06-13 UPDATE — claims-agent free-scrape spiked and rejected; RECAP-first retrieval built

A later session explored the most economical retrieval idea — pulling Form 204s **free** from the court-appointed claims agents' public case sites (Kroll, Stretto, Epiq, Omni, …), routed by the "Claims Admin" field on the client's records. A go/no-go spike against **Kroll** (Bed Bath & Beyond case, driven through a real browser with network tracing) found:

- ✅ Document **discovery** is scriptable — Kroll exposes a clean JSON docket API (`Home-LoadDocketData`) with a description search filter.
- ⚠️ **Identifying** the actual Form 204 is messy — keyword search surfaces affidavits/orders that *reference* the list; large multi-debtor cases file a **consolidated top-30** via motion+order, not a standard B204.
- ❌ **The document download is reCAPTCHA-walled** — every programmatic fetch returned HTTP 405 and a real navigation triggered a Google reCAPTCHA challenge.

**Decision: claims-agent direct scraping is rejected as the retrieval source.** Building past reCAPTCHA across six bespoke agent SPAs is the same brittle-scraper / ToS-dubious trap this doc warns about for CM/ECF — just relocated. (The agent sites remain fine for *manual* human use, and the "Claims Admin" field is still a useful signal.)

**Pivot (chosen by the operator): RECAP-first retrieval.** The cheapest, cleanest legitimate free source is the **Free Law Project CourtListener/RECAP archive** — one official, documented JSON API; free reads for any already-archived document; no captcha. Built this session:

- `services/document-parser/pipeline/retrieval.py` — a pluggable, cheapest-first strategy: **`RecapRetriever`** (free archive) → **`PacerCmecfRetriever`** (existing paid CM/ECF fallback), behind a `CompositeRetriever`. `intake.py` now calls the strategy instead of the bare CM/ECF scrape. Settings gain `COURTLISTENER_API_TOKEN`.
- Full contract in [`courtlistener-recap-api-reference.md`](./courtlistener-recap-api-reference.md).

**Remaining unblock (cheap):** RecapRetriever is built against the documented contract and unit-tested, but is **not yet verified against the live API** — that needs a **free Free Law Project API token** (self-serve registration; no Keith dependency, no cost). Once the token lands: run the real coverage test (do RECAP holdings actually include the Form 204s for our target districts?), then RECAP misses fall through to a paid PACER pull — which still wants Keith's standard PACER account (Q1 below) as the authoritative floor. The economics from the cost model below stand: RECAP free reads + targeted PACER pulls for misses.

---

## Executive summary

- **The problem splits into two capabilities with very different profiles. Discovery is nearly solved; Form 204 retrieval is the hard, constrained part.** Every viable option collapses to the same retrieval truth: **getting the Form 204 PDF requires a standard PACER account.** No legitimate path avoids that.
- **OD-8 Option A (PACER Monitor API) is dead** — confirmed unavailable to Keith. The PacerMonitor REST API + Python SDK *do exist publicly* ([their own spec sheet](https://www.pacermonitor.com/static/images/PacerMonitor_RESTful_API.pdf)), but Keith could not obtain API access in this engagement, and that API *also* requires PACER credentials underneath. It is off the table.
- **The single biggest open question is whether Keith can get a standard PACER account** (separate from his PACER Monitor subscription). A "Case Search Only" account is **free to register, open to anyone (no attorney requirement)**, and grants the official Authentication + PCL APIs `intake.py` is already built against. Internal sources conflict on whether he has one — resolve this first; it forks the entire decision.
- **The recommended path is a pairing, not a single option:** **PCL REST API for discovery** (already built, cheap, officially sanctioned) **+ a standard-PACER-backed Form 204 fetch.** For retrieval, **RECAP Fetch (Free Law Project)** is the stronger default — it replaces the brittle, UNVERIFIED CM/ECF HTML scraper in `intake.py` with a maintained, openly-sanctioned API at the *same* PACER fees — **but it requires POSTing Keith's PACER username+password to a third party (FLP)**, which is a real tradeoff to put in front of the operator, not a footnote.
- **Legality is favourable for the recommended path, and this is the load-bearing finding.** PACER's ToS prohibits automated access to *fee-avoiding* endpoints to dodge billing — it does **not** prohibit authenticated, billed, official-API access. PACER itself publishes the Auth API + PCL API for developers. Scraping PACER Monitor, or scraping CM/ECF in a way that avoids billing, is the ToS-risky territory — the recommendation avoids both.
- **Operating cost is modest but not zero.** Discovery (PCL searches) is effectively free — it falls under PACER's **$30/quarter fee waiver** (75% of PACER users pay nothing). Real cost is document retrieval: **~$1.00–$3.50 per case** ($3-capped docket report + ~$0.30–0.50 for the Form 204 PDF). At the estimated covered-district volume (~2–4 new commercial Ch.11/business day) that's roughly **$40–$300/month**. SMB-tolerable, but state it plainly.
- **The make-or-break capability — the Form 204 download — is currently STUBBED and UNVERIFIED** (`intake.py` `download_form_204()` says so in its own docstring). Whichever retrieval path is chosen, the next concrete step is a **one-day spike against a live PACER account**, not "just swap the PacerClient class." Don't let the elegance of the existing intake code hide that the hard part is unbuilt.

---

## Problem framing

**Stated ask:** Replace the PACER data source now that PACER Monitor's API is confirmed unavailable (OD-8 dead).

**Underlying problem:** The MVP pipeline (PRD FR-1) must, every business day, (a) **detect** new Chapter 11 filings in the target states and (b) **obtain the Form 204 PDF** ("List of Creditors Who Have the 20 Largest Unsecured Claims") for each, so the downstream OCR → ZoomInfo → Salesforce → daily Slack report flow has something to chew on. Without a working data source, the entire pipeline has no input.

**Job-to-be-done:** "Each morning, give me the new bankrupt companies in my territory and their top-20 creditors, automatically, so my reps stop spending 4+ hours/day logging into PACER and copy-pasting." (PRD §Current Workflow — this is literally Keith's manual process today.)

**Why this matters now:** The pipeline scaffold (intake/parse/report) is built and merged; three Railway cron services are live. Intake is the **only** unblocked stage gated on an *external* decision rather than client access (ZoomInfo/SF are access-blocked separately). Resolving the data source unblocks the first end-to-end slice.

**The framing the task proposed — validated.** Splitting "discovery" from "Form 204 retrieval" is exactly right and is the spine of this analysis. They have different cost, legal, and feasibility profiles:

| Capability | Difficulty | Why |
|---|---|---|
| **Discovery** (detect new Ch.11 filings daily) | Easy / nearly solved | Multiple free or near-free, sanctioned sources (PCL API, court RSS, CourtListener). A discovery path already runs in n8n today (SYS-01 RSS/CourtListener per ADR-001). |
| **Form 204 retrieval** (download the actual PDF) | Hard / constrained | It's a paid, access-controlled federal court document. Every legitimate route requires a standard PACER account and incurs per-document fees. The crowdsourced free archives are too gappy to rely on. |

---

## Stakeholders

| Role | Who | Stake | Notes |
|---|---|---|---|
| Economic buyer / decision-maker | Keith Woods (AU Group) | Owns the PACER relationship, ZoomInfo licenses, SF data quality | **Holds the answer to the #1 open question.** PRD says he "manages PACER account" — but that may be the *Monitor* account; do not assume it means standard PACER. |
| End user | AU Group reps (Mike, Frazier, et al.) | Consume the daily creditor report | Not involved in the data-source decision; affected by reliability. |
| Builder / maintainer | AAA (Operator/engineer) | Builds + maintains `intake.py`; owns the brittleness risk if a scraper is chosen | Strong preference (per operator credential rules) against handing secrets to third parties — relevant to the RECAP Fetch credential tradeoff. |
| Data vendor (current) | Free Law Project (CourtListener/RECAP) | Would receive Keith's PACER creds if RECAP Fetch is chosen | Non-profit; mature, well-documented API. |
| Data vendor (rejected) | PacerMonitor / Fitch Solutions | API confirmed unavailable to Keith | Off the table for API; Keith retains the web subscription for manual use. |
| Missing voice | Whoever at AU Group is authorised to register/pay for a PACER account | Standard PACER registration needs a billing card and possibly a "Creditor / Commercial Business" user type | Confirm Keith can self-serve this or needs internal approval. |

---

## Internal context pulled

This is a mid-build engagement with extensive existing artifacts; I worked from the repo rather than re-deriving:

- **`intake.py` is built against official PCL REST (OD-8 "Option B").** The `PacerClient` class does auth (`/services/cso-auth` → `nextGenCSO` token), paginated case search (`/pcl-public-api/rest/cases/find`, `jurisdictionType:"bk"`, `federalBankruptcyChapter:["11"]`), then S3 upload + bankruptcy upsert + job enqueue. The architecture is sound and the discovery half is real.
- **The Form 204 download is explicitly UNVERIFIED.** `download_form_204()` and `_find_form_204_url()` do regex-on-docket-HTML scraping of CM/ECF with the PACER session cookie. The docstring says verbatim: *"UNVERIFIED — cannot validate without live PACER credentials against the production CM/ECF system."* **This is the stubbed make-or-break piece.**
- **District mapping is a partial subset** (`_STATE_TO_COURT_IDS`): NY = `nysb`,`nyeb` (2 of 4 — missing NDNY/WDNY); PA = `paeb`,`pawb` (2 of 3 — missing Middle/`pamb`); FL = all 3; MI = both; NJ = the single district. See open question Q3.
- **A known DB data bug** is already handled in code: Michigan Eastern stored as `maeb`, corrected to `mieb` at call time (`_correct_court_id`).
- **ADR-001 (Accepted, 2026-05-19)** established a **dual-source** intake: RSS/CourtListener for fast discovery + PACER poll for authoritative metadata. This discovery is consistent with ADR-001 — it refines the "PACER poll" leg (now PCL REST) and adds the retrieval-source decision ADR-001 didn't resolve.
- **PRD already flags "PACER cost friction — $0.10/page document costs require intelligent purchase decisions"** as a known bottleneck. The cost model below quantifies it.

**Gaps found:**
- **`docs/architecture/pacer-pcl-api-reference.md` does not exist** despite being cited repeatedly in `n8n-to-code-native-migration.md` and in the `intake.py` docstring. Documentation debt — note for cleanup; not blocking (the PCL API is documented by PACER directly, cited below).

---

## Key assumptions (and which ones matter)

1. **[CRITICAL] Keith does not currently have a standard PACER account, but can obtain one.** Internal sources conflict (CLAUDE.md: "Monitor, NOT standard PACER"; PRD: "manages PACER account"). *Validate:* ask Keith directly (Q1). *If wrong in the "he already has one" direction* → the recommended path is immediately buildable. *If wrong in the "he can't/won't get one" direction* → the only honest path is discovery + **manual** Form 204 (status quo retrieval), not a scraper.
2. **[CRITICAL] The Form 204 can actually be located + downloaded for these districts via the chosen retrieval path.** Currently UNVERIFIED for the CM/ECF-scrape path. *Validate:* one-day spike against a live PACER account (Q2). RECAP Fetch de-risks this (maintained API) but still needs a live-account smoke test.
3. **[Moderate] Covered-district commercial Ch.11 volume is ~2–4 new filings/business day.** Drives the cost estimate. Derived from national 2024 commercial Ch.11 = 7,879 across ~90 districts, with the target states' covered districts being moderate-volume (EDNY, MD/SD Florida, NJ, PA/MI districts) but excluding mega-venues (Delaware, SD Texas, CD California). *Validate:* run a 1-week PCL dry-run (intake.py already has `--dry-run`) to count real volume — costs ~$0 (search fees waived under $30/quarter).
4. **[Moderate] Locating the Form 204 requires first buying/viewing the docket report (~$3 capped) to get the document ID/link.** This is the dominant cost driver. *Validate:* the spike resolves whether the docket report is needed or the Form 204 is reachable more cheaply (some courts expose the petition package directly). RECAP Fetch's two-step (docket → PDF) implies the docket purchase is generally required.
5. **[Moderate] Voluntary Ch.11 Form 204 is available same-day as the petition.** Confirmed by FRBP Rule 1007(d) — it must be filed *with* the petition. *Edge case:* involuntary petitions and amended filings differ; a "filed within N days" case would break a strict same-day fetch. Low frequency; handle with a retry window.
6. **[Low] The official B204 lists 20 creditors; a "30 largest" form variant exists.** The official form title is "20 Largest"; one filing sample showed "30 Largest." Non-blocking — the parser handles a variable-length list either way.

---

## Technical feasibility notes (source-grounded)

### Discovery sources (the easy half)

| Source | Sanctioned? | Cost | Covers daily Ch.11 + state + date filter? | Notes |
|---|---|---|---|---|
| **PCL REST API** (`pcl.uscourts.gov`) | ✅ Official PACER developer API | **$0.10 per search-results page** (54 results/page), **counts toward the $30/quarter waiver** → effectively free at this volume | ✅ Yes — exactly what `intake.py` does (`jurisdictionType:"bk"`, chapter 11, courtId list, dateFiledFrom/To) | Index/case-locator **only** — returns case metadata, **not documents**. Immediate search ≤5,400 results; batch ≤108,000. [PCL API doc](https://pacer.uscourts.gov/sites/default/files/files/PCL-API-Document_3.pdf), [Developer Resources](https://pacer.uscourts.gov/file-case/developer-resources) |
| **Court RSS feeds** (per-court CM/ECF RSS) | ✅ Free public feeds | Free | Partial — RSS lists recent filings but filtering/coverage varies by court; not all courts publish Ch.11-filterable feeds | Good as a *redundant* near-real-time trigger (ADR-001's RSS leg). Not authoritative alone. |
| **CourtListener Search API / RECAP Alerts** | ✅ Sanctioned (FLP) | Free tier (5 daily alerts); paid tiers $10–$100/mo for more/real-time alerts | ✅ Boolean search + jurisdiction + date filters; "RECAP Search Alerts" = Google-Alerts-for-PACER | [LawSites 2025](https://www.lawnext.com/2025/06/courtlistener-launches-recap-search-alerts-for-pacer-filings-google-alerts-for-federal-courts.html). Relies on community-contributed data for *content*, but alerts on new dockets are useful for discovery. |

**Verdict on discovery:** Solved. **PCL REST (already built) is the primary**, cheap, sanctioned, and satisfies the FR-1.1 24-hour SLA. RSS/CourtListener can layer in as redundancy. No change needed here beyond completing district coverage (Q3).

### Form 204 retrieval sources (the hard half)

| Source | Gets the Form 204 PDF? | Needs standard PACER acct? | Cost | Legal / ToS | Maintenance |
|---|---|---|---|---|---|
| **RECAP Fetch API** (FLP) | ✅ Yes — purchases on demand, async POST | ✅ **Yes — uses *your* PACER creds; you pay your own PACER bill** | Same PACER fees (docket + PDF). FLP API itself is free | ✅ Sanctioned — FLP's documented product; legitimate billed PACER access | **Low** — maintained API replaces the brittle scraper. ⚠️ Requires sending Keith's PACER username+password to FLP servers; PACER 180-day password rotation (2025) affects it. [RECAP Fetch docs](https://wiki.free.law/c/courtlistener/help/api/rest/v4/recap), [announcement](https://free.law/2019/11/05/pacer-fetch-api) |
| **Direct CM/ECF fetch** (current `intake.py` approach) | ⚠️ UNVERIFIED — regex-scrapes docket HTML for a Form-204-like link, then GETs it with PACER cookie | ✅ Yes | Same PACER fees | ⚠️ Gray — billed access is fine, but scraping docket HTML to *find* the doc is fragile and skirts the spirit of "intended use"; lower risk than fee-avoidance scraping but unverified | **High** — breaks on any CM/ECF UI change; per-court HTML differences. Creds stay in our Railway env (operator-preferred). |
| **RECAP Archive (read free)** | ❌ Only if *already* in the crowdsourced archive | No (for reads) | Free | ✅ Fine | Coverage is **gappy** — "you cannot retrieve PACER documents that are not already in the archive." Small/new Ch.11 Form 204s often absent. Not reliable as the primary. [UMich Law guide](https://libguides.law.umich.edu/c.php?g=1065830&p=7754488) |
| **Apify PACER/RECAP actors** | ⚠️ Discovery-focused; the RECAP ones wrap the gappy archive | Varies | ~$2/1,000 results (discovery actors) | ⚠️ Community actors; PACER scraping actors carry the same ToS risk as any scraper | **High** — community-maintained, low usage, no SLA. Doesn't solve authenticated Form 204 retrieval. |
| **PacerMonitor API** (OD-8 Option A) | ✅ (per their spec) programmatic doc download | Underneath, yes | Subscription + PACER fees | ✅ Their product | ❌ **CONFIRMED UNAVAILABLE to Keith.** Off the table. |
| **Commercial bankruptcy vendors** (Epiq/AACER, Stretto, BankruptcyData/New Generation Research, Bloomberg Law) | ✅ Most provide filings data; some provide documents | No (they have their own feeds) | Enterprise pricing — typically $$$$/yr | ✅ Licensed | **Low** but **almost certainly out of budget** for an SMB MVP. Mention for completeness; not recommended. |

### Legality — the load-bearing dimension (stated plainly)

PACER's own [Policy & Procedures](https://pacer.uscourts.gov/policy-procedures) / [Privacy](https://pacer.uscourts.gov/privacy) pages:

> *"Any attempt to collect data from PACER in a manner which avoids billing is strictly prohibited and may result in criminal prosecution or civil action … Misuse includes … using an automated process to repeatedly access those portions of the PACER application that **do not assess a fee** … for purposes of collecting case information."*

**The prohibition is specifically about dodging billing.** Authenticated, billed access via the **official Auth API + PCL API** is explicitly provided *by PACER* for developers. So:

- ✅ **Low legal risk:** PCL API discovery (billed/waived) + RECAP Fetch or direct CM/ECF retrieval **with proper billing** under a real PACER account. This is the recommended path.
- ⚠️ **Elevated risk, avoid:** scraping fee-free PACER endpoints to harvest case data without billing; scraping **PacerMonitor** (Fitch Solutions' proprietary platform — their ToS governs redistribution); generic Apify "scrape PACER" actors that may hit fee-free endpoints. **Do not recommend any of these without flagging them as ToS-risky — and this analysis does not recommend them.**

---

## Options

### Option A (RECOMMENDED): PCL REST discovery + RECAP Fetch retrieval — on a standard PACER account

- **Approach:** Keep the built PCL discovery in `intake.py` unchanged. Replace the UNVERIFIED `download_form_204()` CM/ECF scraper with **RECAP Fetch** calls (POST docket request → get `recap_document` ID → POST PDF request → download). Keith registers a free standard PACER "Case Search Only" account; its creds go into Railway env (and are passed through to RECAP Fetch).
- **Effort estimate (rough):** ~1-day live-account verification spike + ~2–3 days to swap the retrieval method, handle RECAP Fetch's async polling, and add the 180-day password-rotation handling. Discovery code unchanged. (Smaller than a from-scratch scraper because FLP maintains the hard part.)
- **Pros:** Officially sanctioned end-to-end; eliminates the brittle regex-on-HTML scraper; FLP maintains the CM/ECF-quirk handling; documents also land in the public RECAP archive (good-citizen side effect); same PACER fees as any path.
- **Cons / risks:** **Requires POSTing Keith's PACER username+password to FLP** — a third party — which conflicts with the operator's strict "never share secrets externally" posture; this needs Keith's explicit consent. Async + two-step (docket then PDF) adds latency (fine for a daily batch). 180-day PACER password rotation needs handling (FLP recommends two rotating accounts). Still needs the live-account spike to confirm Form 204 reachability.
- **Best if:** Keith gets a standard PACER account AND is comfortable with FLP holding his PACER creds (or a dedicated low-privilege PACER sub-account is created for this purpose).

### Option B: PCL REST discovery + direct CM/ECF retrieval (finish the built scraper) — on a standard PACER account

- **Approach:** Keith registers a standard PACER account; creds stay only in Railway env. Verify and harden the existing `download_form_204()` CM/ECF approach against live courts.
- **Effort estimate (rough):** ~1-day spike + **3–5 days** to make the scraper robust across the 8–11 covered districts (per-court HTML differences, document-link heuristics, error handling), then ongoing maintenance.
- **Pros:** **Credentials never leave AAA infrastructure** (matches operator policy). Full control over the flow. No third-party dependency.
- **Cons / risks:** **Highest maintenance burden** — CM/ECF UIs differ per court and change without notice; the regex link-matching is fragile. Currently UNVERIFIED. Gray-area ToS (billed, so low risk, but scraping-to-locate is not the "intended" interface). You re-build what FLP already maintains.
- **Best if:** Credential isolation is non-negotiable and the operator accepts the maintenance cost — or as the fallback if RECAP Fetch can't reach Form 204s for a given court.

### Option C (FLOOR / DON'T-FULLY-BUILD): Automated discovery + manual Form 204

- **Approach:** Run PCL (or RSS/CourtListener) discovery to auto-produce the daily list of new Ch.11 filings + case links, posted to Slack. A human (Keith/rep) clicks through to PACER and downloads the Form 204 manually; the parse pipeline picks up from the uploaded PDF.
- **Effort estimate (rough):** Minimal — discovery already works; just wire the "new filings" Slack notification and a manual upload path.
- **Pros:** Zero ToS/scraping risk; no automated PACER document billing surprises; **works even if Keith won't/can't get a standard PACER account or won't share creds.** Eliminates the *discovery* 4-hours/day pain immediately.
- **Cons / risks:** Does **not** eliminate manual data entry for retrieval (PRD success criterion #5 partially unmet). Throughput-limited by human availability. It's a regression from the automation vision — but an honest interim if the account/credential questions stall.
- **Best if:** Q1 comes back "no standard PACER / won't share creds," or as a **Day-1 stopgap** while the standard-PACER account and spike are in flight.

---

## Recommendation

**Pursue Option A (PCL discovery + RECAP Fetch on a standard PACER account), with Option C as the immediate Day-1 stopgap and Option B as the fallback.** Concretely:

1. **Unblock the account first (Q1).** Confirm Keith has, or can register, a free standard PACER "Case Search Only" account separate from PACER Monitor. This single fact gates everything.
2. **Ship Option C now** to deliver discovery value immediately (daily "new Ch.11 filings" Slack post) regardless of the retrieval decision.
3. **Run the verification spike (Q2)** against the live account: confirm Form 204 is reachable via RECAP Fetch for a sample of the target districts, and measure real per-case cost.
4. **Decide RECAP Fetch vs. direct CM/ECF on the credential tradeoff** — put it to the operator + Keith: is FLP holding PACER creds acceptable (Option A, lower maintenance), or must creds stay in-house (Option B, higher maintenance)? A dedicated low-privilege PACER sub-account for the integration is a reasonable middle path that de-risks the credential exposure.

Why this and not the others: it's the only path that is **officially sanctioned, low-cost, satisfies both discovery + retrieval, and minimises maintenance** — while being honest that the make-or-break Form 204 fetch is unverified and the credential question is real. PacerMonitor API is dead; scrapers/Apify are ToS-risky and high-maintenance; commercial vendors are out of budget.

---

## Cost model (operating, data-source only)

| Component | Unit cost | Frequency | Monthly estimate |
|---|---|---|---|
| PCL discovery searches | $0.10 / 54-result page | Daily, batched per district | ~$0 — **falls under $30/quarter waiver** |
| Docket report (to locate Form 204) | ~$1–3.00 (capped at $3/doc) | Per new case | dominant driver |
| Form 204 PDF | ~$0.30–0.50 (3–5 pages × $0.10) | Per new case | secondary |
| **Per-case retrieval total** | **~$1.00–$3.50** | Per new case | — |
| **Estimated monthly total** | — | ~2–4 new commercial Ch.11/business day in covered districts | **~$40–$300/month** |

Notes: the $30/quarter PACER waiver covers ~75% of users; AU Group's *discovery* spend likely stays within it, but *retrieval* will exceed it once volume is real — so budget for retrieval as a real (if modest) line. RECAP Fetch and direct CM/ECF incur the **same** underlying PACER fees; the FLP API adds no charge. Sources: [PACER Pricing FAQ](https://pacer.uscourts.gov/help/faqs/pricing), [pacer.uscourts.gov](https://pacer.uscourts.gov).

---

## Risks and unknowns

**Known risks**
- **Form 204 fetch is unverified (Assumption 2)** — the make-or-break capability. Mitigate with the Day-1 spike before committing the retrieval method.
- **District coverage gap** — code covers NY 2-of-4, PA 2-of-3 (Q3). If unintentional, leads are silently missed in NDNY/WDNY/MDPA.
- **Credential exposure (Option A)** — FLP holding PACER creds conflicts with operator policy. Mitigate with a dedicated sub-account or fall back to Option B.
- **PACER 180-day password rotation (2025)** — will break any automated login on a fixed schedule. Mitigate with rotation handling / two-account rotation (FLP's own recommendation).
- **Per-court CM/ECF variance (Option B)** — high maintenance; the reason Option A is preferred.

**Unknown unknowns to close before committing**
- Does locating the Form 204 *require* buying the full docket report, or is the petition package reachable more cheaply? (Cost driver — resolve in spike.)
- Does RECAP Fetch reliably return Form 204s for the *specific* target districts, or are some courts gappy? (Resolve in spike.)
- Whether Keith's organisation has any procurement constraint on a new PACER billing account.

---

## Open questions for Keith (next call)

1. **[#1 — gates everything] Do you have, or can you register, a *standard* PACER account at pacer.uscourts.gov — separate from your PACER Monitor subscription?** (Free "Case Search Only" registration; open to anyone, no attorney requirement; you'd register as "Creditor/Creditor's Representative" or "Commercial Business.") **If yes — what's the username?** If no — are you willing/able to create one (needs a billing card)?
2. **Are you comfortable with a third party (Free Law Project / CourtListener) holding your PACER login to fetch documents on your behalf** — or must those credentials stay only inside our systems? (Decides RECAP Fetch vs. in-house fetch. A dedicated low-privilege PACER sub-account for the integration is an option if you're on the fence.)
3. **District coverage:** today the build targets NY (Southern + Eastern only), NJ, PA (Eastern + Western only), FL (all 3), MI (both). **Is excluding Northern/Western NY and Middle PA intentional** (low-volume venues) **or a gap we should close?**
4. **Confirm acceptable monthly PACER document spend** in the ~$40–$300/month range as filing volume scales (we'll confirm real volume with a free 1-week dry-run).
5. **Confirmation of dead end:** you were unable to obtain PacerMonitor API access — correct? (So we permanently drop OD-8 Option A.)

---

## Recommended next steps (prioritised)

1. **Ask Q1 on the next call.** Everything forks on it. (Operator → Keith.)
2. **Ship the discovery-only Slack notification (Option C)** now — delivers value and de-risks the timeline regardless of the retrieval answer.
3. **Run a free 1-week PCL `--dry-run`** (intake.py already supports `--dry-run`) to count real covered-district Ch.11 volume and validate Assumption 3 — costs ~$0.
4. **Once a standard PACER account exists, run the 1-day Form 204 spike** against live courts; resolve Assumptions 2 + 4 and the RECAP-Fetch-coverage unknown.
5. **Put the credential tradeoff (Q2) to operator + Keith** and lock RECAP Fetch vs. in-house fetch.
6. **Housekeeping:** create the missing `docs/architecture/pacer-pcl-api-reference.md` (cited but absent) and update OD-8 in the migration doc to point here.

---

## Sources

- [PACER Pricing FAQ](https://pacer.uscourts.gov/help/faqs/pricing) — $0.10/page, $3 doc cap, $30/quarter waiver, creditor listing named as a $3-capped report. **[External]**
- [PACER homepage](https://pacer.uscourts.gov) — fee model, 75% pay nothing, account types. **[External]**
- [PACER Register for an Account](https://pacer.uscourts.gov/register-account) + [On-Line Registration](https://pacer.psc.uscourts.gov/pscof/registration.jsf) — "Case Search Only" free, no attorney requirement, user types incl. "Creditor/Creditor's Representative," "Commercial Business." **[External]**
- [PACER Policy & Procedures](https://pacer.uscourts.gov/policy-procedures) + [Privacy](https://pacer.uscourts.gov/privacy) — ToS: automated fee-avoidance prohibited; billed access sanctioned. **[External]**
- [PACER Developer Resources](https://pacer.uscourts.gov/file-case/developer-resources) — official Authentication API + PCL API. **[External]**
- [PCL API Document (PDF)](https://pacer.uscourts.gov/sites/default/files/files/PCL-API-Document_3.pdf) + [PCL User Manual 2025 (PDF)](https://pacer.uscourts.gov/sites/default/files/files/PCL_User_Manual_2025.pdf) — `<searchFee>.10</searchFee>`, 54/page, batch ≤108k, index-only (no documents). **[External]**
- [RECAP Fetch API docs (FLP Wiki)](https://wiki.free.law/c/courtlistener/help/api/rest/v4/recap) — requires your PACER creds, you pay your own bill, async, 180-day rotation note. **[External]**
- [FLP RECAP Fetch announcement](https://free.law/2019/11/05/pacer-fetch-api) — two-step docket→PDF flow. **[External]**
- [UMich Law RECAP guide](https://libguides.law.umich.edu/c.php?g=1065830&p=7754488) — RECAP archive is crowdsourced/gappy; tracks 84 of 94 district courts. **[External]**
- [CourtListener RECAP Search Alerts (LawSites, 2025)](https://www.lawnext.com/2025/06/courtlistener-launches-recap-search-alerts-for-pacer-filings-google-alerts-for-federal-courts.html) — alert tiers $0/$10/$25/$50/$100. **[External]**
- [FRBP Rule 1007 (Cornell LII)](https://www.law.cornell.edu/rules/frbp/rule_1007) — Form 204 filed *with* the voluntary Ch.11 petition (1007(d)). **[External]**
- [USCourts Bankruptcy Forms](https://www.uscourts.gov/forms-rules/forms/bankruptcy-forms) — B204 = "20 Largest Unsecured Claims." **[External]**
- [Jones Day, Year in Bankruptcy 2024](https://www.jonesday.com/en/insights/2025/01/the-year-in-bankruptcy-2024) + [Epiq Nov 2025](https://www.epiqglobal.com/en-us/resource-center/news/november-commercial-chapter-11-filings-increase-20-over-2024) + [Congress.gov per-district](https://www.congress.gov/crs_external_products/IN/HTML/IN12536.web.html) — commercial Ch.11 = 7,879 (2024); top business-filing districts (note: that ranking is *all* business filings, not just commercial Ch.11). **[External]**
- [PacerMonitor RESTful API spec (PDF)](https://www.pacermonitor.com/static/images/PacerMonitor_RESTful_API.pdf) + [Fitch/Hearst ownership](https://www.hearst.com/-/hearst-s-fitch-group-to-acquire-fulcrum-financial-data) — API exists publicly but confirmed unavailable to Keith. **[External]**
- `services/document-parser/pipeline/intake.py` — built `PacerClient` (PCL discovery real; `download_form_204()` UNVERIFIED CM/ECF scrape). **[Internal]**
- `docs/architecture/n8n-to-code-native-migration.md` §OD-8 + `adr-001-rss-vs-pacer-intake.md` — prior decisions superseded/refined here. **[Internal]**
- `docs/project/prd.md` MVP scope banner — FR-1 PACER + Form 204; "$0.10/page cost friction" already noted. **[Internal]**
