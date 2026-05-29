# Final Technology Stack
## Bankruptcy Creditor Intelligence Platform

**Version:** 1.0  
**Date:** March 12, 2026  
**Status:** Approved for Implementation

---

## Executive Summary

This document defines the finalized technology stack for the Bankruptcy Creditor Intelligence Platform based on the comprehensive technical architecture debate. All decisions prioritize **speed-to-market (3-4 week Phase 1 delivery)** while maintaining a clear **migration path to scale** (Phase 4: 10x volume).

**Key Principles:**
- ✅ Monolithic Python backend (fastest development, best document processing)
- ✅ No custom frontend (Salesforce-only UI eliminates 2-3 weeks of development)
- ✅ Hybrid database strategy (PostgreSQL + Redis + S3)
- ✅ AWS-native infrastructure (managed services reduce operational overhead)
- ✅ Security-first (all credentials in Secrets Manager, VPC isolation, encryption at rest/transit)

---

## 1. Frontend Stack

### Primary UI: None (Salesforce Lightning)

**Rationale:** Reps already live in Salesforce; custom UI adds friction and delays Phase 1 by 2-3 weeks.

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **End-User UI** | Salesforce Lightning | N/A | Territory reps view leads, bankruptcy context, historical exposure |
| **Custom Objects** | Salesforce | N/A | `Bankruptcy_Event__c`, `Creditor__c` custom objects |
| **Custom Fields** | Salesforce | N/A | Debtor name, filing date, claim amount, case number, court district |
| **Territory Views** | Salesforce Reports | N/A | Filtered views per rep's assigned states |
| **Mobile Access** | Salesforce Mobile App | Native | Reps access leads on mobile devices |

---

### Admin UI: Minimal (Optional HTML Interface)

**Rationale:** Keith uses PACER interface for approvals; minimal admin dashboard for manual triggers only.

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Admin Dashboard** | FastAPI Jinja2 Templates | 0.109+ | Optional: Simple HTML page for manual triggers |
| **Styling** | Tailwind CSS (CDN) | 3.4+ | Minimal styling for admin HTML pages |
| **API Documentation** | Swagger UI (FastAPI built-in) | Auto-generated | Interactive API docs at `/docs` |

**Implementation:**
```python
# Optional admin dashboard (if needed)
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/admin/dashboard")
async def admin_dashboard(request: Request):
    stats = get_processing_stats()  # Daily summary
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": stats
    })
```

**Decision:** Start with **no custom admin UI** (Phase 1-3); add simple HTML dashboard in Phase 4 if Keith requests better UX.

---

## 2. Backend Stack

### Core Application

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Document processing, NLP, API integrations |
| **Web Framework** | FastAPI | 0.109+ | REST API, async support, auto-generated OpenAPI docs |
| **ASGI Server** | Uvicorn | 0.27+ | Production ASGI server for FastAPI |
| **Task Queue** | Celery | 5.3+ | Async job processing (PACER polling, enrichment, Salesforce push) |
| **Message Broker** | Redis | 7.0+ | Celery broker + result backend |
| **ORM** | SQLAlchemy | 2.0+ | Async ORM for PostgreSQL |
| **Database Migrations** | Alembic | 1.13+ | Schema versioning and migrations |

---

### Document Processing & AI

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **PDF Parsing** | PyPDF2 + pdfplumber | 3.0+ / 0.10+ | Extract text from structured PDFs (Form 204, Schedule E/F) |
| **OCR Engine** | Tesseract + pytesseract | 5.3+ / 0.3+ | OCR for scanned/handwritten documents |
| **NLP / Entity Extraction** | spaCy | 3.7+ | Company vs. individual classification, entity recognition |
| **Fuzzy Matching** | RapidFuzz | 3.6+ | Creditor deduplication within filings |
| **Date Parsing** | python-dateutil | 2.8+ | Parse filing dates, claim dates from various formats |

---

### API Integrations

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **HTTP Client** | httpx | 0.26+ | Async HTTP client for API calls (PACER, ZoomInfo, Salesforce) |
| **PACER Integration** | Custom wrapper (httpx) | N/A | PACER API client (authentication, document download) |
| **ZoomInfo SDK** | Custom wrapper (httpx) | N/A | ZoomInfo API client (company enrichment, contact lookup) |
| **Salesforce SDK** | simple-salesforce | 1.12+ | Salesforce REST API client (account creation, updates) |
| **Retry Logic** | tenacity | 8.2+ | Exponential backoff for API failures |

