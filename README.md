# LocalLeadPulse: AI-Powered B2B Lead Generator for Local Businesses Without Websites

LocalLeadPulse is an automated B2B lead generation platform and pipeline designed for digital marketing agencies, freelance developers, and sales teams. It discovers local brick-and-mortar stores (cafes, garages, restaurants, clinics, repair shops, etc.) within a user-specified geographic radius (e.g., Gandhinagar, Gujarat), performs a **two-layer automated verification** to ensure the business does not possess a live standalone website, and exports qualified, outreach-ready contact leads into a beautifully formatted Excel (.xlsx) file.

---

## 1. Executive Summary & Problem Statement

Many local businesses thrive via word-of-mouth or local footfall but lack an independent digital presence:
1. **Google Maps Data Gap**: Often, a shop appears on Google Maps with no website listed on its profile. However, some of these businesses actually have an official website that the owner simply never linked to Google Business Profile.
2. **Directory Noise**: Running a simple internet search reveals aggregator profiles (Justdial, IndiaMART, Zomato, Swiggy, Facebook pages), which are NOT independent official websites.
3. **Agency Goal**: Sales teams need a high-precision pipeline that:
   - Filters out false positives (businesses that already have their own standalone domain).
   - Collects verified leads with business name, category, phone number, and physical address.
   - Enforces a strict user-defined **Limit** (e.g., 10, 20, 50 leads) to prevent wasted compute, API rate limits, and lead saturation.
   - Exports directly to an Excel sheet pre-configured with cold calling CRM columns (Call Status, Pitch Angle, Owner Details).

---

## 2. Core Functional Requirements

### 2.1 User Inputs & Controls
* **Target Location / Area**: Free-text city or neighborhood input (e.g., `"Gandhinagar, Gujarat"` or `"Kudasan, Gandhinagar"`).
* **Business Categories / Keywords**: Multi-select or custom text (e.g., `Cafe`, `Auto Garage`, `Restaurant`, `Pharmacy`, `Dentist`, `Hardware Store`).
* **Lead Limit (Cap)**: Integer field (`10`, `20`, `50`, `100`). The engine halts scraping as soon as the target count of verified website-less leads is collected.
* **Search Engine Provider Toggle**: Support for Google Places API + SerpAPI / Custom Search API, or built-in Playwright automated browser fallback.
* **Mock / Demo Mode**: Offline toggle using pre-cached sample local data for instant testing without consuming API credits.

### 2.2 Two-Layer Verification Engine

```
[Store Found via Maps Query]
          │
          ├── Layer 1 Check: Does Google Maps listing have a website URI?
          │     ├── YES ──► [Disqualified / Ignored]
          │     └── NO  ──► [Proceed to Layer 2]
          │
          └── Layer 2 Check: Query Google Search for `"{Business Name}" "{Location}"`
                │
                ├── Parse Top 5 Organic Search Results
                ├── Check domains against Aggregator / Social Blacklist:
                │     (justdial.com, indiamart.com, facebook.com, instagram.com,
                │      zomato.com, swiggy.com, sulekha.com, jdmagicbox.com, etc.)
                │
                ├── If an independent, non-blacklisted domain is found:
                │     └── [Disqualified: False Negative on Maps - Business owns a site]
                │
                └── If NO independent domain exists (only directories or no results):
                      └── [QUALIFIED LEAD] ──► Extract info & increment lead counter
```

### 2.3 Excel Export Engine
Outputs a stylized `.xlsx` workbook using `openpyxl` with:
- Frozen header pane with dark navy fill (`#1E293B`) and white bold text.
- Data columns:
  1. `ID`
  2. `Shop / Business Name`
  3. `Category`
  4. `Contact Number` (formatted as phone string)
  5. `Full Physical Address`
  6. `Area / Landmark`
  7. `Google Maps URL`
  8. `Web Search Verification Status` (`No Standalone Website Found`)
  9. `Call Status` (Excel Data Validation dropdown: `To Call`, `Called - Interested`, `Called - Not Interested`, `Follow Up`, `Converted`)
  10. `Pitch Angle / Opportunity` (e.g., `"Needs booking system"`, `"Needs digital menu"`, `"Online catalog"`)
  11. `Lead Identified Date`

---

## 3. Technology Stack

* **Backend Framework**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2
* **Data Processing & File Export**: Pandas, OpenPyXL
* **Scraping & Verification**:
  - Primary: Google Places API (New) + Google Custom Search JSON API / SerpAPI
  - Secondary / Free Fallback: Playwright (Headless Chromium) with stealth evasion and DuckDuckGo / Bing / Google direct search scraping
