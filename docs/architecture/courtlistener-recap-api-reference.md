# CourtListener / RECAP REST API v4 — Adapter Contract (Form 204 retrieval)

**Prepared:** 2026-06-13
**Purpose:** Source-grounded API contract for a Python adapter that, given `(court_id, docket_number, debtor_name)`, locates and downloads the **Form 204 "List of Creditors Who Have the 20 Largest Unsecured Claims"** for a Chapter 11 case from the CourtListener / RECAP archive (Free Law Project).
**Scope:** API contract only — endpoint URLs, exact field names, call sequence, gotchas. No code.

> **Field-name provenance.** Every field name below is sourced from one of: (a) the FLP API wiki (`wiki.free.law`), (b) the FLP open-source codebase `freelawproject/courtlistener` (`cl/search/models.py`, `cl/search/api_serializers.py`, `cl/search/filters.py`, `cl/search/documents.py` on `main`), or (c) a live HTTP probe run 2026-06-13. The provenance is marked per claim. The two API surfaces use **different field-name casing** — the REST data API uses snake_case model field names; the Search API (`type=r`, Elasticsearch-backed) uses camelCase result fields. Do not mix them.

---

## 0. Base URL & two surfaces

- **Base URL:** `https://www.courtlistener.com/api/rest/v4/` — *(FLP wiki, overview page)*
- **Two relevant surfaces:**
  1. **REST data API** — `/dockets/`, `/docket-entries/`, `/recap-documents/`, `/recap-fetch/`. Snake_case. Cursor-paginated.
  2. **Search API** — `/search/?type=r`. Elasticsearch-backed, camelCase result fields, returns dockets with up to 3 nested documents in one call.
- **File storage host:** `https://storage.courtlistener.com/` (Amazon S3, public) — *(empirically confirmed, see §4)*

---

## 1. Authentication & rate limits

**Auth header** *(FLP wiki, overview)* — token auth, the word `Token`, a space, then the key:

```
Authorization: Token <your-api-token>
```

**Empirically confirmed (2026-06-13):** the PACER data endpoints are **NOT open-by-default**. An unauthenticated `GET /api/rest/v4/dockets/?...` returns:

```
HTTP 401  {"detail":"Authentication credentials were not provided."}
```

So a valid token is **required** for `/dockets/`, `/docket-entries/`, `/recap-documents/`. (Store it in 1Password / env; never in the repo.)

**Rate limits (authenticated)** *(FLP wiki, overview)* — rolling-window, **all throttles apply concurrently**:

| Window | Limit |
|---|---|
| per minute | 5 requests |
| per hour | 50 requests |
| per day | **125 requests** |

Verbatim *(raw overview page, 2026-06-13)*: "authenticated users may make up to 5 requests per minute, 50 requests per hour, and 125 requests per day. You may be eligible for a Free Law Project membership to expand your API access. Commercial agreements are also available." Rates are a **rolling window** ("the allowed access naturally refills as earlier requests fall out of the window").

> **Gotcha — this is a hard daily ceiling.** 125 authenticated REST calls/day is very low for a batch pipeline. The find→identify→download sequence below is designed to spend **1–2 REST calls per case** (prefer the single Search API call in §5). Budget calls; cache the docket `id` and the resolved `filepath_local` so re-runs don't re-spend. Unauthenticated downloads from `storage.courtlistener.com` (§4) do **not** count against these REST throttles. **If the daily ceiling is binding at the pipeline's case volume, pursue an FLP membership or commercial agreement to raise it** — the wiki names both as the sanctioned upgrade paths.

---

## 2. Find the docket — `GET /api/rest/v4/dockets/`

**Filter params** *(source: `DocketFilter` in `cl/search/filters.py`)*:
- `court` — RelatedFilter to `CourtFilter`; filter on the court id string via `court=<court_id>` (e.g. `court=njb`). (`CourtFilter.id` is an exact lookup.)
- `docket_number` — exact lookup (also `docket_number__exact`).
- `docket_number_core` — exact / startswith (normalized core number).
- Also available: `id`, `pacer_case_id`, `date_filed`, `nature_of_suit`.

**Call:**

```
GET /api/rest/v4/dockets/?court=njb&docket_number=23-13359
Authorization: Token <token>
```