---

### Utilities & Helpers

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Environment Variables** | python-dotenv | 1.0+ | Load `.env` files for local development |
| **Secrets Management** | boto3 (AWS SDK) | 1.34+ | Fetch credentials from AWS Secrets Manager |
| **Logging** | structlog | 24.1+ | Structured JSON logging for CloudWatch |
| **Validation** | Pydantic | 2.6+ | Request/response validation, settings management |
| **Testing** | pytest + pytest-asyncio | 8.0+ / 0.23+ | Unit tests, integration tests, async test support |

---

### Dependencies Summary

**Core (`requirements.txt`):**
```txt
fastapi==0.109.2
uvicorn[standard]==0.27.1
celery==5.3.6
redis==5.0.1
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.6.1
python-dotenv==1.0.1

# Document Processing
PyPDF2==3.0.1
pdfplumber==0.10.4
pytesseract==0.3.10
spacy==3.7.2
rapidfuzz==3.6.1

# API Clients
httpx==0.26.0
simple-salesforce==1.12.5
boto3==1.34.34
tenacity==8.2.3

# Utilities
structlog==24.1.0
python-dateutil==2.8.2
```

**Development (`requirements-dev.txt`):**
```txt
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-cov==4.1.0
black==24.1.1
flake8==7.0.0
mypy==1.8.0
safety==3.0.1
```

---

## 3. Database

> **AU Group (2026):** Pipeline tables (`bankruptcies`, `creditors`, `bankruptcy_creditors`, `zoom_info_contacts`, `salesforce_accounts`, `processing_jobs`, `schedule_f_queue`, `bankruptcy_rss_events`, plus `pipeline_executions`) are deployed on **Supabase Postgres** with migrations named `au_group_*`. TypeScript types for the project database live in [`types/database.types.ts`](types/database.types.ts). Parser staging tables (`documents`, `form201_extractions`, `creditor_matrix_extractions`, `creditor_matrix_rows`, `document_parse_results`) and ops tables (`pipeline_executions`, `au_group_enrich_loop_staging`) must not be dropped without a coordinated refactor — see [`docs/workflows/client-ops-runbook.md`](../workflows/client-ops-runbook.md). The RDS option below remains the documented scale-out / alternative from the original architecture debate.

### Primary Database: PostgreSQL

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **Service** | AWS RDS PostgreSQL | Managed PostgreSQL service |
| **Version** | PostgreSQL 15.5+ | Latest stable version |
| **Instance Type** | db.t3.micro | 2 vCPU, 1GB RAM (Phase 1-3) |
| **Storage** | 20GB SSD (gp3) | General Purpose SSD with burst |
| **Multi-AZ** | Disabled (Phase 1-3) | Single AZ for cost savings; enable in Phase 4 |
| **Backup Retention** | 7 days | Automated daily backups |
| **Encryption** | AWS KMS (AES-256) | Encryption at rest |
| **SSL/TLS** | Required (`sslmode=require`) | Encryption in transit |

