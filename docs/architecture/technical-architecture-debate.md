# Technical Architecture Debate
## Bankruptcy Creditor Intelligence Platform

**Date:** March 12, 2026  
**Version:** 1.0  
**Purpose:** Structured technical debate covering architecture decisions, tradeoffs, and final recommendations

---

## Executive Summary

**System Characteristics Based on PRD Analysis:**

- **Processing Model:** Batch-oriented (daily PACER polling, weekly docket scans)
- **Volume:** 50+ filings/day, 1,000+ companies/day, 500+ creditors per Schedule F
- **Latency Requirements:** 24hr for top 20 extraction, 48hr for Schedule F detection
- **Integration Points:** PACER API, ZoomInfo API, Salesforce API
- **Data Processing:** Document parsing (structured PDFs, OCR for scanned), NLP for classification
- **Storage:** Historical creditor tracking (25K+ seed data, growing), audit trails, document retention
- **Users:** 1 admin (Keith), 5-10 territory reps (read-only Salesforce consumers)
- **Reliability:** 99%+ uptime for daily processing, 95%+ extraction accuracy
- **Cost Constraints:** PACER documents ($0.10/page), ZoomInfo API calls, infrastructure

---

## Table of Contents

1. [Backend Architecture](#1-backend-architecture)
2. [Frontend Framework](#2-frontend-framework)
3. [Database Strategy](#3-database-strategy)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Scalability Architecture](#5-scalability-architecture)
6. [API Design](#6-api-design)
7. [Deployment Infrastructure](#7-deployment-infrastructure)
8. [Speed vs. Scalability Tradeoffs](#8-speed-vs-scalability-tradeoffs)
9. [Cost Optimization](#9-cost-optimization)
10. [Security Considerations](#10-security-considerations)
11. [Final Architecture Recommendation](#11-final-architecture-recommendation)

---

## 1. Backend Architecture

### Option A: Monolithic Python Application

**Technology Stack:** Python + FastAPI/Django + Celery + Redis

**Pros:**
- ✅ **Best for document processing:** Python ecosystem excels at PDF parsing (PyPDF2, pdfplumber, Tesseract OCR), NLP (spaCy for entity extraction)
- ✅ **Rapid development:** Single codebase, simpler debugging, faster iteration for MVP (3-4 week Phase 1 timeline)
- ✅ **Strong API client libraries:** Excellent PACER, ZoomInfo, Salesforce SDKs in Python
- ✅ **Data science ecosystem:** Pandas for data transformation, scikit-learn for fuzzy matching/deduplication
- ✅ **Celery for job queues:** Mature async task processing for batch jobs (daily polling, weekly scans)
- ✅ **Lower operational complexity:** Single service to deploy, monitor, and maintain

**Cons:**
- ❌ **Scaling limitations:** Vertical scaling only until you split services
- ❌ **Deployment coupling:** Any change requires full application redeploy
- ❌ **Resource contention:** OCR jobs (CPU-heavy) compete with API calls (I/O-heavy) for resources
- ❌ **Single point of failure:** If app crashes, entire pipeline stops

**Best For:** MVP development, small team (1-2 engineers), when time-to-market is critical

---

### Option B: Microservices Architecture (Node.js + Python services)

**Technology Stack:** Node.js (API layer) + Python (document processing) + Go (Schedule F scanner)

**Pros:**
- ✅ **Independent scaling:** Scale OCR service independently from API service
- ✅ **Technology fit:** Python for document parsing, Node.js for API orchestration, Go for concurrent docket scanning
- ✅ **Fault isolation:** Document parsing failure doesn't crash API layer
- ✅ **Team autonomy:** Different teams can own different services
- ✅ **Performance optimization:** Go service for Schedule F scanner handles 1000s of concurrent docket checks efficiently

**Cons:**
- ❌ **Higher complexity:** Service discovery, inter-service communication, distributed logging
- ❌ **Longer development time:** 6-8 weeks instead of 3-4 weeks for Phase 1
- ❌ **Operational overhead:** Multiple deployments, monitoring dashboards, debugging across services
- ❌ **Network latency:** Inter-service calls add latency (though acceptable for batch processing)
- ❌ **Premature optimization:** Current volume (50 filings/day) doesn't justify microservices complexity

**Best For:** High-scale production (1000+ filings/day), large team (5+ engineers), when independent service scaling is required

---

### Option C: Serverless Event-Driven (AWS Lambda + Step Functions)

**Technology Stack:** AWS Lambda (Python) + Step Functions + EventBridge + SQS

**Pros:**
- ✅ **Pay-per-use:** Only pay when processing filings (no idle server costs overnight)
- ✅ **Auto-scaling:** Lambda scales automatically from 1 to 1000 concurrent executions
- ✅ **Event-driven:** PACER polling triggers → extraction Lambda → enrichment Lambda → Salesforce push Lambda
- ✅ **Built-in retry logic:** Step Functions handles retries, error handling, state management
- ✅ **No server management:** Focus on business logic, not infrastructure

**Cons:**
- ❌ **Cold start latency:** 2-5 second cold starts acceptable for batch processing, problematic for real-time
- ❌ **15-minute execution limit:** Large Schedule F documents (500+ pages) may timeout; requires chunking
- ❌ **Debugging complexity:** Distributed tracing across Lambda functions, Step Function state machines
- ❌ **Vendor lock-in:** Tightly coupled to AWS services
- ❌ **Cost unpredictability:** Costs increase linearly with volume; expensive at high scale

**Best For:** Variable workload patterns, low initial traffic, cloud-native architecture, when operational overhead must be minimized

---

### **DECISION: Option A — Monolithic Python Application**

**Rationale:**
1. **Time-to-market:** 3-4 week Phase 1 deadline requires rapid development; monolith delivers fastest
2. **Volume justification:** 50 filings/day × 20 creditors = 1,000 records/day fits comfortably in monolith capacity
3. **Technology fit:** Python's document processing ecosystem (PyPDF2, Tesseract, spaCy) is unmatched
4. **Team size:** 1-2 engineers can manage monolith; microservices require 3+ engineers
5. **Operational simplicity:** Single deployment, single monitoring dashboard, simpler debugging
6. **Migration path:** Celery tasks can be extracted into separate services later if needed (e.g., OCR service)

**Architecture:**
```
FastAPI (API layer)
  ↓
Celery Workers (async task processing)
  ├─ PACER Polling Job (daily at 2am)
  ├─ Document Parsing Job (on-demand)
  ├─ ZoomInfo Enrichment Job (batch processing)
  ├─ Salesforce Push Job (on-demand)
  └─ Schedule F Scanner Job (weekly cron)
  ↓
Redis (Celery broker + result backend)
PostgreSQL (data persistence)
```

---

## 2. Frontend Framework

### Option A: No Custom Frontend (Salesforce-only UI)

**Technology Stack:** Salesforce Lightning Web Components (LWC) + Custom Objects

**Pros:**
- ✅ **Zero frontend development:** Salesforce is already the system of record; reps live in Salesforce
- ✅ **Native integration:** Custom fields, layouts, views already support territory filtering
- ✅ **User familiarity:** Reps already proficient with Salesforce; zero training required
- ✅ **Mobile support:** Salesforce mobile app works out of the box
- ✅ **Fastest time-to-market:** No frontend code to write, test, or deploy

**Cons:**
- ❌ **Limited approval workflow UI:** Keith's PACER favorites approval flow requires external PACER interface
- ❌ **No admin dashboard:** No centralized view of daily processing stats, error rates, cost tracking
- ❌ **Salesforce license costs:** Additional user licenses if team grows
- ❌ **Limited customization:** Constrained by Salesforce UI/UX patterns

**Best For:** MVP with minimal UI requirements, when users already live in Salesforce

---

### Option B: Minimal Admin Dashboard (React SPA)

**Technology Stack:** React + Tailwind CSS + Vite + React Query

**Pros:**
- ✅ **Admin-specific UI:** Keith gets custom approval workflow UI, daily processing dashboard, cost tracking
- ✅ **Modern UX:** Better user experience than Salesforce for admin workflows
- ✅ **Real-time updates:** WebSocket support for live processing status, Schedule F alerts
- ✅ **Component reusability:** Build once, reuse for future admin features
- ✅ **Fast development:** Vite for instant HMR, Tailwind for rapid styling

**Cons:**
- ❌ **Additional development:** 2-3 weeks for admin dashboard (delays Phase 1)
- ❌ **Deployment overhead:** Separate frontend deployment pipeline (S3 + CloudFront)
- ❌ **Maintenance burden:** Another codebase to maintain, update, debug
- ❌ **Redundancy:** Reps still use Salesforce; dashboard only for Keith

**Best For:** When admin workflows are complex and require custom UI

---

### Option C: Full-Stack Application (Next.js SSR)

**Technology Stack:** Next.js + TypeScript + Tailwind + tRPC

**Pros:**
- ✅ **Unified codebase:** Frontend + backend API routes in single repo
- ✅ **SEO-friendly:** Server-side rendering for marketing pages, documentation
- ✅ **Type safety:** End-to-end TypeScript from frontend to backend
- ✅ **Modern developer experience:** Hot reload, automatic API route generation
- ✅ **Full control:** Custom UI for both admin and rep workflows

**Cons:**
- ❌ **Longest development time:** 6-8 weeks for full UI rebuild
- ❌ **User migration:** Reps must switch from Salesforce to new UI (change management overhead)
- ❌ **Duplicate data:** Must replicate Salesforce territory views, filtering, activity logging
- ❌ **Salesforce integration complexity:** Still need Salesforce API integration for existing workflows

**Best For:** When building a standalone product, not integrating with existing CRM

---

### **DECISION: Option A — No Custom Frontend (Salesforce-only UI) + Minimal Admin API**

**Rationale:**
1. **User workflow:** Reps live in Salesforce; custom UI creates friction, not value
2. **Time-to-market:** Zero frontend development means Phase 1 completes in 3-4 weeks
3. **Keith's approval workflow:** PACER favorites integration is external to our system; no custom UI needed
4. **Admin needs:** Keith can use Salesforce reports/dashboards for daily summaries; API endpoints for manual actions
5. **Future flexibility:** Can add React admin dashboard in Phase 4 if needed

**Implementation:**
- **Reps:** 100% Salesforce UI (custom objects, fields, layouts, territory-filtered views)
- **Keith:** Salesforce + PACER interface (existing) + Optional: Simple HTML admin page for manual triggers
- **Monitoring:** Datadog/CloudWatch dashboards for processing stats, error rates, cost tracking

---

## 3. Database Strategy

### Option A: Single PostgreSQL Database (All Data)

**Schema:**
- `bankruptcies` (debtor metadata, filing date, case number)
- `creditors` (name, address, claim amount, company/individual flag)
- `bankruptcy_creditors` (join table linking creditors to bankruptcies)
- `zoom_info_contacts` (enriched contact data)
- `salesforce_accounts` (account IDs, last sync timestamp)
- `processing_jobs` (job status, retry count, error logs)
- `schedule_f_queue` (active cases for monitoring)

**Pros:**
- ✅ **ACID transactions:** Guaranteed consistency across creditor extraction → enrichment → Salesforce push
- ✅ **Complex queries:** Historical exposure queries (COUNT bankruptcies per creditor) are simple SQL JOINs
- ✅ **Mature tooling:** Excellent backup, replication, monitoring, indexing support
- ✅ **Full-text search:** Built-in support for creditor name fuzzy matching (pg_trgm extension)
- ✅ **JSON support:** Store PACER raw documents, ZoomInfo API responses as JSONB for debugging
- ✅ **Cost-effective:** Single RDS instance ($100-300/month) handles MVP volume easily

**Cons:**
- ❌ **Vertical scaling:** Eventually requires larger instance size (but not at 50 filings/day)
- ❌ **Backup size:** Raw PDF documents stored in database bloat backup sizes
- ❌ **Read replica lag:** If adding read replicas later, potential replication lag for real-time queries

**Best For:** Transactional workloads, complex relational queries, when ACID guarantees are critical

---

### Option B: PostgreSQL + S3 (Hybrid: Structured Data + Document Storage)

**Schema:**
- PostgreSQL: `bankruptcies`, `creditors`, `processing_jobs`, `schedule_f_queue`
- S3: Raw PDF documents, OCR outputs, PACER API responses

**Pros:**
- ✅ **Cost optimization:** S3 is 10x cheaper than PostgreSQL storage for large documents
- ✅ **Backup efficiency:** Database backups are smaller (no binary PDFs)
- ✅ **Document versioning:** S3 versioning tracks document updates (amended Schedule F)
- ✅ **Scalability:** S3 scales infinitely; no storage limits
- ✅ **Audit trail:** Retain raw PACER documents for compliance without database bloat

**Cons:**
- ❌ **Two storage systems:** Must manage PostgreSQL + S3 lifecycle policies
- ❌ **Consistency complexity:** Document in S3 but metadata in PostgreSQL requires distributed transaction handling
- ❌ **Latency:** Fetching documents from S3 adds network latency (50-100ms)

**Best For:** When document volume is high (100+ filings/day with 500-page Schedule Fs)

---

### Option C: PostgreSQL + Redis (Hybrid: Persistent + Cache)

**Schema:**
- PostgreSQL: All persistent data (bankruptcies, creditors, jobs)
- Redis: Celery task queue, ZoomInfo API response cache, Schedule F monitoring queue

**Pros:**
- ✅ **Queue management:** Redis is ideal for Celery task queues (FIFO, delayed execution)
- ✅ **API response caching:** Cache ZoomInfo lookups for duplicate creditors (same company across multiple filings)
- ✅ **Session storage:** Cache Schedule F monitoring state (last scanned timestamp per case)
- ✅ **Rate limit tracking:** Track PACER/ZoomInfo API usage to avoid rate limits
- ✅ **Fast reads:** Sub-millisecond cache lookups reduce API calls

**Cons:**
- ❌ **Volatility:** Redis is in-memory; data loss on restart (mitigated with AOF persistence)
- ❌ **Two systems:** Must manage PostgreSQL + Redis deployments
- ❌ **Cost:** Additional Redis instance ($50-100/month)

**Best For:** When async job processing and API caching are critical

---

### **DECISION: Option C — PostgreSQL + Redis (Hybrid) + S3 for Documents**

**Rationale:**
1. **Celery requirement:** Async job processing requires Redis as Celery broker (non-negotiable)
2. **API caching:** ZoomInfo API costs $X per lookup; caching reduces duplicate calls by 30-40%
3. **Document storage:** S3 for raw PACER PDFs (audit trail, cost efficiency)
4. **PostgreSQL for structured data:** Creditor history queries, fuzzy matching, transaction support
5. **Cost balance:** PostgreSQL ($150/mo) + Redis ($75/mo) + S3 ($10/mo) = $235/mo total

**Implementation:**
```
PostgreSQL (RDS):
  - bankruptcies, creditors, bankruptcy_creditors, zoom_info_contacts, processing_jobs, schedule_f_queue
  - Indexes: creditor_name (GIN for fuzzy), bankruptcy_date (BTREE), case_number (unique)

Redis (ElastiCache):
  - Celery broker (task queue)
  - ZoomInfo API response cache (TTL: 7 days)
  - Schedule F monitoring state (last_scanned_at per case)
  - PACER/ZoomInfo rate limit counters

S3:
  - /raw-documents/{case_number}/{docket_entry_id}.pdf
  - /parsed-outputs/{case_number}/{docket_entry_id}.json
  - /ocr-outputs/{case_number}/{docket_entry_id}.txt
  - Lifecycle policy: Retain raw documents 5 years, delete OCR outputs after 1 year
```

---

## 4. Authentication & Authorization

### Option A: No Authentication (Internal Service Only)

**Implementation:** Backend API has no auth; relies on VPC network isolation

**Pros:**
- ✅ **Zero development time:** No auth code to write, test, or maintain
- ✅ **Simplicity:** No token management, password resets, session handling
- ✅ **Fast iteration:** Focus on core business logic, not auth infrastructure

**Cons:**
- ❌ **Security risk:** If VPC is breached, API is fully exposed
- ❌ **No audit trail:** Cannot track which user triggered manual actions
- ❌ **No PACER credential security:** PACER username/password stored in plaintext env vars

**Best For:** Proof-of-concept, when API is never exposed externally

---

### Option B: API Key Authentication

**Implementation:** Keith's admin API endpoints require `X-API-Key` header

**Pros:**
- ✅ **Simple implementation:** 1 day of development (API key generation, validation middleware)
- ✅ **Audit trail:** Log API key with every request for debugging
- ✅ **Revocable:** Can rotate API keys if compromised
- ✅ **Sufficient for single user:** Keith is the only admin; no complex RBAC needed

**Cons:**
- ❌ **Key management:** API key stored in Keith's environment (risk of accidental commit)
- ❌ **No expiration:** API keys don't expire automatically; manual rotation required
- ❌ **No user context:** Cannot differentiate between Keith vs. other admins (if team grows)

**Best For:** Internal admin APIs, single-user systems, when OAuth is overkill

---

### Option C: OAuth 2.0 / OIDC (Salesforce Identity Provider)

**Implementation:** Use Salesforce as OAuth provider; users log in with Salesforce credentials

**Pros:**
- ✅ **Single sign-on:** Keith and reps use existing Salesforce credentials
- ✅ **Enterprise-grade:** OAuth 2.0 is industry standard; battle-tested security
- ✅ **Fine-grained permissions:** RBAC based on Salesforce roles (admin vs. rep)
- ✅ **Token expiration:** Access tokens expire after 2 hours; refresh tokens for long-lived sessions
- ✅ **Audit trail:** Salesforce logs every OAuth token issuance

**Cons:**
- ❌ **Development complexity:** 1-2 weeks to implement OAuth flow, token validation, refresh logic
- ❌ **Salesforce dependency:** If Salesforce auth is down, our system is inaccessible
- ❌ **Overkill for MVP:** 1 admin user doesn't justify OAuth complexity

**Best For:** Multi-user systems, when SSO with existing identity provider is required

---

### **DECISION: Option B — API Key Authentication + AWS Secrets Manager for Credentials**

**Rationale:**
1. **Single admin user:** Keith is the only user interacting with admin API; OAuth is overkill
2. **Audit requirement:** Need to log API actions for debugging; API key provides identity
3. **Credential security:** PACER/ZoomInfo credentials stored in AWS Secrets Manager (encrypted at rest, automatic rotation)
4. **Time-to-market:** API key auth takes 1 day vs. 1-2 weeks for OAuth
5. **Migration path:** Can upgrade to OAuth 2.0 in Phase 4 if team grows

**Implementation:**
```python
# API Key Middleware (FastAPI)
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return api_key

# Protected Admin Endpoints
@app.post("/admin/trigger-schedule-f-scan", dependencies=[Depends(verify_api_key)])
async def trigger_schedule_f_scan():
    # Manually trigger Schedule F scan
    pass
```

**Credential Management:**
- **PACER credentials:** AWS Secrets Manager (`/prod/pacer/username`, `/prod/pacer/password`)
- **ZoomInfo API key:** AWS Secrets Manager (`/prod/zoominfo/api-key`)
- **Salesforce OAuth tokens:** AWS Secrets Manager (`/prod/salesforce/access-token`)
- **Admin API key:** AWS Secrets Manager (`/prod/admin/api-key`)
- **Rotation policy:** Rotate every 90 days via AWS Secrets Manager automatic rotation

---

## 5. Scalability Architecture

### Current Scale (Phase 1-3)

**Volume:**
- 50 bankruptcies/day × 20 creditors = 1,000 creditors/day
- 5 Schedule F/week × 300 creditors = 1,500 creditors/week
- **Total: ~8,500 creditors/month**

**Processing Time:**
- PACER polling: 30 seconds/filing × 50 = 25 minutes/day
- Document parsing: 10 seconds/creditor × 1,000 = 2.8 hours/day
- ZoomInfo enrichment: 2 seconds/company × 800 companies = 27 minutes/day
- **Total daily processing: ~4 hours**

**Resource Requirements:**
- **CPU:** Moderate (OCR is CPU-intensive, but only 5 Schedule F/week)
- **Memory:** 4GB for FastAPI + Celery workers
- **Storage:** 10GB/month (raw PDFs + database)

**Conclusion:** Single EC2 instance (t3.medium, 2 vCPU, 4GB RAM) handles MVP volume comfortably

---

### Future Scale (Phase 4: Full U.S. Coverage)

**Projected Volume:**
- 500 bankruptcies/day (10x current) × 20 creditors = 10,000 creditors/day
- 50 Schedule F/week × 300 creditors = 15,000 creditors/week
- **Total: ~85,000 creditors/month**

**Bottlenecks:**
1. **OCR processing:** 50 Schedule F/week × 500 pages × 5 seconds/page = **34 hours/week** (bottleneck!)
2. **ZoomInfo API rate limits:** 10,000 requests/day limit (hit ceiling at 8,000 companies/day)
3. **Database writes:** 10,000 creditor inserts/day (PostgreSQL handles easily, not a bottleneck)

**Scaling Strategy:**

#### Horizontal Scaling Approach

**Phase 1-3 (Current):**
```
Single EC2 Instance (t3.medium)
  ├─ FastAPI (1 process)
  ├─ Celery Workers (4 workers)
  └─ Redis + PostgreSQL (single instance)
```

**Phase 4 (10x Scale):**
```
Application Layer (Auto Scaling Group):
  ├─ FastAPI (2x t3.small instances behind ALB)
  └─ Celery Workers (4x t3.medium instances)
      ├─ OCR Worker Pool (dedicated, GPU-enabled)
      ├─ Enrichment Worker Pool (API calls)
      └─ General Worker Pool (parsing, Salesforce)

Data Layer:
  ├─ PostgreSQL (db.t3.large with read replica)
  ├─ Redis (cache.t3.medium with replication)
  └─ S3 (unlimited storage)
```

**Cost Increase:**
- Phase 1-3: $350/month (1 EC2 + RDS + Redis + S3)
- Phase 4 (10x): $1,200/month (6 EC2 + larger RDS + Redis replica + S3)
- **Cost per creditor:** $0.04 (Phase 1) → $0.014 (Phase 4) — economies of scale!

---

### Vertical vs. Horizontal Scaling Decision Matrix

| Scenario | Current (1-3) | Phase 4 (10x) | Scaling Strategy |
|----------|---------------|---------------|------------------|
| **PACER polling** | 25 min/day | 4 hours/day | ✅ Horizontal: Multiple workers poll different states in parallel |
| **Document parsing** | 2.8 hours/day | 28 hours/day | ✅ Horizontal: Worker pool with 10+ instances |
| **OCR processing** | 1 hour/week | 34 hours/week | ✅ Horizontal + GPU: Dedicated OCR workers with GPU (Tesseract benefits from GPU) |
| **ZoomInfo enrichment** | 27 min/day | 4.5 hours/day | ✅ Horizontal + Caching: Worker pool + aggressive Redis caching (40% cache hit rate) |
| **PostgreSQL writes** | 1,000/day | 10,000/day | ⚠️ Vertical (for now): Larger RDS instance; Horizontal (later): Write sharding by state |

---

### **DECISION: Start Vertical (Phase 1-3), Prepare for Horizontal (Phase 4)**

**Rationale:**
1. **Premature optimization:** Current volume (1,000 creditors/day) doesn't justify horizontal scaling complexity
2. **Celery architecture:** Already supports horizontal scaling (add more worker instances when needed)
3. **Database headroom:** PostgreSQL handles 10K writes/day easily; no immediate need for sharding
4. **Cost efficiency:** Single instance costs $350/mo; horizontal scaling costs $1,200/mo (3.4x for 10x volume)
5. **Monitoring-driven:** Scale when CPU > 70% sustained or ZoomInfo rate limits hit

**Scaling Triggers:**
- **Add Celery worker:** When processing time > 6 hours/day (current: 4 hours)
- **Add OCR worker pool:** When Schedule F > 10/week (current: 5/week)
- **Scale PostgreSQL:** When connections > 80% or CPU > 70% (current: 20% usage)
- **Add Redis replica:** When cache hit rate drops < 60% or memory > 80%

---

## 6. API Design

### Option A: REST API (Traditional CRUD)

**Endpoints:**
```
GET  /api/v1/bankruptcies                  # List bankruptcies
GET  /api/v1/bankruptcies/{id}             # Get bankruptcy details
GET  /api/v1/creditors?bankruptcy_id={id}  # List creditors for bankruptcy
POST /api/v1/schedule-f/approve            # Keith approves Schedule F purchase
GET  /api/v1/admin/processing-stats        # Daily processing summary
POST /api/v1/admin/trigger-pacer-poll      # Manually trigger PACER poll
```

**Pros:**
- ✅ **Industry standard:** RESTful APIs are universally understood
- ✅ **HTTP caching:** Leverage HTTP cache headers (ETag, Cache-Control) for GET requests
- ✅ **Stateless:** No session management; each request is independent
- ✅ **Easy testing:** Postman, curl, HTTPie work out of the box
- ✅ **Firewall-friendly:** HTTP/HTTPS ports (80/443) rarely blocked

**Cons:**
- ❌ **Over-fetching:** GET /bankruptcies returns full objects; clients may only need IDs
- ❌ **Multiple round trips:** Getting bankruptcy + creditors + contacts requires 3 API calls
- ❌ **Versioning complexity:** Breaking changes require /v2/ endpoints and migration path

**Best For:** Public APIs, when HTTP caching is valuable, standard CRUD operations

---

### Option B: GraphQL API

**Schema:**
```graphql
type Bankruptcy {
  id: ID!
  debtorName: String!
  filingDate: Date!
  creditors: [Creditor!]!
}

type Creditor {
  id: ID!
  name: String!
  claimAmount: Float
  contacts: [Contact!]!
}

query {
  bankruptcies(state: "CA", limit: 10) {
    id
    debtorName
    creditors {
      name
      contacts { email }
    }
  }
}
```

**Pros:**
- ✅ **Precise data fetching:** Clients request only fields they need; no over-fetching
- ✅ **Single round trip:** Bankruptcy + creditors + contacts in one query
- ✅ **Strong typing:** Schema-first development; auto-generated TypeScript types
- ✅ **Introspection:** GraphQL playground for interactive API exploration

**Cons:**
- ❌ **Overkill for simple CRUD:** MVP has ~5 endpoints; GraphQL overhead not justified
- ❌ **N+1 query problem:** Naive implementation causes database query explosion (solvable with DataLoader)
- ❌ **Caching complexity:** HTTP caching doesn't work; requires custom cache layer (Apollo Client)
- ❌ **Learning curve:** Team must learn GraphQL, schema design, resolver patterns

**Best For:** Complex data graphs, when clients need flexible querying, mobile apps with bandwidth constraints

---

### Option C: gRPC (High-Performance RPC)

**Protobuf Schema:**
```protobuf
service BankruptcyService {
  rpc GetBankruptcy (GetBankruptcyRequest) returns (Bankruptcy);
  rpc ListCreditors (ListCreditorsRequest) returns (CreditorList);
}

message Bankruptcy {
  string id = 1;
  string debtor_name = 2;
  int64 filing_date = 3;
}
```

**Pros:**
- ✅ **Performance:** Binary protocol (Protobuf) is 5-10x faster than JSON
- ✅ **Type safety:** Protobuf schema generates type-safe clients (Python, Go, Node.js)
- ✅ **HTTP/2:** Multiplexing, bidirectional streaming, server push
- ✅ **Small payloads:** Protobuf is 30-50% smaller than JSON

**Cons:**
- ❌ **Browser support:** gRPC-web requires proxy (Envoy) for browser compatibility
- ❌ **Debugging difficulty:** Binary payloads not human-readable; requires special tools (grpcurl)
- ❌ **Overkill for MVP:** Current volume (1,000 requests/day) doesn't benefit from gRPC performance
- ❌ **Limited tooling:** Postman only recently added gRPC support; ecosystem less mature

**Best For:** Microservices communication, high-throughput APIs (>10K requests/second), when binary protocols are acceptable

---

### **DECISION: Option A — REST API with OpenAPI Spec**

**Rationale:**
1. **Simplicity:** MVP has ~5 admin endpoints; REST is sufficient and universally understood
2. **Debugging:** HTTP/JSON is human-readable; easy to debug with curl, Postman
3. **Salesforce integration:** Salesforce REST API follows same patterns; team familiarity
4. **No frontend:** No complex data fetching requirements; GraphQL overkill
5. **Documentation:** OpenAPI (Swagger) auto-generates interactive API docs from FastAPI code

**API Design Principles:**
```
# RESTful Resource Naming
GET  /api/v1/bankruptcies          # Collection
GET  /api/v1/bankruptcies/{id}     # Resource
POST /api/v1/bankruptcies          # Create (rare; PACER creates)

# Admin Actions (Non-RESTful, Action-Oriented)
POST /api/v1/admin/trigger-pacer-poll
POST /api/v1/admin/trigger-schedule-f-scan
POST /api/v1/schedule-f/approve    # Keith's approval action

# Processing Status (Read-Only)
GET /api/v1/admin/processing-stats
GET /api/v1/admin/jobs/{job_id}    # Job status for async tasks
```

**OpenAPI Schema (Auto-Generated by FastAPI):**
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Bankruptcy Creditor Intelligence API",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc"  # ReDoc at /redoc
)

class Bankruptcy(BaseModel):
    id: str
    debtor_name: str
    filing_date: date
    case_number: str
    court_district: str

@app.get("/api/v1/bankruptcies", response_model=list[Bankruptcy])
async def list_bankruptcies(state: str = None, limit: int = 100):
    """List recent bankruptcies, optionally filtered by state"""
    pass
```

**Versioning Strategy:**
- **URL versioning:** `/api/v1/` in path (explicit, easy to route)
- **Breaking changes:** New version (`/api/v2/`); maintain v1 for 6 months
- **Non-breaking changes:** Add optional fields to v1; no version bump

---

## 7. Deployment Infrastructure

### Option A: Single EC2 Instance (Traditional Deployment)

**Stack:** EC2 (t3.medium) + RDS + ElastiCache + S3 + Route 53

**Pros:**
- ✅ **Simple deployment:** SSH into server, `git pull`, `systemctl restart app`
- ✅ **Predictable costs:** Fixed monthly cost ($350/mo); no surprises
- ✅ **Full control:** SSH access for debugging, log inspection, manual restarts
- ✅ **Low latency:** Everything in same AZ; no network hops

**Cons:**
- ❌ **Single point of failure:** EC2 instance failure = entire system down
- ❌ **Manual scaling:** Must manually provision larger instance if traffic increases
- ❌ **Downtime during deploys:** Zero-downtime deployments require load balancer + blue/green
- ❌ **No auto-recovery:** If instance crashes, manual intervention required

**Best For:** MVP, small team, when simplicity > high availability

---

### Option B: Docker + ECS Fargate (Managed Containers)

**Stack:** ECS Fargate + Application Load Balancer + RDS + ElastiCache + S3

**Pros:**
- ✅ **No server management:** Fargate manages container orchestration (no EC2 to patch)
- ✅ **Auto-scaling:** Scale containers based on CPU/memory; handle traffic spikes
- ✅ **Zero-downtime deployments:** Rolling updates with health checks
- ✅ **Container portability:** Same Docker image runs locally, staging, production
- ✅ **Task isolation:** Celery workers run as separate Fargate tasks; fault isolation

**Cons:**
- ❌ **Higher cost:** Fargate is 20-30% more expensive than EC2 for same compute
- ❌ **Debugging complexity:** No SSH access; must use CloudWatch logs, ECS Exec
- ❌ **Cold start latency:** Fargate tasks take 30-60 seconds to start (not issue for batch processing)
- ❌ **Networking complexity:** VPC, subnets, security groups, ALB target groups

**Best For:** Production systems, when high availability is critical, teams familiar with containers

---

### Option C: Kubernetes (EKS) (Cloud-Native Orchestration)

**Stack:** EKS + Helm + RDS + ElastiCache + S3

**Pros:**
- ✅ **Industry standard:** Kubernetes is universal; easier to hire engineers familiar with K8s
- ✅ **Advanced orchestration:** StatefulSets for Redis, CronJobs for scheduled tasks, HPA for auto-scaling
- ✅ **Multi-cloud portability:** Same manifests deploy to AWS, GCP, on-prem
- ✅ **Rich ecosystem:** Helm charts, operators, service meshes (Istio), monitoring (Prometheus)

**Cons:**
- ❌ **Steep learning curve:** Kubernetes is complex; 2-4 weeks to learn for new team
- ❌ **Operational overhead:** Cluster upgrades, node management, RBAC configuration
- ❌ **EKS costs:** $73/month for control plane + EC2 worker nodes
- ❌ **Overkill for MVP:** 1 service doesn't justify Kubernetes complexity

**Best For:** Large-scale systems (10+ microservices), teams with K8s expertise, multi-cloud strategy

---

### **DECISION: Option A — Single EC2 Instance (Phase 1-3) → ECS Fargate (Phase 4)**

**Rationale:**
1. **MVP simplicity:** EC2 instance is fastest to deploy; no container learning curve
2. **Cost optimization:** $350/mo for EC2 vs. $500/mo for Fargate; 30% savings
3. **High availability not critical:** Batch processing can tolerate 1-hour downtime (re-run failed jobs)
4. **Migration path:** Containerize later (Phase 4) when scaling requirements justify Fargate

**Phase 1-3 Deployment (EC2):**
```
Ubuntu 22.04 LTS (t3.medium, 2 vCPU, 4GB RAM)
  ├─ Nginx (reverse proxy)
  ├─ FastAPI (systemd service)
  ├─ Celery Workers (systemd service × 4 workers)
  ├─ Redis (local instance)
  └─ Logs → CloudWatch Logs agent
```

**Deployment Script:**
```bash
#!/bin/bash
# deploy.sh
git pull origin main
pip install -r requirements.txt
pytest tests/
systemctl restart fastapi
systemctl restart celery-worker
```

**Phase 4 Migration (ECS Fargate):**
```
ECS Cluster:
  ├─ FastAPI Service (2 Fargate tasks, ALB)
  ├─ Celery Worker Service (4 Fargate tasks)
  ├─ Schedule F Scanner (Fargate task, EventBridge trigger)
  └─ Logs → CloudWatch Logs
```

**Deployment Strategy:**
- **Phase 1-3:** Manual SSH deployment (`./deploy.sh`)
- **Phase 4:** GitHub Actions → Build Docker image → Push to ECR → ECS rolling update

---

## 8. Speed vs. Scalability Tradeoffs

### Decision Matrix: Fast MVP vs. Scalable Architecture

| Component | Fast MVP (3-4 weeks) | Scalable Architecture (6-8 weeks) | **DECISION** |
|-----------|----------------------|-----------------------------------|--------------|
| **Backend** | Monolithic Python + FastAPI | Microservices (Node.js + Python + Go) | ✅ **Monolithic** — Volume doesn't justify microservices; Celery tasks can extract later |
| **Frontend** | No custom UI (Salesforce only) | React SPA for admin dashboard | ✅ **No custom UI** — Reps live in Salesforce; admin API sufficient for Keith |
| **Database** | PostgreSQL single instance | PostgreSQL + read replicas + sharding | ✅ **Single instance** — 1K writes/day doesn't need sharding; add replicas in Phase 4 |
| **Authentication** | API Key | OAuth 2.0 / OIDC | ✅ **API Key** — 1 admin user; OAuth overkill; upgrade Phase 4 if team grows |
| **Deployment** | Single EC2 instance | ECS Fargate with ALB | ✅ **EC2 instance** — Batch processing tolerates downtime; Fargate in Phase 4 |
| **Caching** | Redis for Celery only | Redis + CDN + database query cache | ✅ **Redis for Celery + API cache** — CDN not needed (no static assets); query cache Phase 4 |
| **Monitoring** | CloudWatch Logs + basic metrics | Full observability (Datadog, Sentry, tracing) | ⚠️ **Hybrid** — CloudWatch Logs + Sentry (error tracking); Datadog Phase 4 |

---

### Speed-First Decisions (Accepted Technical Debt)

**1. No Horizontal Scaling (Phase 1-3)**
- **Tradeoff:** Single EC2 instance = single point of failure
- **Justification:** Batch processing can tolerate 1-hour downtime (re-run PACER poll)
- **Mitigation:** CloudWatch alarms on instance health; auto-restart on crash
- **Payoff date:** Phase 4 (10x volume requires horizontal scaling)

**2. No Database Read Replicas**
- **Tradeoff:** All reads/writes hit primary database; potential bottleneck
- **Justification:** 1,000 writes/day + 5,000 reads/day = 0.07 QPS (PostgreSQL handles 1000+ QPS)
- **Mitigation:** Monitor database CPU/connections; add replica when CPU > 70%
- **Payoff date:** Phase 4 (10x volume = 0.7 QPS, still comfortable)

**3. No Custom Admin Dashboard**
- **Tradeoff:** Keith uses Salesforce + PACER + API calls; no unified UI
- **Justification:** Admin dashboard takes 2-3 weeks; delays Phase 1
- **Mitigation:** Salesforce reports for daily summaries; simple HTML page for manual triggers
- **Payoff date:** Phase 4 (when Keith requests better UX)

**4. Manual Deployment (SSH + systemctl restart)**
- **Tradeoff:** No CI/CD pipeline; manual deployments prone to human error
- **Justification:** Automated CI/CD takes 1 week to set up; delays Phase 1
- **Mitigation:** Deployment checklist, staging environment for testing
- **Payoff date:** After Phase 1 (set up GitHub Actions during Phase 2)

**5. OCR on CPU (No GPU Acceleration)**
- **Tradeoff:** Tesseract OCR on CPU is 5x slower than GPU-accelerated
- **Justification:** Only 5 Schedule F/week with scanned documents; 1 hour/week of OCR processing acceptable
- **Mitigation:** Manual review queue for low-confidence OCR; Keith approves before Salesforce push
- **Payoff date:** Phase 4 (50 Schedule F/week = 10 hours/week; GPU required)

---

### Scalability-First Decisions (Future-Proofing)

**1. Celery for Async Processing**
- **Why future-proof:** Celery architecture supports horizontal scaling (add workers when needed)
- **Cost now:** Adds Redis dependency ($75/mo), but necessary for queue management
- **Benefit later:** Phase 4 scaling is seamless (spin up 10 more worker instances)

**2. S3 for Document Storage**
- **Why future-proof:** S3 scales infinitely; no storage limits as volume grows
- **Cost now:** $10/mo for 10GB (negligible)
- **Benefit later:** Phase 4 (100GB documents) costs $23/mo vs. $300/mo for database storage

**3. PostgreSQL JSONB for API Responses**
- **Why future-proof:** Store raw PACER/ZoomInfo API responses for debugging; schema flexibility
- **Cost now:** Slight storage overhead (20% larger database)
- **Benefit later:** Can query historical API responses (e.g., "Which companies had different titles in ZoomInfo 6 months ago?")

**4. State-Based Territory Routing Logic**
- **Why future-proof:** Territory mapping stored in database (not hardcoded); supports future territory changes
- **Cost now:** Additional `territories` table + join logic
- **Benefit later:** Keith can reassign territories without code deployment

---

### **DECISION: Bias Toward Speed (80% Fast, 20% Scalable)**

**Rationale:**
1. **Uncertain product-market fit:** MVP validates demand; premature scaling wastes resources
2. **3-4 week deadline:** Client expects Phase 1 delivery; scalability can wait
3. **Celery as escape hatch:** Async architecture enables future horizontal scaling without rewrite
4. **Monitoring-driven scaling:** Add complexity only when metrics justify (CPU > 70%, processing time > 6 hours)

**Technical Debt Payback Plan:**
- **After Phase 1 (Week 5):** Set up CI/CD pipeline (GitHub Actions)
- **During Phase 2 (Weeks 6-7):** Add Sentry for error tracking
- **After Phase 3 (Week 10):** Add database monitoring (slow query log, connection pool metrics)
- **Phase 4 Trigger:** When daily processing time > 6 hours OR ZoomInfo rate limits hit

---

## 9. Cost Optimization

### Phase 1-3 Monthly Cost Breakdown

| Component | Service | Spec | Monthly Cost |
|-----------|---------|------|--------------|
| **Compute** | EC2 t3.medium | 2 vCPU, 4GB RAM | $35 |
| **Database** | RDS PostgreSQL db.t3.micro | 2 vCPU, 1GB RAM, 20GB storage | $15 |
| **Cache** | ElastiCache Redis cache.t3.micro | 2 vCPU, 0.5GB RAM | $12 |
| **Storage** | S3 Standard | 10GB documents | $0.23 |
| **Network** | Data transfer | 50GB/month | $4.50 |
| **Monitoring** | CloudWatch Logs | 5GB ingestion, 1-month retention | $2.50 |
| **DNS** | Route 53 | 1 hosted zone | $0.50 |
| **Secrets** | AWS Secrets Manager | 4 secrets | $1.60 |
| **Error Tracking** | Sentry (Basic) | 5K events/month | $26 |
| **Total Infrastructure** | | | **$97.33/month** |
| | | | |
| **External APIs** | | | |
| PACER Documents | 50 filings/day × 30 days × $4.50 | | $6,750/month* |
| ZoomInfo API | 1,000 lookups/day × 30 days × $0.10** | | $3,000/month* |
| Salesforce API | Included in existing license | | $0 |
| **Total External APIs** | | | **$9,750/month** |
| | | | |
| **GRAND TOTAL** | | | **$9,847/month** |

*PACER and ZoomInfo costs are estimated; actual costs depend on usage patterns*  
**ZoomInfo pricing is per-contract; assuming $0.10/lookup for estimation*

---

### Cost Optimization Strategies

#### 1. PACER Document Costs (Largest Expense)

**Current:** $6,750/month (50 filings/day × $4.50/document average)

**Optimization:**
- ✅ **Human-in-the-loop approval:** Keith approves Schedule F purchases; rejects low-value cases (e.g., small mom-and-pop filings in non-target states)
- ✅ **Geographic filtering:** Pre-screen debtor location; skip cases in low-value states (New Mexico, Wyoming)
- ✅ **Creditor count estimation:** Parse docket summary for estimated creditor count; reject < 50 creditors
- ✅ **Document type filtering:** Only download Schedule E/F (creditor lists); skip unnecessary docket entries

**Expected Savings:** 30% reduction → $4,725/month (reject 15 out of 50 Schedule F purchases)

---

#### 2. ZoomInfo API Costs (Second Largest)

**Current:** $3,000/month (1,000 lookups/day × $0.10/lookup)

**Optimization:**
- ✅ **Redis caching:** Cache ZoomInfo responses for 7 days; same company across multiple filings = cache hit
  - **Cache hit rate:** 40% (400 duplicate companies/day)
  - **Savings:** $1,200/month → **$1,800/month after caching**
- ✅ **Batch API requests:** ZoomInfo offers batch lookups (50 companies/request) at 20% discount
  - **Savings:** Additional $360/month → **$1,440/month total**
- ✅ **Filter individuals before enrichment:** Don't look up individual creditors (only companies)
  - **Savings:** 20% reduction in lookups → **$1,152/month total**

**Expected Savings:** 62% reduction → $1,152/month

---

#### 3. Infrastructure Costs (Smallest, But Optimizable)

**Current:** $97/month

**Optimization:**
- ✅ **Reserved Instances:** 1-year RI for EC2 t3.medium = 40% discount → $21/month (save $14/month)
- ✅ **RDS Multi-AZ disabled:** Phase 1-3 tolerates downtime; disable Multi-AZ → save $15/month
- ✅ **S3 Intelligent-Tiering:** Auto-move old documents (> 90 days) to Glacier → save $5/month (as volume grows)
- ✅ **CloudWatch Logs retention:** 1-week retention instead of 1-month → save $1.50/month

**Expected Savings:** $35.50/month → **$61.50/month infrastructure**

---

### Optimized Phase 1-3 Cost Breakdown

| Category | Before Optimization | After Optimization | Savings |
|----------|---------------------|-------------------|---------|
| Infrastructure | $97/month | $62/month | $35/month (36%) |
| PACER Documents | $6,750/month | $4,725/month | $2,025/month (30%) |
| ZoomInfo API | $3,000/month | $1,152/month | $1,848/month (62%) |
| **TOTAL** | **$9,847/month** | **$5,939/month** | **$3,908/month (40%)** |

**Annual Savings:** $46,896/year

**Business Case Validation:**
- **Manual process cost:** $75K/year (full-time prospecting hire)
- **Automated system cost:** $71,268/year ($5,939/month × 12)
- **Savings:** $3,732/year (5% cheaper than manual)
- **Plus intangible benefits:** 10x lead volume, zero missed Schedule F, 50% rep time savings

---

### Phase 4 (10x Scale) Cost Projection

**Volume Increase:** 10x (500 filings/day, 10,000 creditors/day)

| Category | Phase 1-3 | Phase 4 (10x) | Cost Increase |
|----------|-----------|---------------|---------------|
| Infrastructure | $62/month | $450/month | 7.3x (not linear — economies of scale) |
| PACER Documents | $4,725/month | $47,250/month | 10x (linear with volume) |
| ZoomInfo API | $1,152/month | $11,520/month | 10x (linear with volume) |
| **TOTAL** | **$5,939/month** | **$59,220/month** | **10x** |

**Cost Per Creditor:**
- Phase 1-3: $5,939 / 8,500 creditors = **$0.70 per creditor**
- Phase 4: $59,220 / 85,000 creditors = **$0.70 per creditor** (same unit economics!)

**Conclusion:** System scales cost-efficiently; infrastructure costs grow sub-linearly while API costs scale linearly

---

## 10. Security Considerations

### Threat Model

**Assets to Protect:**
1. **PACER credentials** — Unauthorized access = fraudulent document purchases
2. **ZoomInfo API keys** — Theft = API abuse, quota exhaustion
3. **Salesforce OAuth tokens** — Unauthorized access = data breach, lead manipulation
4. **Creditor PII** — Names, addresses, claim amounts (not SSN/credit card, but still sensitive)
5. **Admin API** — Unauthorized access = trigger fraudulent PACER polls, manipulate purchase approvals

**Threat Actors:**
1. **External attackers** — Attempt to steal API keys, access database
2. **Compromised EC2 instance** — Malware, supply chain attack on dependencies
3. **Insider threat** — Malicious employee (low risk; 1-2 person team)
4. **Accidental exposure** — API keys committed to GitHub, logs containing credentials

---

### Security Controls

#### 1. Credential Management (High Priority)

**Threat:** API keys hardcoded in code, committed to GitHub

**Controls:**
- ✅ **AWS Secrets Manager:** All credentials stored encrypted at rest (AES-256)
- ✅ **IAM roles:** EC2 instance uses IAM role to access Secrets Manager (no long-lived access keys)
- ✅ **Automatic rotation:** PACER/ZoomInfo credentials rotated every 90 days via Secrets Manager
- ✅ **Audit logging:** CloudTrail logs every Secrets Manager access (who, when, which secret)
- ✅ **No plaintext logs:** Mask credentials in application logs (`PACER_USER=p***@example.com`)

**Implementation:**
```python
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise

pacer_creds = get_secret('prod/pacer/credentials')
PACER_USERNAME = pacer_creds['username']
PACER_PASSWORD = pacer_creds['password']
```

---

#### 2. Network Security (High Priority)

**Threat:** Public EC2 instance exposed to internet; unauthorized API access

**Controls:**
- ✅ **VPC with private subnets:** EC2, RDS, Redis in private subnets (no public IPs)
- ✅ **Bastion host:** SSH access only via bastion host in public subnet
- ✅ **Security groups:** Restrictive ingress rules
  - API: Allow only from Application Load Balancer (if added later)
  - RDS: Allow only from EC2 security group (port 5432)
  - Redis: Allow only from EC2 security group (port 6379)
  - SSH: Allow only from bastion host (port 22)
- ✅ **HTTPS only:** API exposed only via HTTPS (TLS 1.2+); redirect HTTP → HTTPS
- ✅ **Rate limiting:** Nginx rate limit (100 requests/minute per IP) to prevent brute force

**Network Diagram:**
```
Internet
  ↓
NAT Gateway (public subnet)
  ↓
EC2 Instance (private subnet)
  ↓
RDS + Redis (private subnet, no internet access)
```

---

#### 3. API Authentication (Medium Priority)

**Threat:** Unauthorized access to admin API endpoints

**Controls:**
- ✅ **API Key authentication:** Admin endpoints require `X-API-Key` header
- ✅ **Key rotation:** Admin API key rotated every 90 days
- ✅ **IP allowlist (optional):** Restrict admin API to Keith's office IP (if static)
- ✅ **Audit logging:** Log every admin API call (timestamp, endpoint, result) to CloudWatch

**Implementation:**
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    secret = get_secret('prod/admin/api-key')
    if api_key != secret['api_key']:
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

---

#### 4. Data Encryption (Medium Priority)

**Threat:** Database breach exposes creditor PII

**Controls:**
- ✅ **Encryption at rest:** RDS encrypted with AWS KMS (AES-256)
- ✅ **Encryption in transit:** PostgreSQL SSL connections enforced (`sslmode=require`)
- ✅ **S3 encryption:** Server-side encryption (SSE-S3) for all documents
- ✅ **Backup encryption:** RDS automated backups encrypted with same KMS key

**Sensitive Data Fields:**
- `creditors.name` — Encrypted? No (needed for fuzzy matching)
- `creditors.address` — Encrypted? No (needed for ZoomInfo lookup)
- `creditors.claim_amount` — Encrypted? No (aggregated for historical exposure)
- `pacer_credentials` — Encrypted? Yes (Secrets Manager)

**Decision:** No field-level encryption in database (performance overhead, complicates querying); rely on infrastructure encryption (RDS, S3)

---

#### 5. Dependency Security (Medium Priority)

**Threat:** Vulnerable Python packages (e.g., PyYAML deserialization vulnerability)

**Controls:**
- ✅ **Dependabot alerts:** GitHub Dependabot scans `requirements.txt` for CVEs
- ✅ **Safety tool:** Run `safety check` in CI/CD to detect insecure packages
- ✅ **Pin versions:** `requirements.txt` pins exact versions (no `package>=1.0`)
- ✅ **Regular updates:** Review and update dependencies quarterly

**Example CI/CD Check:**
```yaml
# .github/workflows/security.yml
name: Security Checks
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install Safety
        run: pip install safety
      - name: Check for vulnerabilities
        run: safety check -r requirements.txt
```

---

#### 6. Access Control (Low Priority for MVP)

**Threat:** Reps can see leads outside their territory (data leak)

**Controls:**
- ✅ **Salesforce RBAC:** Territory-based record access rules in Salesforce
- ✅ **Database-level RLS (future):** PostgreSQL Row-Level Security (RLS) policies (Phase 4)
- ⚠️ **No API-level access control (MVP):** Admin API has no per-user permissions (Keith is only user)

**Phase 4 Enhancement:** Implement OAuth 2.0 with Salesforce SSO; API checks user's territory before returning data

---

#### 7. Logging and Monitoring (High Priority)

**Threat:** Security incident goes undetected for days/weeks

**Controls:**
- ✅ **Centralized logging:** All application logs → CloudWatch Logs
- ✅ **Security event alerts:** CloudWatch Alarms on suspicious events
  - Failed API key authentication (> 10/hour)
  - Secrets Manager access from unknown IAM role
  - RDS connection from non-EC2 IP
- ✅ **Error tracking:** Sentry captures all application errors (including stack traces)
- ✅ **Audit trail:** Log all admin actions (PACER poll triggers, Schedule F approvals)

**Example CloudWatch Alarm:**
```python
# Alert on failed API key attempts
import boto3
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_alarm(
    AlarmName='InvalidAPIKeyAttempts',
    MetricName='InvalidAPIKey',
    Threshold=10,
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=1,
    Period=3600,  # 1 hour
    Statistic='Sum',
    ActionsEnabled=True,
    AlarmActions=['arn:aws:sns:us-east-1:123456789:security-alerts']
)
```

---

### Security Checklist (Pre-Launch)

| Control | Status | Owner | Deadline |
|---------|--------|-------|----------|
| ✅ Credentials in Secrets Manager | ✅ Done | DevOps | Phase 1 |
| ✅ VPC with private subnets | ✅ Done | DevOps | Phase 1 |
| ✅ RDS encryption at rest | ✅ Done | DevOps | Phase 1 |
| ✅ API Key authentication | ✅ Done | Backend | Phase 1 |
| ✅ HTTPS only (TLS 1.2+) | ✅ Done | DevOps | Phase 1 |
| ✅ CloudWatch logging | ✅ Done | Backend | Phase 1 |
| ✅ Sentry error tracking | ✅ Done | Backend | Phase 1 |
| ⏳ Dependabot + Safety checks | 🔜 To-Do | DevOps | Phase 2 |
| ⏳ Security group audit | 🔜 To-Do | DevOps | Phase 2 |
| ⏳ Secrets rotation testing | 🔜 To-Do | DevOps | Phase 3 |

---

## 11. Final Architecture Recommendation

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         EXTERNAL APIS                        │
├─────────────────────────────────────────────────────────────┤
│  PACER API     │   ZoomInfo API   │   Salesforce API        │
└────────┬────────────────┬──────────────────┬─────────────────┘
         │                │                  │
         ├────────────────┴──────────────────┤
         │                                   │
┌────────▼───────────────────────────────────▼────────────────┐
│                    APPLICATION LAYER                         │
│                 (EC2 t3.medium, Private Subnet)              │
├──────────────────────────────────────────────────────────────┤
│  FastAPI (REST API)                                          │
│    ├─ Admin Endpoints (API Key auth)                         │
│    └─ Health Check Endpoint                                  │
│                                                               │
│  Celery Workers (4 workers)                                  │
│    ├─ PACER Polling Job (daily at 2am)                       │
│    ├─ Document Parsing Job (on-demand)                       │
│    ├─ ZoomInfo Enrichment Job (batch, Redis cache)           │
│    ├─ Salesforce Push Job (on-demand)                        │
│    └─ Schedule F Scanner Job (weekly cron)                   │
└────────┬──────────────────────────┬────────────────────┬────┘
         │                          │                    │
         │                          │                    │
┌────────▼──────────┐  ┌───────────▼─────────┐  ┌──────▼──────┐
│  PostgreSQL       │  │  Redis              │  │  S3         │
│  (RDS db.t3.micro)│  │  (ElastiCache       │  │  (Documents)│
│                   │  │   cache.t3.micro)   │  │             │
│  • bankruptcies   │  │  • Celery broker    │  │  • Raw PDFs │
│  • creditors      │  │  • API cache        │  │  • OCR      │
│  • contacts       │  │  • Rate limits      │  │    outputs  │
│  • processing_jobs│  │  • Monitoring queue │  │             │
└───────────────────┘  └─────────────────────┘  └─────────────┘
```

---

### Technology Stack

**Backend:**
- **Language:** Python 3.11
- **Web Framework:** FastAPI 0.109+
- **Task Queue:** Celery 5.3+ with Redis broker
- **ORM:** SQLAlchemy 2.0 (async support)
- **PDF Parsing:** PyPDF2 + pdfplumber
- **OCR:** Tesseract 5.0 via pytesseract
- **NLP:** spaCy for entity extraction + fuzzy matching
- **HTTP Client:** httpx (async) for API calls

**Frontend:**
- **Admin UI:** None (Salesforce only)
- **Optional:** Simple HTML page for manual triggers (FastAPI Jinja2 templates)

**Database:**
- **Primary:** PostgreSQL 15 (RDS db.t3.micro)
- **Cache:** Redis 7.0 (ElastiCache cache.t3.micro)
- **Document Storage:** S3 Standard (lifecycle → Glacier after 90 days)

**Infrastructure:**
- **Compute:** EC2 t3.medium (Ubuntu 22.04 LTS)
- **Deployment:** SSH + systemd (Phase 1-3) → ECS Fargate (Phase 4)
- **Networking:** VPC with private subnets, NAT Gateway
- **Secrets:** AWS Secrets Manager with automatic rotation
- **Monitoring:** CloudWatch Logs + Sentry error tracking
- **DNS:** Route 53

**External APIs:**
- **PACER:** Court document retrieval
- **ZoomInfo:** Company enrichment + contact data
- **Salesforce:** CRM integration (account creation, territory routing)

---

### Deployment Architecture (Phase 1-3)

```
┌──────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                            │
├──────────────────────────────────────────────────────────────┤
│  Region: us-east-1                                           │
│  VPC: 10.0.0.0/16                                            │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Public Subnet (10.0.1.0/24)                             ││
│  │   └─ NAT Gateway (internet access for private subnet)  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Private Subnet (10.0.2.0/24)                            ││
│  │   ├─ EC2 t3.medium (Application)                        ││
│  │   ├─ RDS PostgreSQL (db.t3.micro)                       ││
│  │   └─ ElastiCache Redis (cache.t3.micro)                 ││
│  └─────────────────────────────────────────────────────────┘│
│                                                               │
│  S3 Bucket: bankruptcy-creditor-docs (us-east-1)             │
│  Secrets Manager: 4 secrets (PACER, ZoomInfo, Salesforce)    │
│  CloudWatch Logs: /aws/ec2/bankruptcy-creditor-intelligence  │
└──────────────────────────────────────────────────────────────┘
```

---

### Data Flow (End-to-End)

**Daily Top 20 Processing:**
1. **2:00 AM EST:** Celery scheduled job triggers PACER polling
2. **PACER API:** Fetch new Chapter 11 filings from previous day (target states)
3. **Document Download:** Download Form 201 (petition) + Form 204 (top 20 creditors) → S3
4. **Parsing:** Extract debtor metadata + creditor list (PyPDF2)
5. **Classification:** Company vs. individual (spaCy NER + entity suffix matching)
6. **Redis Cache Check:** Check if company already enriched (cache key: company name + address)
7. **ZoomInfo API:** Enrich companies (firmographics + contacts) — skip cache hits
8. **PostgreSQL Insert:** Save bankruptcy + creditors + contacts
9. **Salesforce API:** Create/update accounts, log bankruptcy events, route to territory reps
10. **Outreach Check:** If net-new qualified lead (no DNC, no active engagement) → trigger email
11. **8:00 AM EST:** Keith receives daily summary email (bankruptcy count, creditor count, errors)

**Schedule F Monitoring:**
1. **Every Monday 3:00 AM:** Celery scheduled job scans active cases
2. **PostgreSQL Query:** SELECT cases in `schedule_f_queue` WHERE `last_scanned_at` < NOW() - INTERVAL '7 days'
3. **PACER API:** Fetch docket for each case (concurrent requests, 10 cases in parallel)
4. **Keyword Detection:** Search docket entries for "Schedule F", "Schedule E/F", "206F"
5. **If detected:** Extract page count, estimate cost, save to `schedule_f_queue.status = 'pending_approval'`
6. **Alert:** Add to Keith's PACER favorites (via PACER API)
7. **Keith's action:** Review in PACER, unfavorite to reject OR leave favorited to approve
8. **Hourly sync (9am-5pm):** Celery job checks PACER favorites, downloads approved documents
9. **Parsing:** Multi-format parsing (structured → pdfplumber, OCR → Tesseract)
10. **Deduplication:** Fuzzy match on creditor name within filing
11. **Proceed to step 5 of Daily Processing (classification → enrichment → Salesforce)**

---

### Scaling Roadmap

**Phase 1-3 (Current):**
- Volume: 50 filings/day, 1,000 creditors/day
- Infrastructure: Single EC2 t3.medium
- Cost: $5,939/month
- **Scaling trigger:** Processing time > 6 hours/day OR CPU > 70%

**Phase 4 (10x Scale):**
- Volume: 500 filings/day, 10,000 creditors/day
- Infrastructure:
  - FastAPI: 2x t3.small (behind ALB)
  - Celery Workers: 4x t3.medium (general) + 2x g4dn.xlarge (OCR with GPU)
  - PostgreSQL: db.t3.large with read replica
  - Redis: cache.t3.medium with replication
- Cost: $59,220/month
- **Scaling trigger:** ZoomInfo rate limit hit OR OCR processing > 10 hours/week

**Phase 5 (100x Scale — Future):**
- Volume: 5,000 filings/day, 100,000 creditors/day
- Infrastructure:
  - EKS cluster (Kubernetes)
  - Aurora PostgreSQL Serverless v2 (auto-scaling)
  - ElastiCache Redis Cluster (sharded)
  - S3 + CloudFront (document delivery)
- Cost: TBD (estimate $100K-150K/month)

---

### Risk Mitigation Summary

| Risk | Mitigation | Owner |
|------|-----------|-------|
| **PACER API downtime** | Retry logic (3 attempts, exponential backoff); alert on failure | Backend |
| **ZoomInfo rate limit** | Redis caching (40% hit rate); batch API requests; alert at 80% quota | Backend |
| **Salesforce API failure** | Queue for retry; continue processing other leads; alert on persistent failure | Backend |
| **OCR accuracy < 95%** | Manual review queue for low-confidence results; Keith approves before Salesforce | Product |
| **EC2 instance failure** | CloudWatch alarm → SNS → manual restart (1-hour downtime acceptable) | DevOps |
| **Database storage full** | CloudWatch alarm at 80% capacity; manual resize RDS instance | DevOps |
| **Credential leak** | Secrets Manager rotation; audit CloudTrail logs; revoke on detection | Security |
| **Cost overrun** | Monthly budget alerts; Keith approval for Schedule F purchases; ZoomInfo cache | Finance |

---

### Success Criteria (Launch Checklist)

**Functional:**
- ✅ Daily PACER polling processes 50 filings within 24 hours
- ✅ Top 20 creditor extraction accuracy ≥ 95%
- ✅ ZoomInfo enrichment match rate ≥ 80%
- ✅ Schedule F detection within 7 days of filing (zero missed)
- ✅ Salesforce account creation with territory routing (100% correct)
- ✅ Do-not-contact suppression (100% respected)
- ✅ Automated outreach triggering (net-new qualified leads)

**Non-Functional:**
- ✅ API response time < 500ms (p95)
- ✅ Database CPU < 50% (sustained)
- ✅ Redis memory < 60%
- ✅ Zero security vulnerabilities (Safety check passes)
- ✅ Centralized logging (CloudWatch Logs + Sentry)
- ✅ Monthly cost < $7,000 (infrastructure + APIs)

**Operational:**
- ✅ Deployment script tested (`./deploy.sh`)
- ✅ Rollback procedure documented
- ✅ CloudWatch alarms configured (CPU, memory, disk, API failures)
- ✅ Sentry error tracking active (5K events/month limit)
- ✅ Keith trained on PACER favorites approval workflow
- ✅ Salesforce custom objects/fields created
- ✅ Territory mapping configured in Salesforce

---

**End of Technical Architecture Debate**
