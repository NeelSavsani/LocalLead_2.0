# LocalLeadPulse Architecture & Technical Specifications

## 1. System Overview

LocalLeadPulse is an automated B2B lead generation engine specifically built to discover brick-and-mortar businesses lacking an official, independent website and compile high-intent outreach lists with pre-configured CRM fields.

```
                  ┌───────────────────────────────┐
                  │ Next.js 14+ Frontend Dashboard │
                  └──────────────┬────────────────┘
                                 │
                  HTTP POST /start & SSE /stream
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   FastAPI Orchestrator Loop   │
                  │   (Limit Enforcement: N)      │
                  └──────────────┬────────────────┘
                                 │
             ┌───────────────────┴───────────────────┐
             │ Layer 1: Google Maps Presence         │
             │ Does listing have websiteUri?         │
             └─────────┬─────────────────────────────┘
                       │ YES ──► Discard (Has Website)
                       │
                       ▼ NO
             ┌───────────────────────────────────────┐
             │ Layer 2: Organic Search Engine Check  │
             │ Query: "{Business Name}" "{Location}" │
             │ Exclude: Aggregators & Social Media   │
             └─────────┬─────────────────────────────┘
                       │ Domain found outside blacklist ──► Discard
                       │
                       ▼ Only blacklisted or no results
             ┌───────────────────────────────────────┐
             │       Qualified Lead Accepted         │
             │ Increment counter: Count / Limit      │
             └─────────┬─────────────────────────────┘
                       │
                       ▼
             ┌───────────────────────────────────────┐
             │   OpenPyXL Styled Excel Generator     │
             │   (.xlsx with CRM Dropdown Pane)      │
             └───────────────────────────────────────┘
```

## 2. Two-Layer Verification Engine

### Layer 1: Google Maps / Places Metadata
- Inspects business entity from Google Places API or spatial scraper.
- Immediate filter: If `websiteUri` or `website` is present, business is immediately discarded as non-target.

### Layer 2: Deep Organic Search Verification
- Queries organic web results for `"{Business Name}" "{Location}"`.
- Parses top 5 search result domains.
- Strips subdomains and tests against `EXCLUDED_DOMAINS` blacklist (directories, food delivery aggregators, social profiles).
- If any organic result links to a dedicated private domain matching the business, it is marked as having a website (false negative on Maps) and excluded.
- If no dedicated domain is discovered, business is verified as an active, website-less lead.

## 3. Strict Limit Enforcement
- Orchestrator tracks `qualified_count`.
- Immediately halts network requests when `qualified_count == target_limit`.
- Transitions scanning job state to `COMPLETED` and produces the `.xlsx` workbook.