**Schema Design:**
```sql
-- Core tables
CREATE TABLE bankruptcies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number VARCHAR(50) UNIQUE NOT NULL,
    debtor_name VARCHAR(255) NOT NULL,
    filing_date DATE NOT NULL,
    court_district VARCHAR(100) NOT NULL,
    estimated_assets NUMERIC(15, 2),
    estimated_liabilities NUMERIC(15, 2),
    estimated_creditor_count INTEGER,
    chapter_type VARCHAR(20) NOT NULL,  -- '11', '7', '11-Subchapter-V'
    state VARCHAR(2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE creditors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(500) NOT NULL,
    address TEXT,
    claim_amount NUMERIC(15, 2),
    claim_date DATE,
    nature_of_claim VARCHAR(255),
    is_company BOOLEAN DEFAULT TRUE,
    is_contingent BOOLEAN DEFAULT FALSE,
    is_unliquidated BOOLEAN DEFAULT FALSE,
    is_disputed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE bankruptcy_creditors (
    bankruptcy_id UUID REFERENCES bankruptcies(id) ON DELETE CASCADE,
    creditor_id UUID REFERENCES creditors(id) ON DELETE CASCADE,
    PRIMARY KEY (bankruptcy_id, creditor_id)
);

CREATE TABLE zoom_info_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creditor_id UUID REFERENCES creditors(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    company_revenue NUMERIC(15, 2),
    company_employee_count INTEGER,
    company_industry VARCHAR(255),
    engagement_score INTEGER,  -- ZoomInfo likelihood score
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE salesforce_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creditor_id UUID REFERENCES creditors(id) ON DELETE CASCADE,
    salesforce_account_id VARCHAR(18) UNIQUE NOT NULL,
    territory_rep VARCHAR(100),
    last_sync_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL,  -- 'pacer_poll', 'document_intelligence', 'document_parse', 'zoom_info_enrich', 'salesforce_push'
    status VARCHAR(20) NOT NULL,  -- 'pending', 'running', 'completed', 'failed'
    bankruptcy_id UUID REFERENCES bankruptcies(id),
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE schedule_f_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bankruptcy_id UUID REFERENCES bankruptcies(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL,  -- 'monitoring', 'detected', 'pending_approval', 'approved', 'rejected', 'processed'
    docket_entry_number VARCHAR(50),
    page_count INTEGER,
    estimated_cost NUMERIC(6, 2),
    last_scanned_at TIMESTAMP,
    detected_at TIMESTAMP,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_bankruptcies_filing_date ON bankruptcies(filing_date);
CREATE INDEX idx_bankruptcies_state ON bankruptcies(state);
CREATE INDEX idx_creditors_name_gin ON creditors USING gin(name gin_trgm_ops);  -- Fuzzy matching
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX idx_schedule_f_queue_status ON schedule_f_queue(status);
```

**Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Fuzzy text matching
```

---

### Cache & Queue: Redis

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **Service** | AWS ElastiCache Redis | Managed Redis service |
| **Version** | Redis 7.0+ | Latest stable version |
| **Instance Type** | cache.t3.micro | 2 vCPU, 0.5GB RAM (Phase 1-3) |
| **Nodes** | 1 node (single-node) | No replication for MVP; add replica in Phase 4 |
| **Eviction Policy** | `allkeys-lru` | Evict least recently used keys when memory full |
| **Encryption** | In-transit (TLS) | Redis AUTH + TLS enabled |

**Usage:**
```python
# Redis keys structure
celery:*                          # Celery task queue
cache:zoominfo:{company_hash}     # ZoomInfo API response cache (TTL: 7 days)
ratelimit:pacer:{date}            # PACER API rate limit counter
ratelimit:zoominfo:{date}         # ZoomInfo API rate limit counter
monitoring:schedule_f:{case_id}   # Schedule F monitoring state
```

---

### Document Storage: S3

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **Service** | AWS S3 Standard | Object storage for documents |
| **Bucket Name** | `bankruptcy-creditor-docs` | Single bucket for all documents |
| **Versioning** | Enabled | Track amended Schedule F documents |
| **Encryption** | SSE-S3 (AES-256) | Server-side encryption at rest |
| **Lifecycle Policy** | Standard → Glacier after 90 days | Cost optimization for old documents |

**Folder Structure:**
```
s3://bankruptcy-creditor-docs/
  ├── raw-documents/
  │   └── {case_number}/
  │       ├── form-201.pdf           # Voluntary petition
  │       ├── form-204.pdf           # Top 20 creditors
  │       └── schedule-f-{entry}.pdf # Schedule F documents
  ├── parsed-outputs/
  │   └── {case_number}/
  │       └── schedule-f-{entry}.json  # Parsed creditor data
  └── ocr-outputs/
      └── {case_number}/
          └── schedule-f-{entry}.txt   # OCR text output
```

**Retention Policy:**
- Raw documents: Retain 5 years (compliance/audit)
- Parsed outputs: Retain 1 year (debugging)
- OCR outputs: Retain 1 year (debugging)

---

## 4. Hosting Platform

### Compute: AWS EC2

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **Cloud Provider** | AWS | Industry standard, managed services ecosystem |
| **Region** | us-east-1 (N. Virginia) | Primary region; lowest latency to PACER servers |
| **Instance Type** | t3.medium | 2 vCPU, 4GB RAM, burstable CPU |
| **OS** | Ubuntu 22.04 LTS | Long-term support, Python 3.11 compatibility |
| **Storage** | 30GB EBS gp3 | General Purpose SSD |
| **Network** | VPC with private subnet | No public IP; NAT Gateway for internet access |

**EC2 Instance Role:**
```
Permissions:
  - SecretsManager: GetSecretValue (read credentials)
  - S3: PutObject, GetObject (document storage)
  - CloudWatch: PutMetricData, PutLogEvents (monitoring)
  - RDS: DescribeDBInstances (health checks)