> **Caveat:** `docket_number` is **not unique** across courts — always include `court`. *(FLP wiki, pacer-data)*

**Response fields on a docket object** *(FLP wiki pacer-data example response)*:

| Field | Meaning |
|---|---|
| `id` | CourtListener docket PK — **this is the key you carry forward** to filter docket-entries / recap-documents. |
| `case_name` | e.g. "20 Largest…" debtor case name. |
| `case_name_full`, `case_name_short` | longer / shorter variants. |
| `docket_number` | e.g. `"23-13359"`. |
| `docket_number_core` | normalized core (e.g. `"2313359"`). |
| `court` | hyperlinked court resource URL. |
| `court_id` | court id string (e.g. `"njb"`). |
| `date_filed` | case filing date. |
| `pacer_case_id` | PACER's internal case id (needed for recap-fetch by case id). |
| `slug`, `absolute_url` | CL web URLs. |

Pagination is cursor-based (`next` / `previous` cursor URLs).

---

## 3. Find documents in the docket

### 3a. `GET /api/rest/v4/docket-entries/?docket=<id>`

**Filter params** *(source: `DocketEntryFilter`)*: `docket` (RelatedFilter), `entry_number`, `date_filed`, `pacer_sequence_number`, `recap_documents` (RelatedFilter), `id`.

**Docket-entry fields** *(FLP wiki + `DocketEntry` model in `cl/search/models.py`)*:
- `id`, `docket`, `date_filed`, `time_filed`
- `entry_number` — the docket row number (the Form 204 is an **early/low** entry, filed with the petition).
- `recap_sequence_number`, `pacer_sequence_number`
- `description` — **the long description** for the *whole entry* ("generally a few sentences long"). *(FLP wiki, pacer-data)*
- **`recap_documents`** — a **nested array** of RECAP Document objects. *(source: `DocketEntrySerializer.recap_documents = RECAPDocumentSerializer(many=True, read_only=True)` in `cl/search/api_serializers.py`, line ~197.)* So docket-entries **DO embed** their recap-documents inline in the REST response — you do **not** strictly need a separate `/recap-documents/` call.

> **Nested-filter gotcha** *(FLP wiki, pacer-data)*: filters on `/docket-entries/` affect only the **top-level** rows, not the nested `recap_documents`. To filter nested records, add `filter_nested_results=True` to the request URL.

### 3b. `GET /api/rest/v4/recap-documents/?docket_entry=<id>` (separate resource)

Use when you want documents directly rather than via the entry. **Filter params** *(source: `RECAPDocumentFilter`)*: `docket_entry` (RelatedFilter), `document_number`, `attachment_number`*, `pacer_doc_id` (incl. `pacer_doc_id__in=`), `is_available`, `document_type`, `ocr_status`, `is_free_on_pacer`, `sha1`, `date_upload`, `id`.

There is also a convenience endpoint **`/api/rest/v4/recap-query/`** that takes `court` + a comma-separated `pacer_doc_id__in` list:
```
/api/rest/v4/recap-query/?docket_entry__docket__court=dcd&pacer_doc_id__in=04505578698,04505578717
```
*(FLP wiki, pacer-data)*

### RECAP Document object — the fields that matter

Sourced from the `RECAPDocument` model (`cl/search/models.py`) + FLP wiki descriptions:

| Field | Type | Use |
|---|---|---|
| **`is_available`** | BooleanField | **(a) Is the PDF already in the free archive?** `true` ⇒ `filepath_local` is populated and downloadable for free. `false` ⇒ not in archive; must buy via recap-fetch (§6). *(model + FLP wiki: "if we have it (`is_available=True`)")* |
| **`filepath_local`** | FileField | **(b) The downloadable path.** Relative path under the storage bucket, e.g. `"recap/gov.uscourts.dcd.178502/gov.uscourts.dcd.178502.2.0_54.pdf"`. *(FLP wiki example)* See §4 for URL construction. |
| **`description`** | TextField | **(c, REST) The per-document description** — "just a few words" describing this sub-document (vs the entry-level `description` which is sentences). *(FLP wiki, pacer-data)* **Note: the REST RECAPDocument object has NO `short_description` field** — `short_description` exists ONLY on the Search API (§5). *(confirmed: `short_description` absent from `RECAPDocument` model; present only in ES serializers.)* |
| `document_number` | CharField | Document number within the case (string). |
| `attachment_number` | SmallIntegerField | Null on the main document; set on attachments. |
| `pacer_doc_id` | CharField | PACER's document id — pass to recap-fetch to buy the PDF (§6). |
| `page_count` | IntegerField | Page count (a top-20 list is short, ~1–3 pp; a consolidated top-30 a bit longer). |
| `document_type` | IntegerField (choices) | Regular document vs attachment. |
| `sha1` | CharField | Content hash (dedup / integrity). |
| `is_free_on_pacer` | BooleanField | Whether PACER offers it free. |
| `is_sealed` | BooleanField | Sealed flag. |
| `ocr_status` | (field w/ choices) | Whether `plain_text` came from OCR — filterable. |
| `plain_text` | TextField | Extracted text. **Heavy** — omit via Field Selection unless needed (FLP wiki notes it significantly slows responses). |
| `date_upload` | DateTimeField | When uploaded to RECAP. |

\* `attachment_number` is filterable on the related entry, not listed as a standalone `RECAPDocumentFilter` Meta field — filter attachments via `document_type` / the entry.

---

## 4. Download the PDF — `storage.courtlistener.com`

**URL construction:** full public URL = `https://storage.courtlistener.com/` **+** `filepath_local` (bare concatenation; `filepath_local` already includes the `recap/...` prefix).

Example: `filepath_local = "recap/gov.uscourts.dcd.178502/gov.uscourts.dcd.178502.2.0_54.pdf"`
→ `https://storage.courtlistener.com/recap/gov.uscourts.dcd.178502/gov.uscourts.dcd.178502.2.0_54.pdf`

**Empirically confirmed (2026-06-13, `curl`):**
```
HTTP/2 200
content-type: application/pdf
server: AmazonS3
```
- The download is a **public, unauthenticated GET** — no `Authorization` header was sent and S3 returned the bytes. (Do **not** send your token to the storage host.)
- It does **not** consume the REST rate limits in §1.
- Only attempt the download when `is_available == true` (otherwise `filepath_local` is empty/null).

---

## 5. One-call find+identify — Search API `GET /api/rest/v4/search/?type=r`

The RECAP Search API returns **dockets with up to three nested documents in a single call** — ideal for find-and-identify in one request (cheapest against the 125/day budget). *(FLP wiki, search)*

```
GET /api/rest/v4/search/?type=r&court=njb&docket_number=23-13359&description=%2220+largest%22&available_only=on
Authorization: Token <token>
```

**Accepted query params** *(authoritative source: `SearchForm` in `cl/search/forms.py` — these are bare query-string params, no `q:` operator wrapping needed)*:
- `type=r` — RECAP dockets.
- `court` — court id (e.g. `njb`).
- `docket_number` — e.g. `23-13359`. (Snake_case **as a query param**, even though the *result field* is camelCase `docketNumber`. *(FLP wiki, search)*)
- `case_name` — debtor name match.
- `description` — **text-match the per-document description** (use for `"20 largest"` / `"largest unsecured"` — directly targets the Form 204 label).
- `document_number`, `attachment_number` — narrow to a specific doc/attachment.
- `available_only` (`=on`) — **restrict to documents already in the free archive** (`is_available == true`); avoids surfacing docs you'd have to buy.
- `q` — free-text query; supports advanced operators as an alternative/supplement to the structured params above.

**Result casing differs (Elasticsearch-backed).** Top-level docket result fields *(source: `BaseDocketESResultSerializer` + `cl/search/documents.py`)*: `docket_id`, `caseName`, `docketNumber`, `court_id`, `dateFiled`, `dateArgued`, `dateTerminated`, `assignedTo`, `cause`, `suitNature`, `absolute_url`.

**Nested documents array** — field name `recap_documents` (via `NestedRECAPDocumentESResultSerializer`). Per-doc fields *(source: ES serializers `BaseRECAPDocumentESResultSerializer` + `documents.py`)*:
- `description`
- **`short_description`** — exists **only here** (the ES surface), the few-word doc label; this is the field to text-match the Form 204 against in a Search call.
- `snippet` — highlighted text fragment.
- `document_number`, `attachment_number`, `pacer_doc_id`, `is_available`, `filepath_local`, `page_count`, `document_type`, `entry_number`, `entry_date_filed`, `cites`.