* **Frontend**: Next.js 14+ (App Router) or Vite + React, Tailwind CSS, Lucide Icons, Shadcn UI
* **Real-Time Communication**: Server-Sent Events (SSE) or WebSockets for live scanning logs, progress bar, and streaming table updates

---

## 4. Project File Structure

```text
local-lead-pulse/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI server entry point & CORS
│   │   ├── config.py                   # Environment variables & API keys
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py               # REST & SSE streaming endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py              # Orchestration loop enforcing lead limits
│   │   │   ├── places_service.py       # Google Places API / Maps scraper
│   │   │   ├── search_verifier.py      # Layer 2 Google/DDG search verifier
│   │   │   └── excel_exporter.py       # Styled OpenPyXL workbook generator
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py              # Pydantic schemas (ScanRequest, LeadItem)
│   ├── tests/
│   │   ├── test_verifier.py
│   │   └── test_exporter.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx                # Single-page dashboard & search interface
│   │   ├── components/
│   │   │   ├── LeadSearchForm.tsx      # Location, category, limit input
│   │   │   ├── LiveProgress.tsx        # Real-time counter & scanning feed
│   │   │   ├── LeadTable.tsx           # Interactive results table
│   │   │   └── ExportButton.tsx        # Trigger & download .xlsx file
│   │   └── lib/
│   │       └── api.ts                  # Axios/Fetch client
│   ├── package.json
│   ├── tailwind.config.js
│   └── tsconfig.json
├── docs/
│   ├── ARCHITECTURE.md
│   └── COLD_CALLING_SCRIPTS.md
└── README.md
```

---

## 5. Step-by-Step Implementation Instructions for Google Antigravity

Follow this sequential execution plan to implement and verify the entire system.

### Phase 1: Backend Foundation & Data Models
1. **Initialize Environment**:
   - Create Python virtual environment and install dependencies from `requirements.txt`:
     ```bash
     fastapi>=0.111.0
     uvicorn[standard]>=0.30.0
     pydantic>=2.7.0
     pandas>=2.2.0
     openpyxl>=3.1.2
     playwright>=1.44.0
     requests>=2.32.0
     beautifulsoup4>=4.12.0
     python-dotenv>=1.0.1
     ```
2. **Define Pydantic Models (`app/models/schemas.py`)**:
   - `ScanRequest`: `location` (str), `category` (str), `limit` (int, default 20), `use_mock` (bool).
   - `LeadRecord`: `id`, `name`, `category`, `phone`, `address`, `maps_url`, `has_maps_site` (bool), `has_web_site` (bool), `status`, `pitch_angle`.
   - `ScanProgress`: `processed_count`, `qualified_count`, `target_limit`, `current_business`, `is_completed`.

### Phase 2: Dual-Layer Verification Engine
1. **Build `search_verifier.py`**:
   - Define comprehensive aggregator blacklist:
     ```python
     EXCLUDED_DOMAINS = {
         "facebook.com", "instagram.com", "twitter.com", "x.com",
         "linkedin.com", "youtube.com", "justdial.com", "indiamart.com",
         "sulekha.com", "tradeindia.com", "yellowpages.in", "zomato.com",
         "swiggy.com", "magicbricks.com", "99acres.com", "tripadvisor.com",
         "jdmagicbox.com", "quikr.com", "olx.in", "wikipedia.org"
     }
     ```
   - Implement function `verify_independent_website(business_name: str, location: str) -> dict`:
     - Queries search engine (SerpAPI, Google Custom Search, or DDG HTML).
     - Extracts top 5 organic domain links.
     - Strips subdomains and checks if any URL is an independent business website outside the blacklist.
     - Returns `{"has_standalone_website": bool, "detected_urls": list}`.

2. **Build `places_service.py`**:
   - Implement location search via Google Places API or Playwright Maps scraping.
   - If Google Maps listing provides a direct `websiteUri`, immediately discard to minimize search overhead.
   - If website is missing, pipe business name and address to `search_verifier.py`.

3. **Build `scanner.py`**:
   - Manages scanning state and asynchronous queues.
   - Evaluates businesses one by one:
     - If disqualified, logs rejection reason.
     - If qualified, appends to `qualified_leads` list.
     - Increments `qualified_count`.
     - When `qualified_count >= request.limit`, cleanly terminates further requests and flags job as `COMPLETED`.