```

---

### Networking

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **VPC** | 10.0.0.0/16 | Isolated network for all resources |
| **Public Subnet** | 10.0.1.0/24 | NAT Gateway only |
| **Private Subnet** | 10.0.2.0/24 | EC2, RDS, ElastiCache (no internet access) |
| **NAT Gateway** | us-east-1a | Outbound internet for EC2 (PACER API, ZoomInfo API) |
| **Security Groups** | Restrictive ingress | SSH from bastion only, RDS from EC2 only |
| **DNS** | Route 53 | Domain registration, DNS management |

**Security Group Rules:**
```
EC2 Security Group:
  - Inbound: SSH (port 22) from bastion host only
  - Outbound: HTTPS (port 443) to internet (APIs)
  - Outbound: PostgreSQL (port 5432) to RDS security group
  - Outbound: Redis (port 6379) to ElastiCache security group

RDS Security Group:
  - Inbound: PostgreSQL (port 5432) from EC2 security group only

ElastiCache Security Group:
  - Inbound: Redis (port 6379) from EC2 security group only
```

---

### Phase 4 Migration: ECS Fargate

**Trigger:** When daily processing time > 6 hours OR manual scaling becomes frequent

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **Service** | AWS ECS Fargate | Managed container orchestration |
| **Load Balancer** | Application Load Balancer | Distribute traffic across FastAPI tasks |
| **FastAPI Tasks** | 2 tasks × 0.5 vCPU, 1GB RAM | API layer with auto-scaling |
| **Celery Worker Tasks** | 4 tasks × 1 vCPU, 2GB RAM | Async job processing |
| **Deployment** | GitHub Actions → ECR → ECS | Automated CI/CD pipeline |

---

## 5. Authentication Provider

### API Authentication: Custom API Key

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Authentication Method** | API Key (HTTP Header) | Simple auth for single admin user (Keith) |
| **Header Name** | `X-API-Key` | Custom header for admin endpoints |
| **Key Storage** | AWS Secrets Manager | Encrypted storage, automatic rotation |
| **Key Rotation** | 90 days | Automatic rotation via Secrets Manager |
| **Audit Logging** | CloudWatch Logs | Log all API key usage (timestamp, endpoint, IP) |

**Implementation:**
```python
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import boto3

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_admin_api_key() -> str:
    """Fetch admin API key from Secrets Manager"""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='prod/admin/api-key')
    return json.loads(response['SecretString'])['api_key']

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for admin endpoints"""
    if not api_key or api_key != get_admin_api_key():
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )
    return api_key

# Protected admin endpoints
@app.post("/api/v1/admin/trigger-pacer-poll", dependencies=[Depends(verify_api_key)])
async def trigger_pacer_poll():
    """Manually trigger PACER polling job"""
    pass
```

---

### Credential Management: AWS Secrets Manager

| Secret Path | Content | Rotation |
|-------------|---------|----------|
| `/prod/pacer/credentials` | `{"username": "...", "password": "..."}` | 90 days |
| `/prod/zoominfo/api-key` | `{"api_key": "..."}` | 90 days |
| `/prod/salesforce/oauth` | `{"client_id": "...", "client_secret": "...", "refresh_token": "...", "instance_url": "..."}` | 90 days |
| `/prod/admin/api-key` | `{"api_key": "..."}` | 90 days |

**Fetch Credentials in Application:**
```python
import boto3
import json

def get_secret(secret_name: str) -> dict:
    """Fetch secret from AWS Secrets Manager"""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
pacer_creds = get_secret('prod/pacer/credentials')
PACER_USERNAME = pacer_creds['username']
PACER_PASSWORD = pacer_creds['password']
```

---

### Phase 4 Migration: OAuth 2.0 (Salesforce SSO)

**Trigger:** When team grows beyond Keith (multiple admin users)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Identity Provider** | Salesforce OAuth 2.0 | Single sign-on with existing Salesforce credentials |
| **Token Type** | OAuth 2.0 Bearer Token | Access token (2-hour expiry) + refresh token |
| **RBAC** | Salesforce roles | Admin vs. rep permissions |
| **Library** | Authlib | Python OAuth 2.0 client library |

---

## 6. AI Services

### Document Processing

| Service | Technology | Purpose |
|---------|-----------|---------|
| **PDF Text Extraction** | PyPDF2 + pdfplumber | Extract text from structured PDFs (Form 204, Schedule E/F) |
| **OCR (Optical Character Recognition)** | Tesseract 5.3 (via pytesseract) | Extract text from scanned/handwritten documents |
| **Text Classification** | spaCy 3.7 (en_core_web_lg model) | Company vs. individual creditor classification |
| **Named Entity Recognition** | spaCy NER | Extract company names, addresses, claim amounts |
| **Fuzzy String Matching** | RapidFuzz | Creditor deduplication (Levenshtein distance) |

---

### No External AI APIs (Phase 1-3)

**Rationale:**
- OCR and NLP handled locally (Tesseract + spaCy)
- No LLM required for structured data extraction
- Avoid external AI costs and latency

**Phase 4 Consideration:**
If OCR accuracy < 90% on handwritten filings, evaluate:
- **AWS Textract:** Managed OCR service (higher accuracy than Tesseract, but $1.50/1000 pages)
- **Google Cloud Vision API:** OCR + handwriting recognition ($1.50/1000 images)

**Decision:** Start with **local Tesseract OCR** (Phase 1-3); upgrade to AWS Textract in Phase 4 only if accuracy is insufficient.

---

### spaCy Model Details

| Model | Size | Accuracy | Use Case |
|-------|------|----------|----------|
| **en_core_web_lg** | 780MB | 85%+ NER accuracy | Production model for entity extraction |
| **en_core_web_sm** | 12MB | 75%+ NER accuracy | Development/testing only (faster, lower accuracy) |

**Installation:**
```bash
python -m spacy download en_core_web_lg
```

**Usage:**
```python
import spacy

nlp = spacy.load("en_core_web_lg")

def classify_creditor(name: str) -> bool:
    """Returns True if company, False if individual"""
    # Rule-based: Check for entity suffixes
    company_suffixes = ["LLC", "Inc", "Corp", "Ltd", "LP", "LLP", "PC"]
    if any(suffix in name.upper() for suffix in company_suffixes):
        return True
    
    # NER-based: Check if spaCy detects ORG entity
    doc = nlp(name)
    if any(ent.label_ == "ORG" for ent in doc.ents):
        return True
    
    # Default: Assume individual if no company indicators
    return False
```

---

## 7. DevOps Tooling

### Version Control

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Source Control** | GitHub | Git repository hosting |
| **Repository** | Private repo | `automation-architecture/bankruptcy-creditor-intelligence` |
| **Branching Strategy** | Git Flow | `main` (production), `develop` (staging), feature branches |
| **Branch Protection** | Required reviews | 1 approval required for PR to `main` |

---

### CI/CD Pipeline (Phase 2+)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **CI/CD Platform** | GitHub Actions | Automated testing, linting, deployment |
| **Container Registry** | AWS ECR | Store Docker images (Phase 4 migration to ECS) |
| **Deployment Tool** | Custom bash script (Phase 1-3) | SSH + systemctl restart |

**GitHub Actions Workflow (`.github/workflows/deploy.yml`):**
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/ --cov=app --cov-report=xml
      - name: Security scan
        run: safety check -r requirements.txt

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to EC2
        env:
          SSH_KEY: ${{ secrets.EC2_SSH_KEY }}
          HOST: ${{ secrets.EC2_HOST }}
        run: |
          echo "$SSH_KEY" > ssh_key.pem
          chmod 600 ssh_key.pem
          ssh -i ssh_key.pem ubuntu@$HOST 'bash -s' < scripts/deploy.sh
```

---

### Infrastructure as Code (Phase 4+)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **IaC Tool** | Terraform | Define infrastructure as code (VPC, EC2, RDS, S3) |
| **State Backend** | S3 + DynamoDB | Store Terraform state with locking |

**Why not Phase 1-3:** Manual infrastructure setup is faster for MVP; IaC adds 1-2 weeks of setup time.

---

### Secrets Management

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Secrets Storage** | AWS Secrets Manager | Encrypted credential storage |
| **Rotation** | Automatic (90 days) | Lambda-based rotation for PACER, ZoomInfo, Salesforce |
| **Access Control** | IAM roles | EC2 instance role can read secrets only (no write) |

---

### Dependency Management

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Package Manager** | pip | Python package installation |
| **Dependency Pinning** | `requirements.txt` | Pin exact versions (e.g., `fastapi==0.109.2`) |
| **Vulnerability Scanning** | Safety + Dependabot | Detect insecure packages (CVEs) |
| **License Compliance** | pip-licenses | Audit dependency licenses |

**Dependency Update Process:**
1. Dependabot creates PR for package updates
2. CI/CD runs tests + security scan
3. Manual review + approval
4. Merge to `main` → auto-deploy

---

## 8. Analytics Stack

### No Custom Analytics (Phase 1-3)

**Rationale:** Salesforce already provides:
- Lead tracking (source: bankruptcy filing)
- Conversion metrics (lead → opportunity → closed-won)
- Rep activity logging (calls, emails, meetings)
- Territory performance dashboards

**Analytics Questions Answered by Salesforce:**
- ✅ How many leads generated per bankruptcy filing?
- ✅ What's the conversion rate of bankruptcy-sourced leads?
- ✅ Which territory has highest lead volume?
- ✅ What's the average time from lead creation to first contact?

---

### System Metrics (CloudWatch)

**Not business analytics, but operational metrics:**

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| **Processing time per filing** | Custom metric (application) | > 2 minutes (P95) |
| **ZoomInfo API success rate** | Custom metric (application) | < 90% |
| **Salesforce push success rate** | Custom metric (application) | < 95% |
| **Schedule F detection rate** | Custom metric (application) | < 100% (missed filings) |
| **PACER cost per day** | Custom metric (application) | > $250 |

**Custom Metrics Implementation:**
```python
import boto3
cloudwatch = boto3.client('cloudwatch')

def track_processing_time(duration_seconds: float):
    """Send processing time to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='BankruptcyCreditorIntelligence',
        MetricData=[{
            'MetricName': 'ProcessingTime',
            'Value': duration_seconds,
            'Unit': 'Seconds'
        }]
    )