**`more_docs`** *(FLP wiki, search + `RECAPESResultSerializer`)*: if a docket has **more than three** matching documents, the result's `more_docs == true` and you must make an additional query (fall back to the REST `/docket-entries/?docket=<docket_id>` path in §3) to see the rest. Relevant because a large case's early entries can exceed three documents — the Form 204 might not be in the top-three nested slice.

---

## 6. Paid fallback — `POST /api/rest/v4/recap-fetch/`

When `is_available == false` (PDF not yet in the free archive), buy it from PACER via RECAP Fetch. *(FLP wiki, recap)*

- **Method:** `POST` (async — returns a request id; you **poll** via `GET /api/rest/v4/recap-fetch/<id>/`). *(FLP wiki: "it immediately responds with an ID … places the request in a queue.")*
- **Requires the operator's PACER credentials in the POST body:** `pacer_username`, `pacer_password` (plus the `Authorization: Token` header). *(FLP wiki, recap)* — **this is a real PACER account, billed by PACER per page.** Never store these in the repo; source from a secret manager at call time.

**`request_type` values** *(FLP wiki, recap)*:

| `request_type` | Buys | Required params |
|---|---|---|
| `1` | Docket sheet | `request_type=1` + one of: `docket` (CL id) **OR** `docket_number`+`court` **OR** `pacer_case_id`+`court`. Optional: `show_parties_and_counsel`, `de_number_start`/`de_number_end`, `de_date_start`/`de_date_end`, `client_code`. |
| `2` | PDF (a specific document) | `request_type=2` + `recap_document` (the CL RECAPDocument id). |
| `3` | Attachment page | `request_type=3` + `recap_document`. |

**Poll status codes** *(FLP wiki, recap)*:
- `2` = processed successfully (then re-read the RECAPDocument; `is_available` flips to `true` and `filepath_local` populates → download via §4).
- `3` = error while processing.
- `1`/`4`/`5`/`6` = queued / in progress / other.

> **Sequence to buy a single Form 204 PDF:** if you only have `court`+`docket_number`, you typically first fetch the **docket** (`request_type=1`) to populate entries+`recap_document` ids in CL, identify the Form 204 entry (§7), then fetch that **PDF** (`request_type=2`, `recap_document=<id>`). Two paid round-trips. PACER page fees apply to both.

---

## 7. Identifying the Form 204 specifically

The form's official title is **"List of Creditors Who Have the 20 Largest Unsecured Claims"** (Official Form 204, filed with the Chapter 11 voluntary petition).

**Where to match:**
- Prefer the document-level label: REST `description` (per-document, few words) or Search API `short_description`. Fall back to the **entry-level** `description` (sentences, often lists the petition + its exhibits/attachments).

