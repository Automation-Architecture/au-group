# Live n8n Workflow Views

## Workflow 1: "When a booking has been made" ✅ ACTIVE

**ID:** `24r46Q18zklOfoh3`  
**Status:** ✅ Running  
**Type:** Event-Driven (Webhook)  
**Last Updated:** 2026-01-28  
**Version:** 48  

### 🎯 Purpose
Real-time multilingual booking confirmation emails sent to guests immediately after booking with personalized onboarding links.

### 📊 Workflow Flow Diagram

```
┌─────────────────────────────────┐
│  On a new booking (Webhook)     │
│  POST /new-booking              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Get booking details (Code)     │
│  Extract record from webhook    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Filter Guest Ids (Code)        │
│  Extract guest_ids array        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Loop Over Items (Batch)        │  ◄─── LOOP BACK
│  Process each guest separately  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Get the guest (Supabase)       │
│  Query: users table by guest_id │
│  Connection: CoralTriangle      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Create Gmail in guests lang    │
│  JavaScript Code Node           │
│  • 4 language templates (EN,ES,│
│    ZH, FR)                      │
│  • Multi-language email HTML    │
│  • Personalizes with guest data │
│  • Builds onboarding URL        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Send an email (Gmail)          │
│  Send HTML email to guest       │
│  Credential: Unknown Gmail      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Wait (Pause)                   │
│  Allow time before next loop    │
└──────────────┬──────────────────┘
               │
               └──► Back to Loop Over Items
```

### 🔧 Node Details

| # | Node | Type | Purpose | Config |
|---|---|---|---|---|
| 1 | On a new booking | Webhook | Listen for POST requests | Path: `new-booking`, Responds immediately |
| 2 | Get booking details | Code | Extract booking record from webhook body | JavaScript extraction logic |
| 3 | Filter Guest Ids | Code | Extract guest_ids array for iteration | Returns array of guest_id objects |
| 4 | Loop Over Items | Split in Batches | Process guests one at a time | Batch size: 1 (sequential) |
| 5 | Get the guest | Supabase | Query guest info from database | Table: `users`, Filter: id = guest_id |
| 6 | Create Gmail | Code JS | Generate multilingual HTML email | 4 language templates, 480+ lines |
| 7 | Send an email | Gmail | Send using Gmail API | Credential: Gmail OAuth2 |
| 8 | Wait | Wait | Pause before looping | Default 1s wait |

### 🌍 Language Support

The workflow supports **4 languages** with fully localized email templates:

- **English (en)** - Default
  - Subject: "Booking Confirmation - Your Dive Adventure Awaits!"
  - Full HTML email with formatted table
  
- **Spanish (es)**
  - Subject: "Confirmación de Reserva - ¡Tu Aventura de Buceo Te Espera!"
  - Spanish localization with peso symbols
  
- **Chinese (zh)**
  - Subject: "预订确认 - 您的潜水冒险等待您！"
  - Chinese date/time formatting (YYYY年MM月DD日)
  
- **French (fr)**
  - Subject: "Confirmation de Réservation - Votre Aventure de Plongée Vous Attend !"
  - French formatting standards

### 📧 Email Template Features

```html
Personalized Greeting
↓
Booking Details Table (Date, Time, Guests, Total Amount)
↓
Special Requests (if provided)
↓
Booking Status Badge
↓
Call-to-Action Button → Onboarding URL
↓
Professional Footer
```

**Onboarding URL Pattern:** `http://localhost:3000/onboard/{booking.id}`

### 💾 Credentials Used

- **Gmail:** Unknown's Gmail account (OAuth2)
- **Supabase:** CoralTriangle Supabase Account
  - Database: users table
  - Query: guest_id lookup

### 📈 Execution Characteristics

- **Trigger:** Webhook (event-driven, real-time)
- **Response Mode:** Immediate (replies to webhook immediately)
- **Processing:** Sequential (loops through each guest)
- **Frequency:** Triggered per booking
- **Version:** v48 (highly iterated)
- **Status:** Active and running

---

## Workflow 2: "Ad Performance Monitor" ✅ ACTIVE

**ID:** `GsUauTMJt3r8tGjX`  
**Status:** ✅ Running  
**Type:** Scheduled (Daily)  
**Last Updated:** 2026-03-18  

### 🎯 Purpose
Monitor AdSense performance metrics daily at 9 AM and send alerts if anomalies detected.

### 📊 Workflow Flow Diagram

