# Jira Backlog Structure — AU Group
## Bankruptcy Creditor Intelligence Platform

**Jira Cloud project key:** `KD` — [Software board](https://automationarchitecture.atlassian.net/jira/software/projects/KD/boards/451)  
**Project name:** AU Group — Bankruptcy Creditor Intelligence  
**Backlog doc IDs:** `AU_GROUP-*` below are logical epic/story labels from discovery (AU Group); create and track work in Jira under **`KD-*`** (same structure, project key differs).
**Version:** 1.0  
**Date:** March 12, 2026

---

## Table of Contents

1. [Epic Overview](#epic-overview)
2. [Phase 1: Daily Pipeline Foundation](#phase-1-daily-pipeline-foundation-weeks-1-4)
3. [Phase 2: Schedule F Monitoring](#phase-2-schedule-f-monitoring-weeks-5-7)
4. [Phase 3: Historical Database](#phase-3-historical-database-weeks-8-9)
5. [Phase 0: Infrastructure & Setup](#phase-0-infrastructure--setup-week-0)
6. [Continuous: QA & DevOps](#continuous-qa--devops)
7. [Sprint Planning](#sprint-planning)
8. [Dependency Matrix](#dependency-matrix)

---

## Epic Overview

| Epic ID | Epic Name | Priority | Story Points | Sprint Target | Phase |
|---------|-----------|----------|--------------|---------------|-------|
| **AU_GROUP-1** | Infrastructure Setup & AWS Configuration | Highest | 23 | Sprint 1 | Phase 0 |
| **AU_GROUP-2** | PACER Filing Monitor & Document Download | Highest | 34 | Sprint 2-3 | Phase 1 |
| **AU_GROUP-3** | Document Parsing Engine | Highest | 55 | Sprint 3-4 | Phase 1 |
| **AU_GROUP-4** | ZoomInfo Enrichment Pipeline | Highest | 34 | Sprint 4-5 | Phase 1 |
| **AU_GROUP-5** | Salesforce Integration | Highest | 55 | Sprint 5-6 | Phase 1 |
| **AU_GROUP-6** | Schedule F Monitoring Queue | High | 55 | Sprint 7-8 | Phase 2 |
| **AU_GROUP-7** | Historical Database Import & Exposure Tracking | Medium | 34 | Sprint 9 | Phase 3 |
| **AU_GROUP-8** | DevOps, Monitoring & Security | Highest | 21 | Continuous | All |

**Total Story Points:** 311 points  
**Estimated Duration:** 9 sprints (18 weeks / ~4.5 months)  
**Target for Phase 1-3 MVP:** 9 sprints

---

## Phase 0: Infrastructure & Setup (Week 0)

### Epic AU_GROUP-1: Infrastructure Setup & AWS Configuration

**Epic Description:** Set up AWS infrastructure, networking, database, and core services required for the platform.

**Epic Acceptance Criteria:**
- ✅ VPC with public/private subnets configured
- ✅ EC2 instance provisioned and accessible via bastion
- ✅ RDS PostgreSQL database created with encryption
- ✅ Redis ElastiCache cluster running
- ✅ S3 bucket created with lifecycle policies
- ✅ AWS Secrets Manager configured with credentials
- ✅ All services communicating securely

---

### Story AU_GROUP-1.1: AWS VPC & Network Configuration (Backend/Infrastructure)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `infrastructure`, `aws`, `networking`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** None

**Description:**
As a DevOps engineer, I need to set up a secure VPC with public and private subnets so that the application runs in an isolated network environment with controlled internet access.

**Acceptance Criteria:**
- ✅ VPC created with CIDR block 10.0.0.0/16
- ✅ Public subnet (10.0.1.0/24) with NAT Gateway for outbound internet
- ✅ Private subnet (10.0.2.0/24) for EC2, RDS, Redis
- ✅ Security groups configured with restrictive ingress rules
- ✅ Route tables configured correctly (private → NAT, public → IGW)
- ✅ VPC Flow Logs enabled to CloudWatch

**Tasks:**

#### Task AU_GROUP-1.1.1: Create VPC and Subnets
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `infrastructure`, `aws-vpc`

**Subtasks:**
- Create VPC with CIDR 10.0.0.0/16
- Create public subnet 10.0.1.0/24 in us-east-1a
- Create private subnet 10.0.2.0/24 in us-east-1a
- Enable DNS hostnames and DNS resolution

**Acceptance Criteria:**
- VPC created with correct CIDR block
- Both subnets created and available

---

#### Task AU_GROUP-1.1.2: Configure NAT Gateway and Internet Gateway
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `infrastructure`, `aws-networking`

**Subtasks:**
- Create Internet Gateway and attach to VPC
- Allocate Elastic IP for NAT Gateway
- Create NAT Gateway in public subnet
- Verify NAT Gateway is in "available" state

**Acceptance Criteria:**
- Internet Gateway attached to VPC
- NAT Gateway running in public subnet
- Elastic IP associated

---

#### Task AU_GROUP-1.1.3: Configure Security Groups
**Assignee:** DevOps Engineer  
**Story Points:** 1  
**Labels:** `infrastructure`, `security`

**Subtasks:**
- Create EC2 security group (SSH from bastion, HTTPS outbound)
- Create RDS security group (PostgreSQL from EC2 only)
- Create Redis security group (Redis from EC2 only)
- Create bastion security group (SSH from specific IP)

**Acceptance Criteria:**
- All security groups created with documented rules
- Ingress rules are restrictive (no 0.0.0.0/0 except bastion)
- Tags applied for identification

---

### Story AU_GROUP-1.2: EC2 Instance Provisioning (Backend/Infrastructure)

**Priority:** Highest  
**Story Points:** 3  
**Labels:** `infrastructure`, `aws-ec2`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** AU_GROUP-1.1 (VPC setup)

**Description:**
As a DevOps engineer, I need to provision an EC2 instance in the private subnet so that the application can run securely without direct internet exposure.

**Acceptance Criteria:**
- ✅ EC2 t3.medium instance running Ubuntu 22.04 LTS
- ✅ Instance placed in private subnet with no public IP
- ✅ IAM role attached with permissions for Secrets Manager, S3, CloudWatch
- ✅ SSH access working via bastion host
- ✅ System packages updated, Python 3.11 installed
- ✅ CloudWatch Logs agent configured

**Tasks:**

#### Task AU_GROUP-1.2.1: Provision EC2 Instance
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `infrastructure`, `aws-ec2`

**Subtasks:**
- Launch t3.medium with Ubuntu 22.04 AMI
- Attach IAM role with required permissions
- Configure 30GB EBS gp3 volume
- Add tags (Name, Environment, Project)
- Verify instance state is "running"

**Acceptance Criteria:**
- Instance accessible via bastion SSH
- IAM role permissions verified (can access Secrets Manager)

---

#### Task AU_GROUP-1.2.2: Install System Dependencies
**Assignee:** Backend Engineer  
**Story Points:** 1  
**Labels:** `infrastructure`, `setup`

**Subtasks:**
- Update apt packages (`apt update && apt upgrade`)
- Install Python 3.11, pip, virtualenv
- Install Tesseract OCR (for document processing)
- Install Nginx (reverse proxy)
- Install system monitoring tools (htop, iotop)

**Acceptance Criteria:**
- Python 3.11 installed and default
- Tesseract OCR working (`tesseract --version`)
- All system dependencies documented in `docs/setup.md`

---

### Story AU_GROUP-1.3: RDS PostgreSQL Database Setup (Backend/Infrastructure)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `infrastructure`, `database`, `aws-rds`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** AU_GROUP-1.1 (VPC setup)

**Description:**
As a backend engineer, I need a PostgreSQL database configured with encryption and proper networking so that the application can store creditor data securely.

**Acceptance Criteria:**
- ✅ RDS PostgreSQL 15 instance running (db.t3.micro)
- ✅ Database accessible from EC2 instance only
- ✅ Encryption at rest enabled (AWS KMS)
- ✅ SSL/TLS enforced for connections
- ✅ Automated daily backups configured (7-day retention)
- ✅ Initial schema applied (tables, indexes, extensions)

**Tasks:**

#### Task AU_GROUP-1.3.1: Create RDS PostgreSQL Instance
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `infrastructure`, `aws-rds`

**Subtasks:**
- Create RDS instance (PostgreSQL 15, db.t3.micro, 20GB gp3)
- Enable encryption at rest (AWS KMS default key)
- Configure security group (port 5432 from EC2 security group only)
- Set master username/password (store in Secrets Manager)
- Enable automated backups (7-day retention)

**Acceptance Criteria:**
- RDS instance status "available"
- Connection working from EC2 instance
- Master credentials stored in Secrets Manager

---

#### Task AU_GROUP-1.3.2: Apply Database Schema
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `database`, `schema`

**Subtasks:**
- Create Alembic migration: initial schema
- Create tables: bankruptcies, creditors, bankruptcy_creditors, zoom_info_contacts, salesforce_accounts, processing_jobs, schedule_f_queue
- Create indexes: filing_date, state, creditor_name (GIN for fuzzy matching)
- Enable PostgreSQL extensions: uuid-ossp, pg_trgm
- Run migration on RDS instance

**Acceptance Criteria:**
- All tables created with correct schema
- Indexes created and verified (`\di` in psql)
- Extensions enabled (`\dx` shows uuid-ossp, pg_trgm)
- Schema documented in `docs/database-schema.md`

---

### Story AU_GROUP-1.4: Redis ElastiCache Configuration (Backend/Infrastructure)

**Priority:** Highest  
**Story Points:** 3  
**Labels:** `infrastructure`, `cache`, `aws-elasticache`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** AU_GROUP-1.1 (VPC setup)

**Description:**
As a backend engineer, I need a Redis instance configured for Celery task queue and API response caching so that async jobs can be processed reliably.

**Acceptance Criteria:**
- ✅ ElastiCache Redis 7.0 cluster running (cache.t3.micro)
- ✅ Redis accessible from EC2 instance only
- ✅ TLS encryption in transit enabled
- ✅ Redis AUTH password set (stored in Secrets Manager)
- ✅ Celery broker connection working
- ✅ Basic cache operations verified (SET/GET)

**Tasks:**

#### Task AU_GROUP-1.4.1: Create ElastiCache Redis Cluster
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `infrastructure`, `aws-elasticache`

**Subtasks:**
- Create Redis 7.0 cluster (cache.t3.micro, single node)
- Configure security group (port 6379 from EC2 security group only)
- Enable in-transit encryption (TLS)
- Set AUTH token (store in Secrets Manager)
- Configure eviction policy (allkeys-lru)

**Acceptance Criteria:**
- Redis cluster status "available"
- Connection working from EC2 via `redis-cli` with TLS + AUTH

---

#### Task AU_GROUP-1.4.2: Configure Celery Broker Connection
**Assignee:** Backend Engineer  
**Story Points:** 1  
**Labels:** `backend`, `celery`

**Subtasks:**
- Install celery + redis Python packages
- Configure Celery broker URL (rediss:// for TLS)
- Test Celery connection (`celery -A app inspect ping`)
- Document Celery configuration in `app/config.py`

**Acceptance Criteria:**
- Celery can connect to Redis broker
- Test task can be queued and executed

---

### Story AU_GROUP-1.5: S3 Bucket & Lifecycle Policies (Backend/Infrastructure)

**Priority:** High  
**Story Points:** 2  
**Labels:** `infrastructure`, `storage`, `aws-s3`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** AU_GROUP-1.1 (VPC setup)

**Description:**
As a backend engineer, I need an S3 bucket configured with lifecycle policies so that raw PACER documents can be stored cost-effectively.

**Acceptance Criteria:**
- ✅ S3 bucket created with versioning enabled
- ✅ Server-side encryption (SSE-S3) enabled
- ✅ Folder structure created (raw-documents/, parsed-outputs/, ocr-outputs/)
- ✅ Lifecycle policy: Standard → Glacier after 90 days
- ✅ IAM policy allows EC2 instance to read/write
- ✅ Test file upload/download working

**Tasks:**

#### Task AU_GROUP-1.5.1: Create S3 Bucket with Encryption
**Assignee:** DevOps Engineer  
**Story Points:** 1  
**Labels:** `infrastructure`, `aws-s3`

**Subtasks:**
- Create S3 bucket: `bankruptcy-creditor-docs`
- Enable versioning
- Enable server-side encryption (SSE-S3, AES-256)
- Block public access (all blocks enabled)
- Add tags (Project, Environment)

**Acceptance Criteria:**
- Bucket created with encryption + versioning
- Public access blocked
- IAM policy attached to EC2 role

---

#### Task AU_GROUP-1.5.2: Configure Lifecycle Policies
**Assignee:** DevOps Engineer  
**Story Points:** 1  
**Labels:** `infrastructure`, `aws-s3`

**Subtasks:**
- Create lifecycle rule: raw-documents/ → Glacier after 90 days
- Create lifecycle rule: ocr-outputs/ → delete after 365 days
- Create lifecycle rule: parsed-outputs/ → delete after 365 days
- Verify lifecycle rules applied

**Acceptance Criteria:**
- Lifecycle policies configured correctly
- Test file transitions verified (can test with short duration in staging)

---

### Story AU_GROUP-1.6: AWS Secrets Manager Configuration (Backend/Infrastructure)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `infrastructure`, `security`, `aws-secrets`, `phase-0`  
**Sprint:** Sprint 1  
**Dependencies:** None

**Description:**
As a backend engineer, I need all credentials stored in AWS Secrets Manager with automatic rotation so that API keys and passwords are never hardcoded.

**Acceptance Criteria:**
- ✅ Secrets created for PACER, ZoomInfo, Salesforce, Admin API Key
- ✅ EC2 IAM role can read secrets
- ✅ Python code can fetch secrets successfully
- ✅ Rotation policy configured (90 days)
- ✅ CloudTrail logging enabled for secret access

**Tasks:**

#### Task AU_GROUP-1.6.1: Create Secrets in Secrets Manager
**Assignee:** DevOps Engineer  
**Story Points:** 1  
**Labels:** `infrastructure`, `security`

**Subtasks:**
- Create secret: `/prod/pacer/credentials` (username, password)
- Create secret: `/prod/zoominfo/api-key` (api_key)
- Create secret: `/prod/salesforce/oauth` (client_id, client_secret, refresh_token, instance_url)
- Create secret: `/prod/admin/api-key` (api_key)
- Set rotation period: 90 days (manual rotation for MVP)

**Acceptance Criteria:**
- All 4 secrets created and encrypted
- EC2 IAM role has `secretsmanager:GetSecretValue` permission

---

#### Task AU_GROUP-1.6.2: Implement Secret Fetching in Application
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `security`

**Subtasks:**
- Install boto3 SDK
- Create `app/secrets.py` module with `get_secret()` function
- Cache secrets in memory (avoid repeated API calls)
- Handle exceptions (secret not found, access denied)
- Write unit tests for secret fetching

**Acceptance Criteria:**
- Application can fetch all secrets successfully
- Secrets cached in memory (not fetched on every request)
- Unit tests passing

---

#### Task AU_GROUP-1.6.3: Gather Production Credentials for Salesforce and ZoomInfo (Client / PM)

**Assignee:** PM / Operator (client-facing)  
**Story Points:** 2  
**Labels:** `client`, `salesforce`, `zoominfo`, `credentials`, `blocking`, `phase-0`  
**Sprint:** Sprint 1 (or current sprint)  
**Dependencies:** None (runs in parallel with secret scaffolding; **blocks** AU_GROUP-1.6.1 population and Epics AU_GROUP-4 / AU_GROUP-5 until complete)

**Description:**  
Salesforce trial signup fails (“Something went wrong. Please try again.”) and ZoomInfo trial is sales-gated. Capture **production** credentials and access details from the client’s existing Salesforce and ZoomInfo accounts so secrets can be created and API clients implemented.

**Subtasks:**
- Share client checklist: [`docs/project/production-credentials-client-checklist.md`](production-credentials-client-checklist.md)
- Track responses; receive secrets only via approved secure channels (no plaintext in email/Slack)
- **Jira Cloud (`KD`):** Track in **[KD-53](https://automationarchitecture.atlassian.net/browse/KD-53)** — *Gather Production Credentials for Salesforce and ZoomInfo* (blocks KD-3, KD-4; relates to KD-1); see checklist for client-facing items

**Acceptance Criteria:**
- ZoomInfo: production API key + documented rate limits + confirmed capabilities (company match, contacts + titles, scores if licensed) + endpoint / allowlist notes
- Salesforce: `client_id`, `client_secret`, `refresh_token`, `instance_url` for integration user + API permissions confirmed
- Territory mapping (state → rep + Salesforce usernames or 18-char user IDs) documented
- Admin confirmation for custom objects/fields per AU_GROUP-5.1 (or documented equivalents)
- Handoff to DevOps for AU_GROUP-1.6.1 secret values (`/prod/zoominfo/api-key`, `/prod/salesforce/oauth` including `instance_url` in JSON); **Jira:** [KD-53](https://automationarchitecture.atlassian.net/browse/KD-53) marked Done when complete

---

## Phase 1: Daily Pipeline Foundation (Weeks 1-4)

### Epic AU_GROUP-2: PACER Filing Monitor & Document Download

**Epic Description:** Implement daily polling of PACER for new Chapter 11 bankruptcy filings and automatic download of Form 201 (petition) and Form 204 (top 20 creditors).

**Epic Acceptance Criteria:**
- ✅ Daily Celery job polls PACER at 2:00 AM
- ✅ New filings in target states retrieved within 24 hours
- ✅ Form 201 and Form 204 downloaded to S3
- ✅ Debtor metadata extracted and stored in PostgreSQL
- ✅ Processing success/failure logged

---

### Story AU_GROUP-2.1: PACER API Client Integration (Backend)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `integration`, `pacer`, `phase-1`  
**Sprint:** Sprint 2  
**Dependencies:** AU_GROUP-1.6 (Secrets Manager)

**Description:**
As a backend engineer, I need a PACER API client that handles authentication and document download so that we can programmatically access bankruptcy filings.

**Acceptance Criteria:**
- ✅ PACER client authenticates with username/password
- ✅ Client can search for new filings by state + date range
- ✅ Client can download documents by case number + docket entry
- ✅ Retry logic handles transient failures (3 attempts, exponential backoff)
- ✅ Rate limiting respects PACER API limits
- ✅ Unit tests cover all client methods

**Tasks:**

#### Task AU_GROUP-2.1.1: Implement PACER Authentication
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `pacer`, `authentication`

**Subtasks:**
- Research PACER API authentication mechanism (session-based?)
- Implement login method (username/password from Secrets Manager)
- Handle session expiration and re-authentication
- Store session token in Redis (TTL: 1 hour)
- Write unit tests with mocked API responses

**Acceptance Criteria:**
- Authentication working with test credentials
- Session token cached in Redis
- Re-authentication triggers on 401 Unauthorized

---

#### Task AU_GROUP-2.1.2: Implement Filing Search
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `pacer`, `search`

**Subtasks:**
- Implement `search_filings(state, start_date, end_date, chapter_type)` method
- Parse API response to extract case metadata (case_number, debtor_name, filing_date, court_district)
- Filter for Chapter 11 filings only
- Handle pagination if API returns > 100 results
- Write integration tests with PACER test environment

**Acceptance Criteria:**
- Can search for filings in specific state + date range
- Returns list of case metadata dictionaries
- Pagination handled correctly

---

#### Task AU_GROUP-2.1.3: Implement Document Download
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `pacer`, `download`

**Subtasks:**
- Implement `download_document(case_number, docket_entry_id)` method
- Save document to S3 (`raw-documents/{case_number}/{docket_entry_id}.pdf`)
- Track PACER cost ($0.10/page, max $4.50/document)
- Implement retry logic (3 attempts with exponential backoff)
- Handle network timeouts (2-minute timeout)

**Acceptance Criteria:**
- Documents downloaded successfully to S3
- Cost tracked and logged to CloudWatch metric
- Timeouts handled gracefully with retries

---

### Story AU_GROUP-2.2: Daily PACER Polling Job (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `backend`, `celery`, `automation`, `phase-1`  
**Sprint:** Sprint 2  
**Dependencies:** AU_GROUP-2.1 (PACER client), AU_GROUP-1.4 (Redis/Celery)

**Description:**
As a backend engineer, I need a scheduled Celery job that polls PACER daily for new filings so that we process 100% of filings in target states within 24 hours.

**Acceptance Criteria:**
- ✅ Celery Beat job runs daily at 2:00 AM EST
- ✅ Job searches PACER for previous day's filings in target states
- ✅ New filings saved to `bankruptcies` table
- ✅ Job completion logged to CloudWatch
- ✅ Error handling sends alert on failure
- ✅ Job is idempotent (can re-run without duplicates)

**Tasks:**

#### Task AU_GROUP-2.2.1: Create Celery Daily Polling Task
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `poll_pacer_daily()`
- Configure Celery Beat schedule (cron: `0 7 * * *` UTC = 2 AM EST)
- Implement logic: search PACER for previous day's filings in target states
- Save new filings to `bankruptcies` table (upsert based on case_number)
- Log success/failure to `processing_jobs` table
- Send CloudWatch metric: `PACERFilingsProcessed`

**Acceptance Criteria:**
- Job runs daily at scheduled time
- New filings saved to database
- Job completion logged

---

#### Task AU_GROUP-2.2.2: Implement Idempotency and Error Handling
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `error-handling`

**Subtasks:**
- Check if case_number already exists before inserting (upsert logic)
- Implement retry logic for PACER API failures (3 attempts)
- Send Sentry alert on persistent failure (all retries exhausted)
- Log detailed error message to `processing_jobs.error_message`
- Ensure job can safely re-run (no duplicate inserts)

**Acceptance Criteria:**
- Job is idempotent (can re-run multiple times safely)
- Failures logged with detailed error context
- Sentry alert sent on 3rd failure

---

### Story AU_GROUP-2.3: Form 201 & 204 Document Download (Backend)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `backend`, `document-processing`, `phase-1`  
**Sprint:** Sprint 2-3  
**Dependencies:** AU_GROUP-2.2 (Daily polling job)

**Description:**
As a backend engineer, I need automatic download of Form 201 (petition) and Form 204 (top 20 creditors) for each new filing so that we have the source documents for extraction.

**Acceptance Criteria:**
- ✅ Form 201 and Form 204 downloaded for each new bankruptcy
- ✅ Documents saved to S3 with correct naming convention
- ✅ Download failures logged and retried
- ✅ PACER cost tracked per document
- ✅ Job completes within 30 minutes for 50 filings

**Tasks:**

#### Task AU_GROUP-2.3.1: Implement Form Download Logic
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `document-processing`

**Subtasks:**
- Create Celery task: `download_bankruptcy_forms(bankruptcy_id)`
- Identify Form 201 and Form 204 docket entry IDs (PACER docket search)
- Download both forms via PACER client
- Save to S3: `raw-documents/{case_number}/form-201.pdf`, `form-204.pdf`
- Update `bankruptcies.forms_downloaded_at` timestamp
- Track PACER cost in `processing_jobs` table

**Acceptance Criteria:**
- Both forms downloaded successfully
- S3 paths follow naming convention
- Cost tracked per document

---

#### Task AU_GROUP-2.3.2: Implement Parallel Download (Optimization)
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `optimization`

**Subtasks:**
- Modify daily polling job to spawn parallel download tasks (10 concurrent)
- Use Celery chord for parallel execution + callback
- Monitor concurrent PACER API requests (stay under rate limit)
- Add CloudWatch metric: `DocumentDownloadDuration`

**Acceptance Criteria:**
- 50 filings downloaded in < 30 minutes (parallel processing)
- Rate limits not exceeded

---

### Story AU_GROUP-2.4: Debtor Metadata Extraction (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `ai`, `document-parsing`, `phase-1`  
**Sprint:** Sprint 3  
**Dependencies:** AU_GROUP-2.3 (Form download)

**Description:**
As a backend engineer, I need to extract debtor metadata from Form 201 (petition) using PyPDF2 so that we can populate the `bankruptcies` table with structured data.

**Acceptance Criteria:**
- ✅ Debtor name, location, industry code extracted from Form 201
- ✅ Estimated assets, liabilities, creditor count extracted
- ✅ Extraction accuracy ≥ 95% on structured PDFs
- ✅ Extraction failures flagged for manual review
- ✅ Extracted data saved to `bankruptcies` table

**Tasks:**

#### Task AU_GROUP-2.4.1: Implement Form 201 PDF Parser
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `document-parsing`

**Subtasks:**
- Install PyPDF2 + pdfplumber
- Implement `parse_form_201(pdf_path)` function
- Extract debtor name (regex: Debtor full name field)
- Extract location (city, state, zip from address field)
- Extract industry code (NAICS code field)
- Extract estimated assets/liabilities (dollar amounts from checkboxes)
- Extract estimated creditor count (creditor range checkbox)
- Handle missing fields gracefully (return None)

**Acceptance Criteria:**
- All fields extracted with 95%+ accuracy on test PDFs
- Function returns structured dictionary
- Missing fields handled (no exceptions thrown)

---

#### Task AU_GROUP-2.4.2: Integrate Extraction with Celery Pipeline
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `celery`

**Subtasks:**
- Modify `download_bankruptcy_forms` task to call parser after download
- Update `bankruptcies` table with extracted metadata
- Log extraction success/failure to `processing_jobs`
- Send Sentry alert on extraction failure (confidence < 80%)
- Add CloudWatch metric: `MetadataExtractionAccuracy`

**Acceptance Criteria:**
- Metadata extracted and saved to database
- Failures logged with error context
- Accuracy metric tracked in CloudWatch

---

### Story AU_GROUP-2.5: Top 20 Creditor Extraction (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `ai`, `document-parsing`, `phase-1`  
**Sprint:** Sprint 3  
**Dependencies:** AU_GROUP-2.3 (Form download)

**Description:**
As a backend engineer, I need to extract the top 20 unsecured creditors from Form 204 so that we have immediate leads on day one without manual document review.

**Acceptance Criteria:**
- ✅ All top 20 creditors extracted with name, address, claim amount
- ✅ Extraction accuracy ≥ 95% on structured PDFs
- ✅ Creditors saved to `creditors` and `bankruptcy_creditors` tables
- ✅ Extraction failures flagged for manual review
- ✅ Available within 24 hours of PACER filing

**Tasks:**

#### Task AU_GROUP-2.5.1: Implement Form 204 PDF Parser
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `document-parsing`

**Subtasks:**
- Implement `parse_form_204(pdf_path)` function using pdfplumber
- Identify table boundaries (top 20 creditors table)
- Extract columns: creditor name, address, nature of claim, claim amount
- Parse claim amounts (handle "$1,234,567.89" format)
- Handle multi-line addresses (combine into single string)
- Return list of creditor dictionaries

**Acceptance Criteria:**
- All 20 creditors extracted with correct fields
- Claim amounts parsed as numeric (Decimal type)
- Multi-line addresses handled correctly

---

#### Task AU_GROUP-2.5.2: Save Creditors to Database
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `database`

**Subtasks:**
- Implement `save_creditors(bankruptcy_id, creditors_list)` function
- Insert creditors into `creditors` table (upsert based on name + address hash)
- Create join records in `bankruptcy_creditors` table
- Update `bankruptcies.top_20_extracted_at` timestamp
- Log extraction count to `processing_jobs`

**Acceptance Criteria:**
- Creditors saved without duplicates
- Join table records created
- Extraction timestamp updated

---

## Epic AU_GROUP-3: Document Parsing Engine

**Epic Description:** Build a multi-format document parsing engine that handles structured PDFs, simple creditor lists, and OCR for scanned documents.

**Epic Acceptance Criteria:**
- ✅ Structured Schedule E/F parsed with 95%+ accuracy
- ✅ Simple creditor lists (name/address only) parsed
- ✅ OCR applied to scanned documents
- ✅ Company vs. individual classification applied
- ✅ Duplicate creditors consolidated within filing

---

### Story AU_GROUP-3.1: Structured Schedule E/F Parser (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 13  
**Labels:** `backend`, `ai`, `document-parsing`, `phase-1`  
**Sprint:** Sprint 3-4  
**Dependencies:** AU_GROUP-2.1 (PACER client)

**Description:**
As a backend engineer, I need to parse structured Schedule E/F documents (Form 206E/F tabular format) to extract all unsecured creditors with full details.

**Acceptance Criteria:**
- ✅ Extract creditor name, address, claim date, nature, amount, status flags
- ✅ Extraction accuracy ≥ 95% on structured documents
- ✅ Handle multi-page tables correctly
- ✅ Parse claim amounts and dates correctly
- ✅ All extracted creditors saved to database

**Tasks:**

#### Task AU_GROUP-3.1.1: Implement Table Detection and Extraction
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `document-parsing`, `tables`

**Subtasks:**
- Research pdfplumber table extraction capabilities
- Implement `parse_schedule_ef(pdf_path)` function
- Detect table boundaries (find "Schedule E/F" header)
- Extract table rows using pdfplumber table extraction
- Handle multi-page tables (concatenate rows across pages)
- Parse columns: creditor name, address, claim date, nature, amount, contingent/unliquidated/disputed flags
- Handle merged cells and irregular table formatting

**Acceptance Criteria:**
- Table detected on 100% of test PDFs
- All rows extracted across multiple pages
- Columns parsed correctly

---

#### Task AU_GROUP-3.1.2: Implement Data Parsing and Validation
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `data-processing`

**Subtasks:**
- Parse claim amounts (handle "$1,234,567.89", "1234567.89", "unknown")
- Parse claim dates (handle "MM/DD/YYYY", "MM-DD-YYYY", empty)
- Parse boolean flags (contingent, unliquidated, disputed) from checkboxes
- Validate extracted data (name not empty, amount is numeric or null)
- Handle missing/malformed data gracefully
- Return list of validated creditor dictionaries

**Acceptance Criteria:**
- Claim amounts parsed as Decimal or None
- Dates parsed as date objects or None
- Boolean flags parsed correctly
- Invalid rows logged but don't crash parser

---

### Story AU_GROUP-3.2: Simple Creditor List Parser (Backend/AI-Automation)

**Priority:** High  
**Story Points:** 8  
**Labels:** `backend`, `ai`, `document-parsing`, `phase-1`  
**Sprint:** Sprint 4  
**Dependencies:** AU_GROUP-3.1 (Structured parser)

**Description:**
As a backend engineer, I need to parse simple creditor lists (name and address only, no amounts or dates) from text-based attachments so that smaller filings can be processed.

**Acceptance Criteria:**
- ✅ Extract creditor names and addresses from plain text
- ✅ Handle various formatting (bullet points, numbered lists, paragraphs)
- ✅ Classify company vs. individual creditors
- ✅ Missing data fields marked as null (not guessed)
- ✅ All extracted creditors saved to database

**Tasks:**

#### Task AU_GROUP-3.2.1: Implement Text-Based Creditor Extraction
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `nlp`, `document-parsing`

**Subtasks:**
- Extract full text from PDF using PyPDF2
- Implement pattern matching for creditor entries (regex or NER)
- Detect name patterns (company names with suffixes, individual names)
- Extract addresses (multi-line format: street, city, state, zip)
- Handle various list formats (numbered, bulleted, paragraph)
- Split text into individual creditor records

**Acceptance Criteria:**
- Creditor names extracted from plain text
- Addresses extracted (even if multi-line)
- List formats handled correctly

---

#### Task AU_GROUP-3.2.2: Implement Company vs. Individual Classification
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `ai`, `nlp`

**Subtasks:**
- Install spaCy + download en_core_web_lg model
- Implement `classify_creditor(name)` function
- Rule-based classification: check for entity suffixes (LLC, Inc, Corp, Ltd)
- NER-based classification: use spaCy to detect ORG entities
- Default to individual if no company indicators
- Return boolean: True = company, False = individual

**Acceptance Criteria:**
- Classification accuracy ≥ 90% on test dataset
- Companies correctly identified by suffix or NER
- Individuals not misclassified as companies

---

### Story AU_GROUP-3.3: OCR Engine for Scanned Documents (Backend/AI-Automation)

**Priority:** High  
**Story Points:** 13  
**Labels:** `backend`, `ai`, `ocr`, `phase-1`  
**Sprint:** Sprint 4  
**Dependencies:** AU_GROUP-3.1 (Structured parser)

**Description:**
As a backend engineer, I need OCR capability for scanned/handwritten Schedule F documents so that we can process small business filings that are submitted as images.

**Acceptance Criteria:**
- ✅ OCR applied to scanned PDFs using Tesseract
- ✅ OCR confidence score tracked per document
- ✅ Low-confidence results (< 80%) flagged for manual review
- ✅ OCR text saved to S3 for debugging
- ✅ Extracted creditors saved to database if confidence sufficient

**Tasks:**

#### Task AU_GROUP-3.3.1: Implement Tesseract OCR Integration
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `ocr`

**Subtasks:**
- Install Tesseract OCR on EC2 instance
- Install pytesseract Python wrapper
- Implement `ocr_document(pdf_path)` function
- Convert PDF pages to images (using pdf2image)
- Apply Tesseract OCR to each page
- Concatenate OCR text from all pages
- Calculate average confidence score
- Save OCR text to S3: `ocr-outputs/{case_number}/{docket_entry}.txt`

**Acceptance Criteria:**
- OCR working on scanned PDFs
- Confidence score calculated (0-100%)
- OCR text saved to S3

---

#### Task AU_GROUP-3.3.2: Implement Low-Confidence Flagging
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `quality-control`

**Subtasks:**
- Define confidence threshold: < 80% = low confidence
- Flag low-confidence OCR results in `processing_jobs` table (status: 'manual_review_required')
- Send alert to Keith via email/Slack (optional)
- Skip automatic Salesforce push for low-confidence extractions
- Document manual review process in `docs/manual-review.md`

**Acceptance Criteria:**
- Low-confidence results flagged correctly
- Manual review queue visible to Keith
- No low-confidence data pushed to Salesforce automatically

---

#### Task AU_GROUP-3.3.3: Implement Post-OCR Creditor Extraction
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `nlp`

**Subtasks:**
- Parse OCR text using simple creditor list parser (reuse AU_GROUP-3.2)
- Extract creditor names and addresses from OCR text
- Apply company/individual classification
- Save creditors to database if confidence ≥ 80%

**Acceptance Criteria:**
- OCR text parsed using existing parser
- Creditors extracted from high-confidence OCR
- Classification applied

---

### Story AU_GROUP-3.4: Creditor Deduplication (Backend/AI-Automation)

**Priority:** High  
**Story Points:** 8  
**Labels:** `backend`, `ai`, `data-quality`, `phase-1`  
**Sprint:** Sprint 4  
**Dependencies:** AU_GROUP-3.1 (Creditor extraction)

**Description:**
As a backend engineer, I need to deduplicate creditor entries within a single filing (same company listed multiple times with slight variations) so that we don't create duplicate enrichment requests.

**Acceptance Criteria:**
- [x] Duplicate creditors consolidated using fuzzy matching (KD-40 — `app/dedup/creditors.py`)
- [x] Fuzzy match threshold: 85% on normalized name+address (`CREDITOR_DEDUP_THRESHOLD`, RapidFuzz)
- [x] Total claim amounts summed for duplicates
- [x] Deduplication applied before ZoomInfo enrichment (parser → `merge_creditors` before SYS-03)
- [x] Original creditor count vs. deduplicated count logged (`raw_extraction.dedup_stats`, structured log `creditor_dedup`)

**Tasks:**

#### Task AU_GROUP-3.4.1: Implement Fuzzy Matching
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `data-quality`

**Subtasks:**
- Install RapidFuzz library
- Implement `deduplicate_creditors(creditors_list)` function
- RapidFuzz `token_set_ratio` on normalized name + address
- Threshold: ≥ 85% similarity = duplicate (`CREDITOR_DEDUP_THRESHOLD`)
- Group duplicates (Union-Find); canonical row by confidence; sum claim amounts
- Return deduplicated list

**Acceptance Criteria:**
- Duplicates correctly identified (e.g., "ABC Corp" vs. "ABC Corporation")
- Claim amounts summed correctly
- Non-duplicates not incorrectly merged

---

#### Task AU_GROUP-3.4.2: Integrate Deduplication into Pipeline
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `celery`

**Subtasks:**
- Add deduplication step after creditor extraction (before database save)
- Log counts to `documents.raw_extraction.dedup_stats` + structured log `creditor_dedup` (Railway parser; not `processing_jobs`)
- CloudWatch metric deferred (ops via log/monitoring); see implementation-notes.md
- Database save uses deduplicated list via `au_group_merge_creditor_matrix`

**Acceptance Criteria:**
- [x] Deduplication runs automatically in pipeline
- [x] Duplicate count logged (`dedup_stats` / `creditor_dedup`)
- [ ] CloudWatch metric (deferred — not in Railway stack)

---

### Story AU_GROUP-3.5: Page Classification for Multi-Document Filings (Backend/AI-Automation)

**Priority:** Medium  
**Story Points:** 13  
**Labels:** `backend`, `ai`, `document-processing`, `phase-1`  
**Sprint:** Sprint 4  
**Dependencies:** AU_GROUP-3.1 (Structured parser)

**Description:**
As a backend engineer, I need to classify pages in large dockets (200+ pages) to identify creditor list pages so that we only parse relevant sections.

**Acceptance Criteria:**
- ✅ Page classification identifies creditor list pages with 90%+ accuracy
- ✅ Non-creditor pages excluded from parsing (saves processing time)
- ✅ Classification works on multi-document docket entries
- ✅ Classification speed: < 1 second per page
- ✅ False negatives (missed creditor pages) tracked and minimized

**Tasks:**

#### Task AU_GROUP-3.5.1: Implement Rule-Based Page Classification
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `document-processing`

**Subtasks:**
- Implement `classify_page(page_text)` function
- Rule 1: Page contains "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims"
- Rule 2: Page contains tabular data (detected via pdfplumber)
- Rule 3: Page contains creditor-like entries (name + address pattern)
- Score each page (0-100%) based on rules
- Threshold: > 50% score = creditor page
- Return list of page numbers that are creditor pages

**Acceptance Criteria:**
- Creditor pages identified with 90%+ accuracy
- Non-creditor pages correctly excluded
- Classification completes in < 1 second per page

---

#### Task AU_GROUP-3.5.2: Integrate Page Classification into Parser
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `optimization`

**Subtasks:**
- Modify structured parser to classify pages first
- Only parse identified creditor pages
- Skip non-creditor pages (table of contents, cover pages, signatures)
- Log page classification results to `processing_jobs`
- Add CloudWatch metric: `PageClassificationAccuracy`

**Acceptance Criteria:**
- Parser only processes creditor pages
- Processing time reduced by 50%+ on large dockets
- Accuracy metric tracked

---

#### Task AU_GROUP-3.5.3: Implement False Negative Detection
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `quality-control`

**Subtasks:**
- After parsing, check if expected creditor count matches extracted count
- If mismatch > 20%, flag for manual review
- Log false negative cases to Sentry for analysis
- Improve classification rules based on false negative patterns

**Acceptance Criteria:**
- False negatives detected and flagged
- Manual review queue contains missed pages
- Classification rules improved iteratively

---

## Epic AU_GROUP-4: ZoomInfo Enrichment Pipeline

**Epic Description:** Integrate with ZoomInfo API to enrich creditor companies with firmographic data and decision-maker contacts using tier-based targeting rules.

**Epic Acceptance Criteria:**
- ✅ ZoomInfo API client integrated with authentication
- ✅ Tier-based targeting rules applied (Enterprise/Mid-Market/SMB)
- ✅ Up to 3 contacts returned per company, ranked by engagement score
- ✅ 80%+ successful company match rate achieved
- ✅ API responses cached in Redis to reduce costs

---

### Story AU_GROUP-4.1: ZoomInfo API Client Integration (Backend)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `integration`, `zoominfo`, `phase-1`  
**Sprint:** Sprint 4-5  
**Dependencies:** AU_GROUP-1.6 (Secrets Manager), AU_GROUP-1.4 (Redis)

**Description:**
As a backend engineer, I need a ZoomInfo API client that handles authentication, company lookup, and contact retrieval so that we can enrich creditor data.

**Acceptance Criteria:**
- ✅ ZoomInfo client authenticates with API key
- ✅ Client can look up company by name + address
- ✅ Client can retrieve contacts with job title filtering
- ✅ Retry logic handles transient failures
- ✅ Rate limiting respects ZoomInfo API limits
- ✅ API responses cached in Redis (TTL: 7 days)

**Tasks:**

#### Task AU_GROUP-4.1.1: Implement ZoomInfo Authentication and Company Lookup
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `zoominfo`

**Subtasks:**
- Research ZoomInfo API documentation (authentication method)
- Implement `ZoomInfoClient` class with API key auth
- Implement `lookup_company(name, address)` method
- Parse API response to extract firmographic data (revenue, employee_count, industry, headquarters)
- Handle "no match found" gracefully (return None)
- Implement retry logic (3 attempts, exponential backoff)
- Write unit tests with mocked API responses

**Acceptance Criteria:**
- Authentication working with test API key
- Company lookup returns firmographic data
- No-match cases handled gracefully

---

#### Task AU_GROUP-4.1.2: Implement Contact Retrieval with Title Filtering
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `zoominfo`

**Subtasks:**
- Implement `get_contacts(company_id, titles, limit=3)` method
- Filter contacts by job title list (e.g., ["CFO", "Controller", "VP of Finance"])
- Rank contacts by ZoomInfo engagement likelihood score
- Return up to 3 contacts sorted by score (descending)
- Parse contact fields: full_name, title, email, phone, engagement_score

**Acceptance Criteria:**
- Contacts filtered by title correctly
- Up to 3 contacts returned, ranked by score
- Contact fields parsed correctly

---

### Story AU_GROUP-4.2: Tier-Based Targeting Rules Implementation (Backend)

**Priority:** Highest  
**Story Points:** 5  
**Labels:** `backend`, `business-logic`, `phase-1`  
**Sprint:** Sprint 5  
**Dependencies:** AU_GROUP-4.1 (ZoomInfo client)

**Description:**
As a backend engineer, I need to implement tier-based targeting rules that select appropriate contact titles based on company size so that we target the right decision-makers.

**Acceptance Criteria:**
- ✅ Tier 1 (Enterprise): $1B+ revenue or 5,000+ employees
- ✅ Tier 2 (Mid-Market): $100M–$1B revenue or 500–5,000 employees
- ✅ Tier 3 (SMB): < $100M revenue or < 500 employees
- ✅ Correct tier identified for 95%+ of companies
- ✅ Fallback logic: tier 1 → tier 2 → tier 3 until match found
- ✅ Targeting rules configurable via database or config file

**Tasks:**

#### Task AU_GROUP-4.2.1: Implement Tier Classification
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Implement `classify_company_tier(revenue, employee_count)` function
- Tier 1: revenue ≥ $1B OR employees ≥ 5,000
- Tier 2: revenue ≥ $100M OR employees ≥ 500
- Tier 3: everything else
- Handle null revenue/employee_count (default to Tier 3)
- Return tier number (1, 2, or 3)

**Acceptance Criteria:**
- Tier classification correct for all test cases
- Null values handled gracefully
- Boundary cases correct (e.g., exactly $100M = Tier 2)

---

#### Task AU_GROUP-4.2.2: Implement Title Selection with Fallback
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Define tier-to-titles mapping:
  - Tier 1: ["VP of Finance", "Treasurer", "Director of Credit", "VP of Credit Risk"]
  - Tier 2: ["CFO", "Controller", "Director of Finance", "Credit Manager"]
  - Tier 3: ["CFO", "AP/AR Manager", "Accounting Manager", "Office Manager", "Owner"]
- Implement `get_target_titles(tier)` function
- Implement fallback logic:
  1. Try tier 1 titles → if no contacts, try tier 2 → if no contacts, try tier 3
  2. If still no contacts, flag company as "no contact found"
- Store targeting rules in database table or config file (for easy updates)

**Acceptance Criteria:**
- Correct titles selected for each tier
- Fallback logic works correctly
- Targeting rules configurable without code changes

---

### Story AU_GROUP-4.3: ZoomInfo Enrichment Celery Job (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `celery`, `automation`, `phase-1`  
**Sprint:** Sprint 5  
**Dependencies:** AU_GROUP-4.2 (Targeting rules), AU_GROUP-3.2 (Company classification)

**Description:**
As a backend engineer, I need a Celery job that enriches company creditors with ZoomInfo data so that we have decision-maker contacts for outreach.

**Acceptance Criteria:**
- ✅ Job processes company creditors (skips individuals)
- ✅ Company lookup and contact retrieval via ZoomInfo client
- ✅ Tier-based targeting rules applied
- ✅ Enriched data saved to `zoom_info_contacts` table
- ✅ 80%+ successful match rate achieved
- ✅ Job completes within 4 hours for 1,000 companies

**Tasks:**

#### Task AU_GROUP-4.3.1: Implement ZoomInfo Enrichment Task
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `enrich_creditors_with_zoominfo(bankruptcy_id)`
- Query `creditors` table for company creditors (is_company = TRUE)
- For each company:
  1. Check Redis cache for previous enrichment (cache key: hash(name + address))
  2. If cache hit: use cached data, skip API call
  3. If cache miss: lookup company in ZoomInfo
  4. Classify company tier based on firmographic data
  5. Get target titles for tier
  6. Retrieve up to 3 contacts with fallback logic
  7. Save contacts to `zoom_info_contacts` table
  8. Cache API response in Redis (TTL: 7 days)
- Log enrichment stats: total companies, matched, no match, cache hits
- Send CloudWatch metric: `ZoomInfoMatchRate`

**Acceptance Criteria:**
- Company creditors enriched successfully
- Cache hit rate ≥ 40%
- Match rate ≥ 80%

---

#### Task AU_GROUP-4.3.2: Implement Batch Processing for Performance
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `optimization`

**Subtasks:**
- Research ZoomInfo batch API (if available)
- Modify enrichment task to batch 50 companies per API request (if batch API supported)
- If no batch API: process companies sequentially with rate limiting (10 requests/second)
- Monitor ZoomInfo API usage to avoid rate limit
- Add CloudWatch metric: `ZoomInfoAPIUsage` (requests per day)

**Acceptance Criteria:**
- Batch API used if available (20% cost savings)
- Rate limits not exceeded
- 1,000 companies processed in < 4 hours

---

### Story AU_GROUP-4.4: Redis Caching for ZoomInfo Responses (Backend)

**Priority:** High  
**Story Points:** 5  
**Labels:** `backend`, `cache`, `cost-optimization`, `phase-1`  
**Sprint:** Sprint 5  
**Dependencies:** AU_GROUP-4.1 (ZoomInfo client)

**Description:**
As a backend engineer, I need to cache ZoomInfo API responses in Redis so that we reduce API costs when the same company appears in multiple bankruptcies.

**Acceptance Criteria:**
- ✅ ZoomInfo responses cached in Redis with 7-day TTL
- ✅ Cache key: hash(company_name + address)
- ✅ Cache hit rate ≥ 40% (40% of companies are duplicates across filings)
- ✅ Cache misses trigger API call
- ✅ Cache invalidation on company data changes (rare, manual)

**Tasks:**

#### Task AU_GROUP-4.4.1: Implement Cache Layer
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `cache`

**Subtasks:**
- Implement `get_cached_zoominfo_data(company_name, address)` function
- Generate cache key: `SHA256(company_name.lower() + address.lower())`
- Check Redis for cache key
- If found: deserialize JSON, return data
- If not found: return None (trigger API call)
- Implement `set_cached_zoominfo_data(company_name, address, data)` function
- Store data as JSON in Redis with TTL: 7 days (604,800 seconds)

**Acceptance Criteria:**
- Cache get/set working correctly
- TTL enforced (keys expire after 7 days)
- Cache keys unique per company

---

#### Task AU_GROUP-4.4.2: Integrate Cache into Enrichment Pipeline
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `integration`

**Subtasks:**
- Modify `enrich_creditors_with_zoominfo` task to check cache first
- On cache hit: use cached data, skip API call, log cache hit
- On cache miss: call API, save response to cache, log cache miss
- Add CloudWatch metric: `ZoomInfoCacheHitRate` (hits / total requests)
- Monitor cache hit rate over 30 days (target: ≥ 40%)

**Acceptance Criteria:**
- Cache checked before every API call
- Cache hit rate tracked in CloudWatch
- Cost savings validated (40% fewer API calls)

---

### Story AU_GROUP-4.5: Company Name Normalization (Backend/AI-Automation)

**Priority:** Medium  
**Story Points:** 8  
**Labels:** `backend`, `ai`, `data-quality`, `phase-1`  
**Sprint:** Sprint 5  
**Dependencies:** AU_GROUP-4.1 (ZoomInfo client)

**Description:**
As a backend engineer, I need to normalize company names (abbreviate long names, use canonical names) so that ZoomInfo lookups are more accurate.

**Acceptance Criteria:**
- ✅ Long company names shortened using common abbreviations
- ✅ Canonical names from ZoomInfo used (e.g., "IBM" instead of "International Business Machines Corporation")
- ✅ Normalization improves match rate by 5-10%
- ✅ Original name preserved in database (normalization for lookup only)

**Tasks:**

#### Task AU_GROUP-4.5.1: Implement Name Normalization Rules
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `data-processing`

**Subtasks:**
- Implement `normalize_company_name(name)` function
- Rule 1: Replace common long forms with abbreviations:
  - "Incorporated" → "Inc"
  - "Corporation" → "Corp"
  - "Limited" → "Ltd"
  - "Limited Liability Company" → "LLC"
- Rule 2: Remove common suffixes (Inc, Corp, LLC, Ltd) for lookup (add back after match)
- Rule 3: Trim whitespace and convert to title case
- Rule 4: Use ZoomInfo canonical name if match found (store in database)

**Acceptance Criteria:**
- Long names shortened correctly
- Suffixes handled consistently
- Original name preserved in database

---

#### Task AU_GROUP-4.5.2: Integrate Normalization into Lookup
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `integration`

**Subtasks:**
- Modify ZoomInfo lookup to normalize name before API call
- Store canonical name from ZoomInfo response
- Update `creditors.name` with canonical name (optional: add `canonical_name` column)
- Add CloudWatch metric: `NameNormalizationImpact` (match rate before/after)

**Acceptance Criteria:**
- Normalized names used for lookup
- Canonical names stored in database
- Match rate improvement tracked

---

## Epic AU_GROUP-5: Salesforce Integration

**Epic Description:** Integrate with Salesforce to create/update accounts, log bankruptcy events, route leads to territory reps, and trigger automated outreach.

**Epic Acceptance Criteria:**
- ✅ Salesforce custom objects created (Bankruptcy_Event__c, Creditor__c)
- ✅ Accounts created or updated with bankruptcy event data
- ✅ Territory routing based on state-to-rep mapping
- ✅ Do-not-contact and active engagement checks before outreach
- ✅ Automated email sequences triggered via ZoomInfo Engage/SalesLoft

---

### Story AU_GROUP-5.1: Salesforce Custom Objects & Fields (Design/Backend)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `design`, `salesforce`, `backend`, `phase-1`  
**Sprint:** Sprint 5  
**Dependencies:** None

**Description:**
As a Salesforce admin, I need custom objects and fields configured in Salesforce so that bankruptcy event data can be stored and viewed by reps.

**Acceptance Criteria:**
- ✅ Custom object: `Bankruptcy_Event__c` created
- ✅ Custom fields added to Account object
- ✅ Page layouts configured for territory reps
- ✅ Territory-based record access rules configured
- ✅ Custom views created for reps (filtered by territory)

**Tasks:**

#### Task AU_GROUP-5.1.1: Create Bankruptcy_Event Custom Object
**Assignee:** Salesforce Admin / Backend Engineer  
**Story Points:** 3  
**Labels:** `salesforce`, `design`

**Subtasks:**
- Create custom object: `Bankruptcy_Event__c`
- Add fields:
  - `Account__c` (Lookup to Account)
  - `Debtor_Name__c` (Text, 255)
  - `Filing_Date__c` (Date)
  - `Claim_Amount__c` (Currency)
  - `Case_Number__c` (Text, 50, unique)
  - `Court_District__c` (Text, 100)
  - `Chapter_Type__c` (Picklist: '11', '7', '11-Subchapter-V')
  - `PACER_URL__c` (URL)
- Set object permissions (reps can view, admins can edit)
- Add to page layouts

**Acceptance Criteria:**
- Custom object created with all fields
- Object visible to reps in Salesforce UI
- Page layout configured

---

#### Task AU_GROUP-5.1.2: Add Custom Fields to Account Object
**Assignee:** Salesforce Admin  
**Story Points:** 2  
**Labels:** `salesforce`, `design`

**Subtasks:**
- Add custom fields to Account object:
  - `Bankruptcy_Exposure_Count__c` (Number: count of bankruptcy events)
  - `Total_Claim_Amount__c` (Currency: sum of claim amounts)
  - `First_Bankruptcy_Date__c` (Date: earliest filing date)
  - `Most_Recent_Bankruptcy_Date__c` (Date: latest filing date)
  - `Repeat_Exposure_Flag__c` (Checkbox: TRUE if ≥ 4 bankruptcies in 18 months)
- Add fields to page layout (section: Bankruptcy History)
- Configure field-level security (read-only for reps)

**Acceptance Criteria:**
- Custom fields added to Account
- Fields visible on Account page layout
- Field-level security configured

---

#### Task AU_GROUP-5.1.3: Configure Territory-Based Views and Access
**Assignee:** Salesforce Admin  
**Story Points:** 3  
**Labels:** `salesforce`, `design`, `rbac`

**Subtasks:**
- Create list views for each territory rep (filtered by Account.BillingState)
  - "Mike's Leads (CA, NV, AZ)"
  - "Frazier's Leads (TX, OK, LA)"
- Configure record access rules (reps see only their territory accounts)
- Create dashboard widgets for each rep (lead count, conversion rate)
- Document territory mapping in `docs/salesforce-territories.md`

**Acceptance Criteria:**
- List views created and filtered correctly
- Reps see only their territory leads
- Dashboard widgets configured

---

### Story AU_GROUP-5.2: Salesforce API Client Integration (Backend)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `backend`, `integration`, `salesforce`, `phase-1`  
**Sprint:** Sprint 5-6  
**Dependencies:** AU_GROUP-5.1 (Salesforce objects), AU_GROUP-1.6 (Secrets Manager)

**Description:**
As a backend engineer, I need a Salesforce API client that handles authentication and CRUD operations so that we can create/update accounts and bankruptcy events.

**Acceptance Criteria:**
- ✅ Salesforce client authenticates via OAuth 2.0
- ✅ Client can create/update Account records
- ✅ Client can create Bankruptcy_Event__c records
- ✅ Retry logic handles transient failures
- ✅ Rate limiting respects Salesforce API limits (15,000 requests/day)
- ✅ Unit tests cover all client methods

**Tasks:**

#### Task AU_GROUP-5.2.1: Implement Salesforce OAuth Authentication
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `salesforce`, `authentication`

**Subtasks:**
- Install simple-salesforce Python library
- Fetch Salesforce OAuth credentials from Secrets Manager (client_id, client_secret, refresh_token)
- Implement `SalesforceClient` class with OAuth authentication
- Handle token refresh (access token expires after 2 hours)
- Store access token in Redis (TTL: 1 hour) to avoid repeated refresh
- Write unit tests with mocked OAuth responses

**Acceptance Criteria:**
- Authentication working with test credentials
- Access token cached in Redis
- Token refresh triggered on 401 Unauthorized

---

#### Task AU_GROUP-5.2.2: Implement Account CRUD Operations
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `salesforce`

**Subtasks:**
- Implement `create_account(name, billing_address, territory_rep)` method
- Implement `update_account(salesforce_id, fields)` method
- Implement `search_account(name, address)` method (fuzzy match)
- Handle duplicate detection (search before create)
- Implement retry logic (3 attempts, exponential backoff)
- Write integration tests with Salesforce sandbox environment

**Acceptance Criteria:**
- Accounts can be created and updated
- Duplicate detection prevents duplicate accounts
- Retry logic works on failures

---

### Story AU_GROUP-5.3: Salesforce Push Celery Job (Backend/AI-Automation)

**Priority:** Highest  
**Story Points:** 13  
**Labels:** `backend`, `celery`, `automation`, `phase-1`  
**Sprint:** Sprint 6  
**Dependencies:** AU_GROUP-5.2 (Salesforce client), AU_GROUP-4.3 (ZoomInfo enrichment)

**Description:**
As a backend engineer, I need a Celery job that pushes enriched leads to Salesforce with territory routing so that reps can view leads immediately.

**Acceptance Criteria:**
- ✅ Enriched creditors pushed to Salesforce as accounts
- ✅ Bankruptcy_Event__c records created and linked to accounts
- ✅ Territory routing based on creditor state
- ✅ Do-not-contact flag checked before outreach
- ✅ Active engagement detection (open opportunities, recent activity)
- ✅ Job completes within 1 hour for 1,000 creditors

**Tasks:**

#### Task AU_GROUP-5.3.1: Implement Salesforce Push Task
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `push_to_salesforce(bankruptcy_id)`
- Query enriched creditors (with ZoomInfo contacts)
- For each creditor:
  1. Search Salesforce for existing account (fuzzy match on name + address)
  2. If found: update account, add new Bankruptcy_Event__c
  3. If not found: create account, create Bankruptcy_Event__c
  4. Route to territory rep based on state mapping
  5. Check do-not-contact flag
  6. Check for active engagements (open opportunities, activity within 90 days)
  7. If net-new qualified lead: queue for outreach trigger
  8. If flagged (DNC or active engagement): mark as manual review
- Log push stats: total pushed, created, updated, flagged
- Send CloudWatch metric: `SalesforcePushSuccessRate`

**Acceptance Criteria:**
- Accounts created/updated correctly
- Territory routing applied (100% correct)
- Do-not-contact flag respected
- Active engagement detected

---

#### Task AU_GROUP-5.3.2: Implement Territory Routing Logic
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Load state-to-rep mapping from database or config file:
  - CA, NV, AZ → Mike
  - TX, OK, LA → Frazier
  - (etc. for all territories)
- Implement `get_territory_rep(state)` function
- Set Account.OwnerId = territory_rep_user_id
- Handle unmapped states (default to Keith)
- Log territory assignment to `processing_jobs`

**Acceptance Criteria:**
- Territory routing correct for all states
- Unmapped states default to Keith
- Rep assignment logged

---

#### Task AU_GROUP-5.3.3: Implement Do-Not-Contact and Active Engagement Checks
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Check Account.Do_Not_Contact__c field (custom checkbox)
- If TRUE: set `outreach_status` = 'suppressed_dnc', skip outreach trigger
- Query Opportunities related to Account (Status = 'Open', 'Negotiation', 'Closed-Won')
- If open opportunity exists: set `outreach_status` = 'suppressed_active_engagement'
- Query Tasks/Events on Account (CreatedDate > NOW() - 90 days)
- If recent activity exists: set `outreach_status` = 'suppressed_active_engagement'
- Log suppression reason to `processing_jobs`

**Acceptance Criteria:**
- Do-not-contact flag checked before every outreach
- Active engagements detected correctly
- Suppression reasons logged

---

### Story AU_GROUP-5.4: Automated Outreach Triggering (Backend)

**Priority:** High  
**Story Points:** 8  
**Labels:** `backend`, `integration`, `automation`, `phase-1`  
**Sprint:** Sprint 6  
**Dependencies:** AU_GROUP-5.3 (Salesforce push)

**Description:**
As a backend engineer, I need to trigger automated email sequences via ZoomInfo Engage/SalesLoft for net-new qualified leads so that outreach happens within 24 hours.

**Acceptance Criteria:**
- ✅ Email sequences triggered for net-new qualified leads only
- ✅ Leads with DNC or active engagement flagged (no auto-send)
- ✅ Email triggered within 24 hours (T+1 timing, next business day)
- ✅ Email template configured in ZoomInfo Engage/SalesLoft
- ✅ Email send success/failure logged

**Tasks:**

#### Task AU_GROUP-5.4.1: Integrate with ZoomInfo Engage API
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `integration`, `zoominfo`

**Subtasks:**
- Research ZoomInfo Engage API (or SalesLoft API if used instead)
- Implement `trigger_email_sequence(contact_email, template_id)` method
- Configure email template in ZoomInfo Engage (use existing template ID)
- Handle API authentication (API key from Secrets Manager)
- Implement retry logic (3 attempts)
- Log email trigger to `processing_jobs`

**Acceptance Criteria:**
- Email sequences triggered successfully
- Template ID configurable (no hardcoding)
- Failures logged with error context

---

#### Task AU_GROUP-5.4.2: Implement Outreach Timing Logic (T+1)
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Schedule email trigger for next business day (T+1 from creditor extraction)
- Skip weekends (if extracted on Friday, trigger Monday)
- Use Celery ETA (estimated time of arrival) for delayed execution
- Example: if extracted at 3 PM, trigger at 9 AM next business day
- Log scheduled trigger time to `processing_jobs`

**Acceptance Criteria:**
- Email triggers next business day (not same day)
- Weekends handled correctly
- Trigger time logged

---

### Story AU_GROUP-5.5: Historical Exposure Calculation (Backend)

**Priority:** High  
**Story Points:** 8  
**Labels:** `backend`, `business-logic`, `phase-1`  
**Sprint:** Sprint 6  
**Dependencies:** AU_GROUP-5.3 (Salesforce push)

**Description:**
As a backend engineer, I need to calculate cumulative bankruptcy exposure for each creditor (number of filings, total claim amounts, date range) so that historical context is visible in Salesforce.

**Acceptance Criteria:**
- ✅ Exposure calculated: number of bankruptcies, total claim amounts, date range
- ✅ Repeat-exposure threshold detected (≥ 4 bankruptcies in 18 months)
- ✅ Exposure data saved to Account custom fields
- ✅ Repeat-exposure flag set on Account (triggers alternate messaging)
- ✅ Calculation runs after each Salesforce push

**Tasks:**

#### Task AU_GROUP-5.5.1: Implement Exposure Calculation
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Implement `calculate_bankruptcy_exposure(account_id)` function
- Query all Bankruptcy_Event__c records for Account
- Calculate:
  - `exposure_count` = COUNT(events)
  - `total_claim_amount` = SUM(Claim_Amount__c)
  - `first_bankruptcy_date` = MIN(Filing_Date__c)
  - `most_recent_bankruptcy_date` = MAX(Filing_Date__c)
- Detect repeat exposure: COUNT(events WHERE Filing_Date__c > NOW() - 18 months) ≥ 4
- Update Account custom fields with calculated values

**Acceptance Criteria:**
- Exposure calculated correctly
- Repeat-exposure threshold detected accurately
- Account fields updated

---

#### Task AU_GROUP-5.5.2: Integrate Exposure Calculation into Pipeline
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `celery`

**Subtasks:**
- Add exposure calculation step after Bankruptcy_Event__c creation
- If repeat-exposure detected: set `outreach_status` = 'flagged_repeat_exposure'
- Generate suggested alternate messaging (stored in Salesforce or sent to Keith)
- Log exposure data to `processing_jobs`

**Acceptance Criteria:**
- Exposure calculated after every Salesforce push
- Repeat-exposure leads flagged correctly
- Alternate messaging generated

---

## Phase 2: Schedule F Monitoring (Weeks 5-7)

### Epic AU_GROUP-6: Schedule F Monitoring Queue

**Epic Description:** Implement active docket monitoring that scans for Schedule F publication and human-in-the-loop purchase approval workflow.

**Epic Acceptance Criteria:**
- ✅ Active cases added to monitoring queue
- ✅ Weekly docket scans detect Schedule F within 7 days
- ✅ Purchase approval workflow via PACER favorites
- ✅ Approved Schedule F documents downloaded and parsed
- ✅ Zero missed Schedule F filings in monitored cases

---

### Story AU_GROUP-6.1: Schedule F Monitoring Queue Database (Backend)

**Priority:** High  
**Story Points:** 5  
**Labels:** `backend`, `database`, `phase-2`  
**Sprint:** Sprint 7  
**Dependencies:** AU_GROUP-2.2 (Daily polling job)

**Description:**
As a backend engineer, I need a database table to track active bankruptcy cases for Schedule F monitoring so that we can systematically scan dockets.

**Acceptance Criteria:**
- ✅ `schedule_f_queue` table created with appropriate fields
- ✅ New bankruptcies automatically added to queue
- ✅ Queue status tracks: monitoring, detected, pending_approval, approved, rejected, processed
- ✅ Last scanned timestamp tracked per case
- ✅ Queue visible to Keith (optional: admin UI)

**Tasks:**

#### Task AU_GROUP-6.1.1: Create Schedule F Queue Schema
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `database`

**Subtasks:**
- Add `schedule_f_queue` table (already in schema from AU_GROUP-1.3.2)
- Add indexes: status, last_scanned_at
- Create Alembic migration
- Run migration on RDS instance

**Acceptance Criteria:**
- Table created with correct schema
- Indexes created for query performance

---

#### Task AU_GROUP-6.1.2: Implement Queue Management Functions
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Implement `add_to_monitoring_queue(bankruptcy_id)` function
- Implement `update_queue_status(queue_id, status)` function
- Implement `get_cases_for_scanning()` function (returns cases WHERE last_scanned_at < NOW() - 7 days AND status = 'monitoring')
- Automatically add new bankruptcies to queue (modify daily polling job)

**Acceptance Criteria:**
- Queue management functions working correctly
- New cases automatically added to queue
- Scanning query returns correct cases

---

### Story AU_GROUP-6.2: Weekly Docket Scanning Job (Backend/AI-Automation)

**Priority:** High  
**Story Points:** 13  
**Labels:** `backend`, `celery`, `automation`, `phase-2`  
**Sprint:** Sprint 7  
**Dependencies:** AU_GROUP-6.1 (Queue database), AU_GROUP-2.1 (PACER client)

**Description:**
As a backend engineer, I need a scheduled Celery job that scans dockets weekly for Schedule F publication so that we detect full creditor lists within 7 days.

**Acceptance Criteria:**
- ✅ Job runs weekly (Monday 3:00 AM)
- ✅ Scans dockets for all cases in monitoring queue
- ✅ Detects Schedule F keywords: "Schedule F", "Schedule E/F", "206F"
- ✅ Schedule F detected within 7 days of actual filing
- ✅ Detection logged to `schedule_f_queue` table

**Tasks:**

#### Task AU_GROUP-6.2.1: Implement Docket Scanning Task
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `scan_dockets_for_schedule_f()`
- Configure Celery Beat schedule (cron: `0 8 * * 1` UTC = 3 AM EST Monday)
- Query `schedule_f_queue` for cases needing scan (last_scanned_at < NOW() - 7 days)
- For each case:
  1. Fetch docket from PACER (list of docket entries)
  2. Search docket entry descriptions for keywords: "Schedule F", "Schedule E/F", "Creditors Holding Unsecured Claims", "206F"
  3. If found: extract docket entry ID, page count, filing date
  4. Calculate PACER cost estimate ($0.10/page, max $4.50)
  5. Update `schedule_f_queue`: status = 'detected', docket_entry_number, page_count, estimated_cost, detected_at
  6. Update last_scanned_at timestamp
- Process 10 cases concurrently (parallel docket fetches)
- Log scan results to `processing_jobs`

**Acceptance Criteria:**
- Dockets scanned weekly for all queued cases
- Schedule F detected via keyword search
- Metadata extracted correctly (entry ID, page count, cost)

---

#### Task AU_GROUP-6.2.2: Implement Concurrent Docket Fetching
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `optimization`

**Subtasks:**
- Use asyncio or Celery group for concurrent PACER API calls (10 concurrent)
- Monitor PACER API rate limits (stay under limit)
- Implement exponential backoff on rate limit errors
- Add CloudWatch metric: `ScheduleFScanDuration`

**Acceptance Criteria:**
- 100 cases scanned in < 10 minutes (concurrent processing)
- Rate limits not exceeded
- Scan duration logged

---

### Story AU_GROUP-6.3: PACER Favorites Purchase Approval Workflow (Backend)

**Priority:** High  
**Story Points:** 13  
**Labels:** `backend`, `integration`, `pacer`, `phase-2`  
**Sprint:** Sprint 7-8  
**Dependencies:** AU_GROUP-6.2 (Docket scanning)

**Description:**
As a backend engineer, I need to integrate with PACER favorites feature so that Keith can approve/reject Schedule F purchases with zero manual data entry.

**Acceptance Criteria:**
- ✅ System adds detected Schedule F to Keith's PACER favorites
- ✅ Keith unfavorites to reject, leaves favorited to approve
- ✅ System syncs with PACER favorites hourly (9 AM - 5 PM)
- ✅ Approved documents automatically downloaded and processed
- ✅ Rejected documents removed from queue (status = 'rejected')

**Tasks:**

#### Task AU_GROUP-6.3.1: Implement PACER Favorites API Integration
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `pacer`, `integration`

**Subtasks:**
- Research PACER favorites API (add/remove favorite, list favorites)
- Implement `add_to_favorites(case_number, docket_entry_id)` method
- Implement `get_favorites()` method (returns list of favorited dockets)
- Implement `remove_from_favorites(case_number, docket_entry_id)` method
- Handle API authentication and session management

**Acceptance Criteria:**
- Can add dockets to PACER favorites
- Can retrieve list of favorites
- Can remove from favorites

---

#### Task AU_GROUP-6.3.2: Implement Hourly Favorites Sync Job
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `sync_pacer_favorites()`
- Configure Celery Beat schedule (hourly from 9 AM - 5 PM EST)
- Query `schedule_f_queue` for cases with status = 'detected'
- Add detected dockets to PACER favorites (if not already added)
- Fetch current favorites list from PACER
- For each detected docket:
  - If still in favorites: status remains 'pending_approval'
  - If removed from favorites: status = 'rejected'
  - If newly detected and not in favorites: add to favorites, status = 'pending_approval'
- For approved dockets (still in favorites after 24 hours): status = 'approved', trigger download
- Log sync results to `processing_jobs`

**Acceptance Criteria:**
- Favorites synced hourly during business hours
- Approved/rejected status updated correctly
- Approved documents queued for download

---

### Story AU_GROUP-6.4: Schedule F Document Download & Parsing (Backend/AI-Automation)

**Priority:** High  
**Story Points:** 13  
**Labels:** `backend`, `document-processing`, `automation`, `phase-2`  
**Sprint:** Sprint 8  
**Dependencies:** AU_GROUP-6.3 (Purchase approval), AU_GROUP-3 (Parsing engine)

**Description:**
As a backend engineer, I need to automatically download and parse approved Schedule F documents so that all creditors are extracted without manual effort.

**Acceptance Criteria:**
- ✅ Approved Schedule F documents downloaded from PACER
- ✅ Parsing engine selects correct format (structured, simple list, OCR)
- ✅ All creditors extracted and saved to database
- ✅ Deduplication applied within filing
- ✅ Parsed creditors proceed to ZoomInfo enrichment

**Tasks:**

#### Task AU_GROUP-6.4.1: Implement Schedule F Download Task
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Create Celery task: `download_schedule_f(queue_id)`
- Triggered when status changes to 'approved'
- Download document from PACER using `download_document(case_number, docket_entry_id)`
- Save to S3: `raw-documents/{case_number}/schedule-f-{entry}.pdf`
- Update `schedule_f_queue.status` = 'downloaded'
- Log download to `processing_jobs`

**Acceptance Criteria:**
- Approved documents downloaded automatically
- Documents saved to S3 with correct naming
- Download status tracked

---

#### Task AU_GROUP-6.4.2: Implement Format Detection and Parsing
**Assignee:** Backend Engineer  
**Story Points:** 8  
**Labels:** `backend`, `document-processing`

**Subtasks:**
- Create Celery task: `parse_schedule_f(queue_id)`
- Detect document format:
  1. Attempt structured parsing (pdfplumber table extraction)
  2. If tables found: use structured parser (AU_GROUP-3.1)
  3. If no tables: attempt simple text parsing (AU_GROUP-3.2)
  4. If text quality poor (< 80% confidence): apply OCR (AU_GROUP-3.3)
- Parse creditors using appropriate parser
- Apply deduplication (AU_GROUP-3.4)
- Save creditors to `creditors` and `bankruptcy_creditors` tables
- Update `schedule_f_queue.status` = 'processed'
- Proceed to ZoomInfo enrichment (trigger AU_GROUP-4.3 task)

**Acceptance Criteria:**
- Format detected correctly
- Appropriate parser selected
- Creditors extracted and saved
- Enrichment triggered

---

### Story AU_GROUP-6.5: Schedule F Alert Generation (Backend/Design)

**Priority:** Medium  
**Story Points:** 5  
**Labels:** `backend`, `design`, `alerts`, `phase-2`  
**Sprint:** Sprint 8  
**Dependencies:** AU_GROUP-6.2 (Docket scanning)

**Description:**
As a backend engineer, I need to generate alerts for Keith when Schedule F is detected so that he can review and approve purchases quickly.

**Acceptance Criteria:**
- ✅ Alert includes case context: debtor name, filing date, estimated creditor count
- ✅ Alert includes document metadata: page count, PACER cost estimate
- ✅ Alert delivered via email (optional: Slack)
- ✅ Alert includes link to PACER docket entry
- ✅ Keith receives alert within 1 hour of detection

**Tasks:**

#### Task AU_GROUP-6.5.1: Implement Email Alert
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `alerts`

**Subtasks:**
- Install email library (boto3 SES for AWS)
- Implement `send_schedule_f_alert(queue_id, keith_email)` function
- Email template:
  - Subject: "[Action Required] Schedule F Detected - {Debtor Name}"
  - Body: Debtor name, filing date, estimated creditor count, page count, cost estimate, PACER link
- Send email via AWS SES
- Log email sent to `processing_jobs`

**Acceptance Criteria:**
- Email sent on Schedule F detection
- Email contains all required context
- Keith receives email within 1 hour

---

#### Task AU_GROUP-6.5.2: Optional: Implement Slack Alert
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `alerts`, `optional`

**Subtasks:**
- Install Slack SDK (slack-sdk)
- Configure Slack webhook URL (store in Secrets Manager)
- Implement `send_slack_alert(queue_id, slack_channel)` function
- Slack message format: similar to email
- Send to #bankruptcy-alerts channel (or DM to Keith)

**Acceptance Criteria:**
- Slack alert sent on detection
- Alert visible in Slack channel
- Links clickable

---

## Phase 3: Historical Database (Weeks 8-9)

### Epic AU_GROUP-7: Historical Database Import & Exposure Tracking

**Epic Description:** Import Keith's existing 25K-row Excel database of historical creditor-bankruptcy records and build creditor exposure tracking.

**Epic Acceptance Criteria:**
- ✅ 25K-row Excel dataset imported into PostgreSQL
- ✅ Creditor exposure scores calculated (count, total amount, date range)
- ✅ Repeat-exposure threshold detection working
- ✅ Historical exposure visible in Salesforce
- ✅ Two-tier email logic implemented (suppress auto-send for repeat creditors)

---

### Story AU_GROUP-7.1: Historical Data Import Script (Backend)

**Priority:** Medium  
**Story Points:** 8  
**Labels:** `backend`, `data-migration`, `phase-3`  
**Sprint:** Sprint 9  
**Dependencies:** AU_GROUP-1.3 (Database schema)

**Description:**
As a backend engineer, I need a data import script that loads Keith's 25K-row Excel database into PostgreSQL so that historical exposure data is available.

**Acceptance Criteria:**
- ✅ Excel file parsed successfully (handle CSV or XLSX format)
- ✅ Data validated before import (required fields not null)
- ✅ Duplicates detected and skipped
- ✅ 100% of valid rows imported without data loss
- ✅ Import process idempotent (can re-run safely)

**Tasks:**

#### Task AU_GROUP-7.1.1: Implement Excel Parser
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `data-processing`

**Subtasks:**
- Install pandas library
- Implement `parse_historical_excel(file_path)` function
- Read Excel columns: case_number, debtor_name, filing_date, creditor_name, creditor_address, claim_amount, court_district
- Validate data:
  - case_number not null
  - debtor_name not null
  - filing_date is valid date
  - creditor_name not null
- Handle missing claim_amount (set to null, not 0)
- Return list of valid row dictionaries

**Acceptance Criteria:**
- Excel parsed successfully
- Invalid rows logged (not skipped silently)
- Valid rows returned as structured data

---

#### Task AU_GROUP-7.1.2: Implement Database Import
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `database`

**Subtasks:**
- Implement `import_historical_data(rows)` function
- For each row:
  1. Check if bankruptcy exists (case_number) → insert if not found
  2. Check if creditor exists (name + address hash) → insert if not found
  3. Check if bankruptcy_creditor join exists → insert if not found
- Use database transactions (commit after all rows or rollback on error)
- Log import stats: total rows, inserted, duplicates skipped
- Make import idempotent (upsert logic, not insert)

**Acceptance Criteria:**
- All valid rows imported
- Duplicates skipped (not re-inserted)
- Import stats logged

---

### Story AU_GROUP-7.2: Creditor Exposure Calculation (Backend)

**Priority:** Medium  
**Story Points:** 8  
**Labels:** `backend`, `business-logic`, `phase-3`  
**Sprint:** Sprint 9  
**Dependencies:** AU_GROUP-7.1 (Historical data import), AU_GROUP-5.5 (Exposure calculation function)

**Description:**
As a backend engineer, I need to calculate creditor exposure scores for all creditors (historical + new) so that exposure data is available in Salesforce.

**Acceptance Criteria:**
- ✅ Exposure calculated for all creditors in database
- ✅ Exposure includes: count, total amount, first date, most recent date
- ✅ Repeat-exposure threshold detected (≥ 4 bankruptcies in 18 months)
- ✅ Exposure data synced to Salesforce Account custom fields
- ✅ Calculation runs nightly to keep data fresh

**Tasks:**

#### Task AU_GROUP-7.2.1: Implement Batch Exposure Calculation
**Assignee:** Backend Engineer  
**Story Points:** 5  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Create Celery task: `calculate_all_exposures()`
- Query all creditors with > 1 bankruptcy event
- For each creditor: call `calculate_bankruptcy_exposure()` (reuse from AU_GROUP-5.5.1)
- Update Salesforce Account fields (batch update, not one-by-one)
- Log exposure calculation stats to `processing_jobs`
- Add CloudWatch metric: `ExposureCalculationDuration`

**Acceptance Criteria:**
- Exposure calculated for all creditors
- Salesforce fields updated in batch (efficient)
- Calculation completes in < 30 minutes for 25K creditors

---

#### Task AU_GROUP-7.2.2: Schedule Nightly Exposure Recalculation
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `celery`, `automation`

**Subtasks:**
- Configure Celery Beat schedule (cron: `0 4 * * *` UTC = 11 PM EST)
- Run `calculate_all_exposures()` task nightly
- Only recalculate creditors with new bankruptcy events (optimization)
- Log nightly run to `processing_jobs`

**Acceptance Criteria:**
- Exposure recalculated nightly
- Only updated creditors processed (not full table scan)
- Job runs successfully without manual intervention

---

### Story AU_GROUP-7.3: Two-Tier Email Logic (Repeat Exposure Flagging) (Backend)

**Priority:** Medium  
**Story Points:** 8  
**Labels:** `backend`, `business-logic`, `phase-3`  
**Sprint:** Sprint 9  
**Dependencies:** AU_GROUP-7.2 (Exposure calculation), AU_GROUP-5.4 (Outreach triggering)

**Description:**
As a backend engineer, I need to implement two-tier email logic that suppresses auto-send for repeat-exposure creditors and generates suggested alternate messaging.

**Acceptance Criteria:**
- ✅ Repeat-exposure threshold configurable (default: ≥ 4 bankruptcies in 18 months)
- ✅ Repeat creditors flagged (no auto-send)
- ✅ Suggested alternate messaging generated referencing history
- ✅ Keith receives list of flagged creditors for manual review
- ✅ Alternate messaging template stored in Salesforce or emailed to Keith

**Tasks:**

#### Task AU_GROUP-7.3.1: Implement Repeat Exposure Detection
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Modify outreach trigger logic (AU_GROUP-5.4) to check repeat-exposure flag
- Query Bankruptcy_Event__c for Account (WHERE Filing_Date__c > NOW() - 18 months)
- Count events in 18-month window
- If count ≥ 4: set `outreach_status` = 'flagged_repeat_exposure'
- Skip auto-send, proceed to alternate messaging generation

**Acceptance Criteria:**
- Repeat-exposure detected correctly
- Auto-send suppressed for repeat creditors
- Flagged status logged

---

#### Task AU_GROUP-7.3.2: Generate Suggested Alternate Messaging
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `business-logic`

**Subtasks:**
- Implement `generate_alternate_message(account_id)` function
- Template: "Your company has been affected by {count} bankruptcies since {first_date}, totaling ${total_amount} in claims. We specialize in helping companies like yours protect against future losses."
- Store suggested message in Salesforce custom field: `Suggested_Messaging__c`
- Alternatively: send email to Keith with list of flagged creditors + suggested messages

**Acceptance Criteria:**
- Alternate message generated for repeat creditors
- Message references actual exposure data (count, amount, date)
- Message stored in Salesforce or emailed to Keith

---

#### Task AU_GROUP-7.3.3: Implement Manual Review Queue for Keith
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `design`

**Subtasks:**
- Create Salesforce list view: "Flagged for Manual Review" (filter: Repeat_Exposure_Flag__c = TRUE AND Outreach_Status__c = 'flagged')
- Optional: Send daily email to Keith with list of flagged leads
- Optional: Add admin API endpoint to manually trigger outreach for flagged leads

**Acceptance Criteria:**
- Manual review queue visible to Keith in Salesforce
- Keith can view flagged leads and suggested messaging
- Keith can manually trigger outreach if desired

---

### Story AU_GROUP-7.4: Salesforce Exposure Views (Design/Backend)

**Priority:** Low  
**Story Points:** 5  
**Labels:** `design`, `salesforce`, `backend`, `phase-3`  
**Sprint:** Sprint 9  
**Dependencies:** AU_GROUP-7.2 (Exposure calculation)

**Description:**
As a Salesforce admin, I need custom page layouts and dashboards that display creditor exposure history so that reps can reference it during outreach.

**Acceptance Criteria:**
- ✅ Exposure fields visible on Account page layout
- ✅ Bankruptcy_Event__c related list visible (shows all past bankruptcies)
- ✅ Dashboard widget: "Repeat Exposure Leads" (count by territory)
- ✅ Report: "Top 100 Creditors by Exposure" (sorted by total claim amount)

**Tasks:**

#### Task AU_GROUP-7.4.1: Update Account Page Layout
**Assignee:** Salesforce Admin  
**Story Points:** 2  
**Labels:** `salesforce`, `design`

**Subtasks:**
- Add "Bankruptcy History" section to Account page layout
- Add fields: Bankruptcy_Exposure_Count__c, Total_Claim_Amount__c, First_Bankruptcy_Date__c, Most_Recent_Bankruptcy_Date__c, Repeat_Exposure_Flag__c
- Add related list: Bankruptcy_Event__c (shows all past bankruptcies for this account)
- Reorder sections for optimal viewing

**Acceptance Criteria:**
- Exposure fields visible on Account page
- Related list shows past bankruptcies
- Layout optimized for reps

---

#### Task AU_GROUP-7.4.2: Create Exposure Dashboards and Reports
**Assignee:** Salesforce Admin  
**Story Points:** 3  
**Labels:** `salesforce`, `design`, `analytics`

**Subtasks:**
- Create dashboard widget: "Repeat Exposure Leads by Territory" (bar chart)
- Create report: "Top 100 Creditors by Exposure" (table, sorted by Total_Claim_Amount__c)
- Create report: "Flagged Leads Awaiting Manual Review" (list view)
- Add dashboards to rep home pages

**Acceptance Criteria:**
- Dashboards created and visible to reps
- Reports filterable by territory
- Data accurate (matches database)

---

## Continuous: QA & DevOps

### Epic AU_GROUP-8: DevOps, Monitoring & Security

**Epic Description:** Set up CI/CD pipeline, monitoring dashboards, error tracking, and security hardening for production launch.

**Epic Acceptance Criteria:**
- ✅ GitHub Actions CI/CD pipeline configured
- ✅ Automated testing (unit + integration tests)
- ✅ Sentry error tracking integrated
- ✅ CloudWatch dashboards for key metrics
- ✅ Security scan passes (no high/critical vulnerabilities)
- ✅ Production deployment checklist complete

---

### Story AU_GROUP-8.1: Automated Testing (QA/Backend)

**Priority:** High  
**Story Points:** 13  
**Labels:** `qa`, `backend`, `testing`, `continuous`  
**Sprint:** Sprint 2-9 (ongoing)  
**Dependencies:** All backend stories

**Description:**
As a QA engineer, I need comprehensive automated tests (unit + integration) so that we can catch bugs early and deploy with confidence.

**Acceptance Criteria:**
- ✅ Unit tests for all core functions (target: 80%+ code coverage)
- ✅ Integration tests for API clients (PACER, ZoomInfo, Salesforce)
- ✅ End-to-end tests for critical workflows (daily polling, enrichment, Salesforce push)
- ✅ Tests run automatically in CI/CD pipeline
- ✅ Test failures block deployment to production

**Tasks:**

#### Task AU_GROUP-8.1.1: Write Unit Tests for Core Modules
**Assignee:** QA Engineer / Backend Engineer  
**Story Points:** 8  
**Labels:** `qa`, `testing`

**Subtasks:**
- Write unit tests for PDF parsers (AU_GROUP-3.1, AU_GROUP-3.2, AU_GROUP-3.3)
- Write unit tests for creditor classification (AU_GROUP-3.2.2)
- Write unit tests for deduplication (AU_GROUP-3.4.1)
- Write unit tests for tier classification (AU_GROUP-4.2.1)
- Write unit tests for exposure calculation (AU_GROUP-5.5.1)
- Target: 80%+ code coverage
- Use pytest + pytest-cov

**Acceptance Criteria:**
- Unit tests passing for all core modules
- Code coverage ≥ 80%
- Tests run in < 2 minutes

---

#### Task AU_GROUP-8.1.2: Write Integration Tests for API Clients
**Assignee:** QA Engineer  
**Story Points:** 5  
**Labels:** `qa`, `testing`, `integration`

**Subtasks:**
- Write integration tests for PACER client (auth, search, download)
- Write integration tests for ZoomInfo client (company lookup, contacts)
- Write integration tests for Salesforce client (account create/update)
- Use mocked API responses (VCR or similar) for deterministic tests
- Test error handling (API down, rate limits, timeouts)

**Acceptance Criteria:**
- Integration tests passing for all API clients
- Error cases covered (timeouts, rate limits, API errors)
- Tests run in < 5 minutes

---

### Story AU_GROUP-8.2: CI/CD Pipeline (DevOps)

**Priority:** High  
**Story Points:** 8  
**Labels:** `devops`, `ci-cd`, `continuous`  
**Sprint:** Sprint 2 (setup), ongoing  
**Dependencies:** AU_GROUP-8.1 (Testing)

**Description:**
As a DevOps engineer, I need a CI/CD pipeline that automatically tests and deploys code so that deployments are fast, reliable, and repeatable.

**Acceptance Criteria:**
- ✅ GitHub Actions workflow configured
- ✅ Runs on every push to `main` branch
- ✅ Steps: lint, test, security scan, deploy
- ✅ Deployment to production requires manual approval (optional gate)
- ✅ Rollback procedure documented

**Tasks:**

#### Task AU_GROUP-8.2.1: Configure GitHub Actions Workflow
**Assignee:** DevOps Engineer  
**Story Points:** 5  
**Labels:** `devops`, `ci-cd`

**Subtasks:**
- Create `.github/workflows/ci-cd.yml`
- Steps:
  1. Lint code (flake8 + black)
  2. Run unit tests (pytest)
  3. Run integration tests (pytest)
  4. Security scan (safety check)
  5. Build deployment package
  6. SSH to EC2 and deploy
- Add GitHub secrets: EC2_SSH_KEY, EC2_HOST, ADMIN_API_KEY
- Test workflow on staging branch first

**Acceptance Criteria:**
- Workflow runs on every push to `main`
- All steps pass before deployment
- Deployment automated (SSH + rsync + systemctl restart)

---

#### Task AU_GROUP-8.2.2: Implement Rollback Procedure
**Assignee:** DevOps Engineer  
**Story Points:** 3  
**Labels:** `devops`, `incident-response`

**Subtasks:**
- Create rollback script: `scripts/rollback.sh`
- Script reverts to previous git commit and restarts services
- Document rollback procedure in `docs/rollback.md`
- Test rollback on staging environment

**Acceptance Criteria:**
- Rollback script works correctly
- Rollback completes in < 5 minutes
- Procedure documented

---

### Story AU_GROUP-8.3: Monitoring Dashboards (DevOps)

**Priority:** High  
**Story Points:** 8  
**Labels:** `devops`, `monitoring`, `continuous`  
**Sprint:** Sprint 3 (setup), ongoing  
**Dependencies:** AU_GROUP-2 (Daily polling job)

**Description:**
As a DevOps engineer, I need CloudWatch dashboards that display key metrics so that we can monitor system health and performance.

**Acceptance Criteria:**
- ✅ Dashboard: Daily Processing (filings processed, creditors extracted, errors)
- ✅ Dashboard: Infrastructure (CPU, memory, disk, network)
- ✅ Dashboard: API Usage (PACER, ZoomInfo, Salesforce request counts + costs)
- ✅ Dashboard: Data Quality (extraction accuracy, match rates, cache hit rates)
- ✅ Dashboards accessible to Keith and engineers

**Tasks:**

#### Task AU_GROUP-8.3.1: Create Daily Processing Dashboard
**Assignee:** DevOps Engineer  
**Story Points:** 3  
**Labels:** `devops`, `monitoring`

**Subtasks:**
- Create CloudWatch dashboard: "Daily Processing"
- Add widgets:
  - PACER Filings Processed (line chart, daily)
  - Creditors Extracted (line chart, daily)
  - Processing Errors (line chart, daily)
  - Processing Duration (line chart, P50/P95/P99)
- Add annotations for each phase launch (Phase 1, 2, 3)

**Acceptance Criteria:**
- Dashboard created with all widgets
- Data populating correctly
- Dashboard public (shareable link)

---

#### Task AU_GROUP-8.3.2: Create Infrastructure Dashboard
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `devops`, `monitoring`

**Subtasks:**
- Create CloudWatch dashboard: "Infrastructure"
- Add widgets:
  - EC2 CPU Utilization (%)
  - EC2 Memory Usage (%)
  - RDS CPU Utilization (%)
  - RDS Connections (count)
  - Redis Memory Usage (%)
- Add alarms for each metric (threshold: 80%)

**Acceptance Criteria:**
- Dashboard created with all widgets
- Alarms configured and tested
- Dashboard accessible to engineers

---

#### Task AU_GROUP-8.3.3: Create API Usage & Cost Dashboard
**Assignee:** DevOps Engineer  
**Story Points:** 3  
**Labels:** `devops`, `monitoring`, `cost-tracking`

**Subtasks:**
- Create CloudWatch dashboard: "API Usage & Costs"
- Add widgets:
  - PACER API Requests (count, daily)
  - PACER Cost (dollars, daily)
  - ZoomInfo API Requests (count, daily)
  - ZoomInfo Cost (estimated, daily)
  - Salesforce API Requests (count, daily)
- Add monthly cost projection (based on daily average)

**Acceptance Criteria:**
- Dashboard created with cost tracking
- Cost projections accurate (±10%)
- Keith can view monthly costs

---

### Story AU_GROUP-8.4: Error Tracking with Sentry (DevOps)

**Priority:** High  
**Story Points:** 5  
**Labels:** `devops`, `monitoring`, `continuous`  
**Sprint:** Sprint 1 (setup), ongoing  
**Dependencies:** None

**Description:**
As a DevOps engineer, I need Sentry error tracking integrated so that we get real-time alerts on application errors.

**Acceptance Criteria:**
- ✅ Sentry SDK integrated into FastAPI + Celery
- ✅ Errors automatically reported to Sentry
- ✅ Error alerts sent to Slack/email
- ✅ Stack traces and context captured
- ✅ Release tracking enabled (tag errors by git commit)

**Tasks:**

#### Task AU_GROUP-8.4.1: Integrate Sentry SDK
**Assignee:** Backend Engineer  
**Story Points:** 3  
**Labels:** `backend`, `monitoring`

**Subtasks:**
- Install sentry-sdk Python package
- Configure Sentry DSN (store in Secrets Manager)
- Initialize Sentry in `app/__init__.py` with FastAPI + Celery integrations
- Set environment tag (production, staging)
- Enable release tracking (set release = git commit SHA)
- Test error capture (trigger test exception)

**Acceptance Criteria:**
- Sentry initialized correctly
- Test errors appearing in Sentry dashboard
- Release tags visible in Sentry

---

#### Task AU_GROUP-8.4.2: Configure Error Alerts
**Assignee:** DevOps Engineer  
**Story Points:** 2  
**Labels:** `devops`, `alerts`

**Subtasks:**
- Configure Sentry alert rules:
  - New error type: Email to engineers immediately
  - Error rate > 10/hour: Slack notification
  - Critical errors (database down, API failures): Page on-call
- Test alert delivery (trigger test errors)

**Acceptance Criteria:**
- Alerts configured in Sentry
- Test alerts delivered successfully
- Engineers notified on errors

---

### Story AU_GROUP-8.5: Security Hardening (DevOps/Backend)

**Priority:** Highest  
**Story Points:** 8  
**Labels:** `devops`, `backend`, `security`, `continuous`  
**Sprint:** Sprint 1 (setup), Sprint 8 (pre-launch audit)  
**Dependencies:** AU_GROUP-1 (Infrastructure)

**Description:**
As a DevOps engineer, I need to harden security (dependency scanning, secrets audit, penetration testing) so that the system is secure before production launch.

**Acceptance Criteria:**
- ✅ No high/critical vulnerabilities in dependencies
- ✅ All credentials in Secrets Manager (no hardcoded secrets)
- ✅ Security groups restrictive (no 0.0.0.0/0 except bastion)
- ✅ Encryption at rest and in transit enforced
- ✅ Security audit documented and passed

**Tasks:**

#### Task AU_GROUP-8.5.1: Dependency Vulnerability Scanning
**Assignee:** DevOps Engineer  
**Story Points:** 3  
**Labels:** `devops`, `security`

**Subtasks:**
- Add Safety check to CI/CD pipeline (scan requirements.txt)
- Enable Dependabot on GitHub repo
- Review and fix all high/critical CVEs
- Document exceptions for low/medium CVEs (with justification)

**Acceptance Criteria:**
- Safety check passes in CI/CD
- No high/critical vulnerabilities
- Exceptions documented

---

#### Task AU_GROUP-8.5.2: Secrets Audit
**Assignee:** Backend Engineer  
**Story Points:** 2  
**Labels:** `backend`, `security`

**Subtasks:**
- Scan codebase for hardcoded secrets (use trufflehog or git-secrets)
- Verify all credentials fetched from Secrets Manager
- Ensure no secrets in git history (if found, rotate credentials)
- Add pre-commit hook to block secret commits (optional)

**Acceptance Criteria:**
- No hardcoded secrets found
- All credentials in Secrets Manager
- Pre-commit hook installed (optional)

---

#### Task AU_GROUP-8.5.3: Security Group Audit
**Assignee:** DevOps Engineer  
**Story Points:** 3  
**Labels:** `devops`, `security`, `audit`

**Subtasks:**
- Review all security group rules
- Ensure no 0.0.0.0/0 ingress (except bastion SSH)
- Ensure RDS/Redis only accessible from EC2 security group
- Document security group rules in `docs/security-groups.md`
- Run AWS Trusted Advisor security checks

**Acceptance Criteria:**
- Security groups follow least-privilege principle
- Audit documented
- Trusted Advisor checks pass

---

## Sprint Planning

### Sprint Duration: 2 weeks  
### Team Capacity: 80 story points per sprint (2 engineers × 40 points each)

---

### Sprint 0: Infrastructure Setup (Week 0)

**Goal:** Set up AWS infrastructure, database, and core services.

**Epic:** AU_GROUP-1 (Infrastructure Setup)

**Stories:**
- AU_GROUP-1.1: AWS VPC & Network Configuration (5 points)
- AU_GROUP-1.2: EC2 Instance Provisioning (3 points)
- AU_GROUP-1.3: RDS PostgreSQL Database Setup (5 points)
- AU_GROUP-1.4: Redis ElastiCache Configuration (3 points)
- AU_GROUP-1.5: S3 Bucket & Lifecycle Policies (2 points)
- AU_GROUP-1.6: AWS Secrets Manager Configuration (5 points)
- AU_GROUP-8.4: Error Tracking with Sentry (5 points)
- AU_GROUP-8.5: Security Hardening (8 points - only tasks 8.5.1 and 8.5.2)

**Total:** 36 points  
**Dependencies:** None  
**Deliverables:** Infrastructure ready, database schema applied, credentials in Secrets Manager

---

### Sprint 1-2: PACER Integration & Document Download (Weeks 1-4)

**Goal:** Implement daily PACER polling and automatic download of Form 201/204.

**Epic:** AU_GROUP-2 (PACER Filing Monitor)

**Stories:**
- AU_GROUP-2.1: PACER API Client Integration (8 points)
- AU_GROUP-2.2: Daily PACER Polling Job (5 points)
- AU_GROUP-2.3: Form 201 & 204 Document Download (5 points)
- AU_GROUP-2.4: Debtor Metadata Extraction (8 points)
- AU_GROUP-2.5: Top 20 Creditor Extraction (8 points)
- AU_GROUP-8.1: Automated Testing (8 points - start unit tests)
- AU_GROUP-8.2: CI/CD Pipeline (8 points)

**Total:** 50 points across 2 sprints  
**Dependencies:** AU_GROUP-1 (Infrastructure)  
**Deliverables:** Daily PACER polling working, top 20 creditors extracted to database

---

### Sprint 3-4: Document Parsing Engine (Weeks 5-8)

**Goal:** Build multi-format document parsing engine.

**Epic:** AU_GROUP-3 (Document Parsing Engine)

**Stories:**
- AU_GROUP-3.1: Structured Schedule E/F Parser (13 points)
- AU_GROUP-3.2: Simple Creditor List Parser (8 points)
- AU_GROUP-3.3: OCR Engine for Scanned Documents (13 points)
- AU_GROUP-3.4: Creditor Deduplication (8 points)
- AU_GROUP-3.5: Page Classification for Multi-Document Filings (13 points)
- AU_GROUP-8.1: Automated Testing (5 points - continue unit tests)

**Total:** 60 points across 2 sprints  
**Dependencies:** AU_GROUP-2 (PACER integration)  
**Deliverables:** Parsing engine handles all document formats, deduplication working

---

### Sprint 5: ZoomInfo Enrichment (Weeks 9-10)

**Goal:** Integrate ZoomInfo API and implement tier-based targeting.

**Epic:** AU_GROUP-4 (ZoomInfo Enrichment)

**Stories:**
- AU_GROUP-4.1: ZoomInfo API Client Integration (8 points)
- AU_GROUP-4.2: Tier-Based Targeting Rules Implementation (5 points)
- AU_GROUP-4.3: ZoomInfo Enrichment Celery Job (8 points)
- AU_GROUP-4.4: Redis Caching for ZoomInfo Responses (5 points)
- AU_GROUP-4.5: Company Name Normalization (8 points)
- AU_GROUP-5.1: Salesforce Custom Objects & Fields (8 points)

**Total:** 42 points  
**Dependencies:** AU_GROUP-3 (Parsing engine), AU_GROUP-1.4 (Redis)  
**Deliverables:** ZoomInfo enrichment working, 80%+ match rate, caching operational

---

### Sprint 6: Salesforce Integration (Weeks 11-12)

**Goal:** Integrate with Salesforce and implement outreach triggering.

**Epic:** AU_GROUP-5 (Salesforce Integration)

**Stories:**
- AU_GROUP-5.2: Salesforce API Client Integration (8 points)
- AU_GROUP-5.3: Salesforce Push Celery Job (13 points)
- AU_GROUP-5.4: Automated Outreach Triggering (8 points)
- AU_GROUP-5.5: Historical Exposure Calculation (8 points)
- AU_GROUP-8.3: Monitoring Dashboards (8 points)

**Total:** 45 points  
**Dependencies:** AU_GROUP-4 (ZoomInfo), AU_GROUP-5.1 (Salesforce objects)  
**Deliverables:** Leads pushed to Salesforce, territory routing working, outreach triggering operational

---

### Sprint 7-8: Schedule F Monitoring (Weeks 13-16)

**Goal:** Implement Schedule F detection and purchase approval workflow.

**Epic:** AU_GROUP-6 (Schedule F Monitoring Queue)

**Stories:**
- AU_GROUP-6.1: Schedule F Monitoring Queue Database (5 points)
- AU_GROUP-6.2: Weekly Docket Scanning Job (13 points)
- AU_GROUP-6.3: PACER Favorites Purchase Approval Workflow (13 points)
- AU_GROUP-6.4: Schedule F Document Download & Parsing (13 points)
- AU_GROUP-6.5: Schedule F Alert Generation (5 points)

**Total:** 49 points across 2 sprints  
**Dependencies:** AU_GROUP-2 (PACER), AU_GROUP-3 (Parsing)  
**Deliverables:** Schedule F detection working, purchase approval via PACER favorites, zero missed filings

---

### Sprint 9: Historical Database (Weeks 17-18)

**Goal:** Import historical data and build exposure tracking.

**Epic:** AU_GROUP-7 (Historical Database)

**Stories:**
- AU_GROUP-7.1: Historical Data Import Script (8 points)
- AU_GROUP-7.2: Creditor Exposure Calculation (8 points)
- AU_GROUP-7.3: Two-Tier Email Logic (Repeat Exposure Flagging) (8 points)
- AU_GROUP-7.4: Salesforce Exposure Views (5 points)
- AU_GROUP-8.5: Security Hardening (3 points - task 8.5.3 audit)

**Total:** 32 points  
**Dependencies:** AU_GROUP-5 (Salesforce), AU_GROUP-7 (Exposure calculation)  
**Deliverables:** 25K historical records imported, exposure scores calculated, repeat-exposure flagging working

---

## Dependency Matrix

| Epic/Story | Depends On | Blocks |
|------------|-----------|--------|
| **AU_GROUP-1** (Infrastructure) | None | AU_GROUP-2, AU_GROUP-3, AU_GROUP-4, AU_GROUP-5, AU_GROUP-6, AU_GROUP-7 |
| **AU_GROUP-2** (PACER Monitor) | AU_GROUP-1 | AU_GROUP-3, AU_GROUP-6 |
| **AU_GROUP-3** (Parsing Engine) | AU_GROUP-2 | AU_GROUP-4, AU_GROUP-6 |
| **AU_GROUP-4** (ZoomInfo) | AU_GROUP-3, AU_GROUP-1.4 (Redis) | AU_GROUP-5 |
| **AU_GROUP-5** (Salesforce) | AU_GROUP-4, AU_GROUP-5.1 (SF Objects) | AU_GROUP-7 |
| **AU_GROUP-6** (Schedule F) | AU_GROUP-2, AU_GROUP-3 | None |
| **AU_GROUP-7** (Historical DB) | AU_GROUP-5 | None |
| **AU_GROUP-8** (DevOps) | Various (continuous) | None |

---

## Labels Reference

| Label | Purpose |
|-------|---------|
| `backend` | Backend implementation (Python, FastAPI, Celery) |
| `frontend` | Frontend implementation (none for MVP, Salesforce only) |
| `infrastructure` | AWS infrastructure, networking, deployment |
| `design` | Salesforce UI/UX, page layouts, dashboards |
| `qa` | Testing, quality assurance |
| `ai` | AI/ML components (OCR, NLP, classification) |
| `automation` | Automated workflows (Celery jobs, scheduled tasks) |
| `integration` | External API integrations (PACER, ZoomInfo, Salesforce) |
| `security` | Security hardening, vulnerability scanning, secrets |
| `cost-optimization` | Cost reduction features (caching, batch processing) |
| `phase-0` | Infrastructure setup |
| `phase-1` | Daily pipeline foundation |
| `phase-2` | Schedule F monitoring |
| `phase-3` | Historical database |
| `continuous` | Ongoing work (DevOps, monitoring, QA) |

---

**End of Jira Backlog Structure**

**Total Story Points:** 311 points  
**Estimated Duration:** 9 sprints (18 weeks)  
**Target Launch:** End of Sprint 9 (Week 18)