**Heuristics (combine, don't rely on one):**
1. **Low `entry_number` / `document_number`.** It's filed *with the voluntary petition*, so it's among the **earliest entries** (often entry 1 and its attachments, or within the first few). Sort/scan ascending `entry_number` first.
2. **Text patterns** to match (case-insensitive) against `description` / `short_description`, in rough priority:
   - `"20 largest"` / `"Twenty Largest"`
   - `"Largest Unsecured"`
   - `"Creditors Who Have"` / `"Creditors Holding"` (older phrasing "Creditors Holding the 20 Largest Unsecured Claims")
   - `"List of Creditors"` (broader — also matches the full mailing matrix; lower-confidence on its own)
   - `"Form 204"` / `"Official Form 204"` (when present in the description)
   - The form is frequently an **attachment to the petition** (`attachment_number` set, parent entry described as "Voluntary Petition"), so also scan attachments of the petition entry.
3. **Page count** as a tiebreaker: a 20-creditor list is short (~1–3 pp); useful to disambiguate from the full creditor matrix.

> **Caveat — large multi-debtor / mega cases file a consolidated top-30.** In jointly-administered Chapter 11 cases (multiple affiliated debtors under one lead case), debtors commonly file a **single consolidated "List of Creditors Who Have the 30 Largest Unsecured Claims"** instead of per-debtor top-20s (Bankruptcy Rule practice for mega-cases). Your matcher must therefore also accept:
>   - `"30 largest"` / `"Thirty Largest"` / `"Consolidated List"`
> and not assume exactly 20 entries or exactly one such document. Treat "top-N largest unsecured" as the concept, N ∈ {20, 30}.

---

## 8. Recommended adapter call sequence (REST-budget-aware)

Given `(court_id, docket_number, debtor_name)`:

1. **One Search call (cheapest):** `GET /search/?type=r&court=<court_id>&docket_number=<docket_number>&q="largest unsecured"`.
   - Read top result's `docket_id`; scan its nested `recap_documents[]` for a Form 204 match (§7) using `short_description`/`description`.
   - If matched **and** `is_available == true` → take `filepath_local`, download via §4. **Done in 1 REST call.**
   - If `more_docs == true` (Form 204 not in the top-3 slice) → go to step 2.
2. **REST fallback (1 call):** `GET /docket-entries/?docket=<docket_id>` (entries embed `recap_documents`). Scan ascending `entry_number`, match §7.
   - If matched + `is_available == true` → download via §4. **2 REST calls total.**
3. **Not in free archive (`is_available == false`):** buy via recap-fetch (§6) — `request_type=1` (docket) if entries/ids aren't populated, then `request_type=2` (`recap_document=<id>`) for the PDF. Poll until status `2`; re-read the RECAPDocument; download via §4. (Paid PACER fees; async.)

**Carry-forward keys to cache:** docket `id` (CL), the matched RECAPDocument `id` + `pacer_doc_id`, and the resolved `filepath_local` — so re-runs skip the search/identify spend.

---

## 9. Gotchas summary

- **REST data endpoints require a token (401 without).** Not open-by-default, unlike some other CL endpoints.
- **125 authenticated REST calls/day, 50/hr, 5/min — concurrent.** Design for 1–2 calls/case; the Search API does find+identify in one. Storage downloads are free of this budget.
- **Two casings:** REST = snake_case (`docket_number`, `case_name`); Search = camelCase (`docketNumber`, `caseName`).
- **`short_description` exists only on the Search API**, not on REST RECAPDocument. Match on REST `description` (per-doc) there.
- **Entry `description` (long, sentences) vs document `description` (short, few words)** — different fields, both named `description` at their respective levels.
- **Download URL = `https://storage.courtlistener.com/` + `filepath_local`** (public S3, no auth). Only valid when `is_available == true`.
- **`more_docs == true`** in a Search result means the 3-nested-doc slice is incomplete — fall back to `/docket-entries/`.
- **`plain_text` is heavy** — exclude it with Field Selection unless you need extracted text.
- **Mega-cases file a consolidated top-30, not a top-20** — accept N ∈ {20, 30} and possibly a single consolidated doc.
- **recap-fetch needs real PACER username/password in the POST body and bills per page** — secret-managed, never in repo; async-polled.

---

### Sources

- FLP API wiki (v4): overview (auth, rate limits, base URL); `pacer-data` (dockets / docket-entries / recap-documents fields, filters, `filepath_local`); `recap` (recap-fetch); `search` (`type=r`, `more_docs`, camelCase mapping). Hosted at `https://wiki.free.law/c/courtlistener/help/api/rest/v4/{overview,pacer-data,recap,search}` (the `courtlistener.com/help/api/rest/*` URLs 301-redirect here).
- FLP open source `freelawproject/courtlistener` (`main`): `cl/search/models.py` (`RECAPDocument`, `DocketEntry` field types), `cl/search/api_serializers.py` (nested `recap_documents`, ES `short_description`/`more_docs`/`snippet`), `cl/search/filters.py` (`DocketFilter`/`DocketEntryFilter`/`RECAPDocumentFilter`/`CourtFilter` Meta + RelatedFilters), `cl/search/documents.py` (ES result fields).
- Empirical HTTP probes (2026-06-13): `GET /api/rest/v4/dockets/?...` → `401` unauth; `GET https://storage.courtlistener.com/recap/gov.uscourts.dcd.178502/gov.uscourts.dcd.178502.2.0_54.pdf` → `200 application/pdf` from AmazonS3, no auth header.