### Phase 3: Excel Report Generator (`excel_exporter.py`)
1. Create a styled spreadsheet using `openpyxl`:
   - Sheet Name: `"Qualified Leads - [Location]"`
   - Top Title Card: `"LOCALLEADPULSE B2B SALES PIPELINE - [LOCATION]"`, subtitle with scan date and target count.
   - Header Row: Dark slate fill (`#1E293B`), white bold text, row height 28pt.
   - Column Auto-Widths with clean padding.
   - Alternating row zebra shading (`#F8FAFC` and `#FFFFFF`).
   - Add dropdown validation for column `Call Status`:
     - List: `"Pending Call, Attempted, Interested - Demo Scheduled, Not Interested, Closed"`
   - Save to dynamic path `exports/leads_{job_id}.xlsx`.

### Phase 4: API Endpoints & Streaming (`routes.py` & `main.py`)
1. `POST /api/leads/start`: Starts background scan task, returns `job_id`.
2. `GET /api/leads/stream/{job_id}`: Server-Sent Events (SSE) streaming real-time JSON events:
   - `{ "event": "candidate_evaluated", "name": "...", "status": "REJECTED | QUALIFIED", "lead_count": 3, "limit": 10 }`
3. `GET /api/leads/results/{job_id}`: Returns JSON array of final qualified leads.
4. `GET /api/leads/download/{job_id}`: Serves the generated `.xlsx` binary file for browser download.

### Phase 5: Modern Dashboard Frontend
1. **Hero & Query Section**:
   - Input for Target City / Area (with Gandhinagar default suggestion).
   - Category selector pills (Cafe, Garage, Restaurant, Salons, Boutique, Clinics).
   - Number input with label **"Limit"** (Default: 20, Min: 1, Max: 100).
   - Start Scan button with loading spinners and disabled state handling.
2. **Live Scanning Telemetry**:
   - Real-time animated progress bar (`Qualified: X / Limit: Y`).
   - Live activity ticker displaying current shop being analyzed (e.g., *"Checking 'Maruti Car Care'... Maps: No site... Search: No site... QUALIFIED (1/10)"*).
3. **Data Table**:
   - Display qualified leads in real time as they arrive.
   - Badges for status, clickable phone numbers (`tel:+91...`), and address map links.
4. **Export Action**:
   - Green **"Download Excel Sheet (.xlsx)"** button that activates immediately upon job completion or when limit is reached.

---

## 6. Cold Calling & Outreach Playbook (Included in App)

To empower immediate monetization, provide a dedicated UI tab with battle-tested phone pitch templates:

### Script: Gandhinagar Local Business Cold Call
> **Sales Rep**: "Hello, is this the owner or manager of [Business Name]?"  
> **Owner**: "Yes, speaking. What is this about?"  
> **Sales Rep**: "Namaste sir/ma'am. I was looking for [services, e.g., car repairs/bakeries] near [Area, e.g., Kudasan / Infocity] on Google. I noticed that while your competitors have their own website where customers view menus and book directly, your Google listing doesn't have an official website attached."  
> **Owner**: "Yes, we don't have one right now."  
> **Sales Rep**: "We help local businesses in Gandhinagar get an affordable, clean website set up in 48 hours to get direct customer orders without hefty platform commissions. Would it be okay if I sent a 1-minute WhatsApp preview demo of what your website could look like?"

---

## 7. Configuration (`.env.example`)

```env
# Optional API Keys (Leave blank to use Playwright headless scraping mode)
GOOGLE_MAPS_API_KEY=""
GOOGLE_SEARCH_API_KEY=""
GOOGLE_SEARCH_ENGINE_ID=""

# Application Settings
DEFAULT_SEARCH_RADIUS_KM=10
DEFAULT_LEAD_LIMIT=20
MAX_LEAD_LIMIT=100
HEADLESS_BROWSER=true
MOCK_MODE=false
```

---

## 8. Verification & Acceptance Criteria for Antigravity

- [ ] **Limit Enforcement**: When Limit is set to `10`, the scanner strictly terminates after finding exactly 10 qualified leads, even if 200 candidates remain in the area.
- [ ] **Dual Check Accuracy**: A business with an unlisted website on Maps that nonetheless ranks #1 on Google Search under its exact brand name is correctly flagged and dropped.
- [ ] **Directory Exclusions**: A business whose only search results are Justdial and Facebook is correctly marked as having **NO website**.
- [ ] **Excel Usability**: The generated `.xlsx` file opens cleanly in Microsoft Excel / Google Sheets without formatting warnings and contains the pre-populated CRM dropdowns.