```

---

### Phase 4: Add Business Intelligence (Optional)

**Trigger:** When Keith requests deeper analytics beyond Salesforce reports

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Warehouse** | Amazon Redshift Serverless | Aggregate data from PostgreSQL + Salesforce |
| **ETL** | AWS Glue | Extract-Transform-Load from RDS → Redshift |
| **Visualization** | Tableau or Looker | Custom dashboards (bankruptcy trends, rep performance) |

**Cost:** $100-300/month (Redshift Serverless + Glue)

**Decision:** **No custom analytics** for Phase 1-3; rely on Salesforce reports.

---

## 9. Monitoring Stack

### Application Performance Monitoring (APM)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Error Tracking** | Sentry | Real-time error reporting, stack traces, release tracking |
| **Plan** | Sentry Team ($26/month) | 5,000 events/month, 1 team member |
| **SDK** | sentry-sdk (Python) | FastAPI + Celery integration |

**Sentry Configuration:**
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment="production",
    traces_sample_rate=0.1,  # Sample 10% of transactions for performance monitoring
    integrations=[
        FastApiIntegration(),
        CeleryIntegration(),
    ],
)
```

**Alerts:**
- Error rate > 10/hour → Slack notification
- New error type → Email to engineer
- Release deployed → Slack notification

