# Sophie GHL Conversation AI — Agent Studio Configuration

## Overview

Sophie is a GoHighLevel Conversation AI chatbot deployed via Agent Studio. This document captures the full configuration for reproducibility.

## Agent Details

| Field | Value |
|-------|-------|
| Agent Name | Sophie (Discovery Booking) |
| Agent Type | Conversation AI (Chat Widget) |
| Model | OpenAI GPT 4.1 via GHL Conversation AI |
| Base Language | English |
| Widget Type | Chat Bubble (embed on website) |

## Widget Configuration

- **Start Message**: Welcome greeting with introduction
- **Qualification Thresholds**:
  - Income: ≥ threshold (configurable per client)
  - Accessible Equity: ≥ threshold (configurable per client)
- **Required Fields for Booking**: Email, Mobile, Timezone

## Lead Qualification Flow

```
Visitor → Greeting → Income Check → Equity Check → Qualified?
    ├── Yes → Collect info (name → email → phone → timezone)
    │         → Show calendar slots → Prospect picks slot
    │         → Summary confirmation → Booking created in GHL
    │         → Tag: discovery-booked → Pipeline: Discovery
    └── No  → Nurture message → Tag: nurture-not-qualified
              → Added to nurture campaign
```

## Information Collection (Sequential)

| Step | Field |
|------|-------|
| 1 | Full name |
| 2 | Email for booking confirmation |
| 3 | Mobile with country code |
| 4 | City/area (timezone inferred automatically) |

## Booking Flow

After collecting info, Sophie presents up to 6 available calendar slots. Prospect selects a slot → gets a summary confirmation → booking is created in GHL CRM.

## Webhook Integration

On booking confirmation:
- Contact created/updated in GHL CRM (name, email, phone, timezone)
- Custom fields populated (income, equity from conversation)
- Tag applied: `discovery-booked`
- Appointment created on GHL Calendar

## Stress Test Results

| Metric | Result |
|--------|--------|
| Message flow (12-step conversation) | 12/12 passed |
| Backend verification | All fields captured correctly |
| Calendar booking integration | Verified working |
| Widget rendering | Confirmed on target pages |