```
┌──────────────────────────────────┐
│  Daily Schedule (9 AM)           │
│  Trigger: Every day at 9:00 AM  │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  Fetch AdSense Metrics           │
│  HTTP Request to AdSense API     │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  Analyze Metrics                 │
│  Code Node: Process data         │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  Check for Anomaly               │
│  IF Node: Decision point         │
└────────┬──────────────────┬──────┘
         │ (Anomaly)        │ (Normal)
         ▼                  ▼
    ┌──────────┐      ┌──────────┐
    │Send Alert│      │Send Alert│
    │Email     │      │(Normal)  │
    └────┬─────┘      └────┬─────┘
         │                 │
         └────────┬────────┘
                  ▼
      ┌──────────────────────┐
      │  Log Metrics to      │
      │  Google Sheets       │
      └──────────────────────┘
```

### 🔧 Node Details

| # | Node | Type | Purpose | Config |
|---|---|---|---|---|
| 1 | Daily Schedule (9 AM) | Schedule Trigger | Run daily at 9 AM UTC | Cron-based scheduling |
| 2 | Fetch AdSense Metrics | HTTP Request | Query AdSense API | GET request with API auth |
| 3 | Analyze Metrics | Code | Calculate anomalies | JavaScript analysis |
| 4 | Check for Anomaly | IF (Conditional) | Branch on anomaly detection | Compares vs baseline |
| 5 | Send Alert Email | Gmail | Send alert if needed | Conditional send |
| 6 | If | IF (Conditional) | Secondary routing | Determines logging |
| 7 | Log Metrics to Sheets | Google Sheets | Append metrics row | Append operation |

### 📈 Execution Characteristics

- **Trigger:** Schedule (9 AM daily)
- **Frequency:** Once per day
- **Integrations:** 
  - AdSense API
  - Gmail
  - Google Sheets
- **Status:** Active

---

## Workflow 3: "iOptimize - Scrape Company Internal News" ✅ ACTIVE

**ID:** `3bWcaJGrEaGEfguq`  
**Status:** ✅ Running  
**Type:** Data Pipeline (109 nodes!)  
**Complexity:** VERY HIGH  
**Nodes:** 109 (largest active workflow)  
**Last Updated:** 2025-12-20  

### 🎯 Purpose
Automated web scraping of company internal news and content, storing results in Airtable database.

### 📊 Large Workflow (109 nodes) - Simplified Overview

```
┌─────────────────────────────────┐
│  Trigger                        │
│  (Schedule / Manual / Webhook)  │
└──────────────┬──────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │  Data Collection Phase   │
    │  (Multiple scrape nodes) │
    └──────────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────┐
    │  Data Processing         │
    │  (Transform, parse)      │
    └──────────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────┐
    │  Deduplication           │
    │  (Remove duplicates)     │
    └──────────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────┐
    │  Storage                 │
    │  (Save to Airtable)      │
    └──────────────────────────┘
```

**This is a complex data pipeline with 109 interconnected nodes!**

---

## Summary: Your Active Workflows

| Workflow | Status | Type | Nodes | Purpose |
|---|---|---|---|---|
| **Booking Notifications** | ✅ ACTIVE | Webhook | 8 | Real-time multilingual booking emails |
| **Ad Performance Monitor** | ✅ ACTIVE | Scheduled | 7 | Daily AdSense metrics monitoring |
| **iOptimize Company News** | ✅ ACTIVE | Pipeline | 109 | Web scraping to Airtable |
| **iOptimize Honors/Awards** | ✅ ACTIVE | Pipeline | 9 | Employee honors data collection |
| **iOptimize Employee Articles** | ✅ ACTIVE | Pipeline | 15 | Article scraping automation |
| **iOptimize Employee Activities** | ✅ ACTIVE | Pipeline | 10 | Activity tracking pipeline |
| **iOptimize LinkedIn + RSS** | ✅ ACTIVE | Pipeline | 23 | Multi-source content aggregation |
| **iOptimize Company Mission** | ✅ ACTIVE | Pipeline | 17 | Mission statement extraction |
| **PI - AI Blueprint_3** | ✅ ACTIVE | AI Pipeline | 64 | Advanced AI processing (64 nodes) |
| **RA - Error Logger** | ✅ ACTIVE | Monitor | 5 | Error tracking and logging |
| **Marketing Dashboard** | ✅ ACTIVE | Monitor | 3 | Dashboard update automation |

---

**Generated:** May 15, 2026, 9:43 AM (UTC+7)  
**Source:** n8n Cloud API via n8n-MCP