---

### Infrastructure Monitoring

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Logs** | AWS CloudWatch Logs | Centralized log aggregation (application + system logs) |
| **Metrics** | AWS CloudWatch Metrics | Infrastructure metrics (CPU, memory, disk, network) |
| **Alarms** | AWS CloudWatch Alarms | Alert on threshold breaches (CPU > 80%, disk > 90%) |
| **Notifications** | AWS SNS → Email | Send alerts to Keith + engineer on-call |

**CloudWatch Log Groups:**
```
/aws/ec2/bankruptcy-creditor-intelligence/application  # FastAPI + Celery logs
/aws/ec2/bankruptcy-creditor-intelligence/system       # Ubuntu system logs
/aws/rds/postgresql/bankruptcy-creditor-intelligence   # PostgreSQL slow query log
```

**CloudWatch Alarms:**
```python
import boto3
cloudwatch = boto3.client('cloudwatch')

# Alarm: EC2 CPU > 80% for 5 minutes
cloudwatch.put_metric_alarm(
    AlarmName='EC2-CPU-High',
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=1,
    MetricName='CPUUtilization',
    Namespace='AWS/EC2',
    Period=300,  # 5 minutes
    Statistic='Average',
    Threshold=80.0,
    ActionsEnabled=True,
    AlarmActions=['arn:aws:sns:us-east-1:123456789:operations-alerts'],
    Dimensions=[{'Name': 'InstanceId', 'Value': 'i-1234567890abcdef0'}]
)
```

---

### Database Monitoring

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **RDS Enhanced Monitoring** | AWS RDS | OS-level metrics (CPU, memory, disk I/O, network) |
| **Slow Query Log** | PostgreSQL | Log queries > 1 second for optimization |
| **Connection Pool Metrics** | SQLAlchemy | Track connection pool usage, detect leaks |

**PostgreSQL Slow Query Log:**
```sql
-- Enable slow query logging in RDS parameter group
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1 second
ALTER SYSTEM SET log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ';
```

---

### Uptime Monitoring

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Health Checks** | AWS Route 53 Health Checks | Monitor API endpoint uptime (30-second interval) |
| **Endpoint** | `GET /health` | FastAPI health check endpoint |
| **Status Page** | Custom HTML page (optional) | Public status page for Keith |

**Health Check Endpoint:**
```python
@app.get("/health")
async def health_check():
    """Health check endpoint for Route 53 monitoring"""
    # Check database connection
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    # Check Redis connection
    try:
        redis_client.ping()
    except Exception as e:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    return {"status": "healthy"}
```

---

### Phase 4: Add Full Observability Stack (Optional)

**Trigger:** When debugging becomes difficult with CloudWatch Logs alone

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **APM Platform** | Datadog | Unified logs, metrics, traces, dashboards |
| **Plan** | Datadog Pro ($15/host/month) | Full-stack observability |
| **Distributed Tracing** | OpenTelemetry → Datadog | Trace requests across Celery tasks |

**Cost:** $180/month (1 EC2 host + 4 Celery workers)

**Decision:** **Start with CloudWatch + Sentry** (Phase 1-3, $26/month); upgrade to Datadog in Phase 4 if needed ($180/month).

---

## Summary: Complete Technology Stack

| Category | Technology | Version | Cost (Monthly) |
|----------|-----------|---------|----------------|
| **Frontend** | Salesforce Lightning (existing) | N/A | $0 (included in existing license) |
| **Backend** | Python + FastAPI + Celery | 3.11 / 0.109 / 5.3 | $0 (open source) |
| **Database** | PostgreSQL (RDS) + Redis (ElastiCache) + S3 | 15 / 7.0 | $27 |
| **Hosting** | AWS EC2 t3.medium | 2 vCPU, 4GB RAM | $35 |
| **Authentication** | API Key + AWS Secrets Manager | N/A | $1.60 |
| **AI Services** | Tesseract OCR + spaCy NER (local) | 5.3 / 3.7 | $0 (local processing) |
| **DevOps** | GitHub Actions (CI/CD) | N/A | $0 (free tier) |
| **Analytics** | Salesforce Reports (existing) | N/A | $0 (included in existing license) |
| **Monitoring** | CloudWatch + Sentry | N/A / Team | $28.50 |
| **Total Infrastructure** | | | **$92/month** |
| | | | |
| **External APIs** | PACER + ZoomInfo + Salesforce | N/A | $5,877/month* |
| **GRAND TOTAL** | | | **$5,969/month** |

*After optimization: PACER ($4,725) + ZoomInfo ($1,152) + Salesforce ($0)

---

## Migration Roadmap

### Phase 1-3: MVP (Current)
- Single EC2 instance + RDS + Redis + S3
- Manual deployment via SSH
- CloudWatch Logs + Sentry for monitoring
- API Key authentication

### Phase 4: Scale (10x Volume)
- Migrate to ECS Fargate (containerized)
- Add Application Load Balancer
- Enable PostgreSQL read replicas
- Add Redis replication
- CI/CD via GitHub Actions
- Consider OAuth 2.0 (if team grows)
- Consider Datadog (if observability needs increase)

### Phase 5: Enterprise (100x Volume — Future)
- Migrate to EKS (Kubernetes)
- Aurora PostgreSQL Serverless (auto-scaling)
- ElastiCache Redis Cluster (sharded)
- Full observability stack (Datadog)
- Multi-region deployment (if needed)

---

**End of Final Technology Stack Document**
