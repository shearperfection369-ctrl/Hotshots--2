# Tennant TMS · HUD Command Center

A production-grade Transportation Management System built for **Tennant Companies** — a dark, cyber/HUD-styled, single-pane-of-glass dispatch console that tracks every shipment across every mode (TL · LTL · Parcel · Ocean · Air · Rail) and gives the team the tools they use *every day*: dispatch, booking, BOL generation, yard tracking, trade compliance, and Microsoft Copilot.

> Production: **https://livecleans.com**  ·  Preview/Dev: **https://clean-logistics-dash.preview.emergentagent.com**

---

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | React 19 · React Router · Tailwind · shadcn/ui · lucide-react · Recharts · Leaflet · Sonner |
| Backend | FastAPI · Python 3.11 · Motor (async MongoDB) · GridFS · OpenPyXL · Playwright (offline screenshots) |
| Database | MongoDB |
| AI | Microsoft Copilot launcher (deep-links to copilot.microsoft.com) |
| Email | **MOCKED** — `_do_send_email()` logs to `db.outbound_emails`; ready to swap in SendGrid via `SENDGRID_API_KEY` |
| Auth | JWT session tokens + role-based access (admin · dispatcher · auditor · carrier) |

The full stack runs in a Kubernetes pod under **supervisor**. Hot-reload is enabled on both services — you do not need to restart manually unless you change `.env` or install new dependencies.

---

## Repository Layout

```
/app
├── README.md                         ← you are here
├── backend/
│   ├── server.py                     ← FastAPI app (≈5700 lines, all routers in one file)
│   ├── equipment_module.py           ← OpenPyXL parser for daily yard XLSX uploads
│   ├── requirements.txt
│   ├── seed_assets/
│   │   └── routing-guide.pdf         ← Tennant Inbound Routing Guide (Rev 29, seeded to GridFS)
│   └── tests/                        ← pytest cases per iteration
│
├── frontend/
│   ├── public/
│   │   └── promo.mp4                 ← 39.6s "Built for the Team's Day" promo
│   └── src/
│       ├── App.js                    ← React Router routes
│       ├── components/
│       │   ├── Sidebar.jsx           ← nav
│       │   ├── Topbar.jsx
│       │   ├── MiniCalendar.jsx      ← Command Center mini calendar w/ live event badges
│       │   ├── DraggableTiles.jsx    ← per-user layout persistence wrapper
│       │   ├── TruckloadBookingSheet.jsx  ← Excel-style real-time booking grid
│       │   ├── QuotesTicker.jsx
│       │   └── ui/                   ← shadcn primitives
│       ├── lib/
│       │   ├── api.js                ← axios instance, BACKEND_URL helper
│       │   └── auth.js               ← AuthContext + useAuth()
│       └── pages/
│           ├── Dashboard.jsx         ← Command Center (map, KPIs, weather, news, calendar)
│           ├── Shipments.jsx
│           ├── Workbook.jsx          ← Truckload Booking Sheet host
│           ├── Documents.jsx         ← BOL archive (GridFS)
│           ├── RoutingGuide.jsx      ← inbound routing PDF + email
│           ├── Equipment.jsx         ← Yard tracker (drop daily XLSX)
│           ├── TradeCompliance.jsx   ← Incoterms · 301 · 232 · FTZ · broker
│           ├── MicrosoftCopilot.jsx  ← Copilot launcher (replaces HUDLINK AI)
│           ├── Machines.jsx          ← 35-model Tennant catalog
│           ├── CarrierRates.jsx      ← 80+ carrier rate decks
│           └── …
│
├── scripts/
│   ├── build_promo_with_screens.py   ← Builds /frontend/public/promo.mp4 from live screenshots
│   ├── capture_tms_screens_pw.py     ← Playwright authenticated screenshot capture
│   └── scrape_tennant_images.py
│
├── memory/                            ← agent memory (PRD, credentials, plan)
│   ├── PRD.md                         ← Product requirements + version log
│   └── test_credentials.md            ← Admin/dispatcher test tokens
│
└── test_reports/
    └── iteration_*.json               ← testing-agent results per iteration
```

---

## Running Locally

You don't normally need to run anything by hand — supervisor handles both services in the cloud pod. If you've cloned the repo and want to run it yourself:

### Prerequisites
- Python 3.11+
- Node 18+ with `yarn`
- MongoDB running locally (or a hosted URI)
- An `EMERGENT_LLM_KEY` if you want to enable any Claude/Gemini features

### Backend
```bash
cd backend
pip install -r requirements.txt
# Configure backend/.env
cp backend/.env.example backend/.env   # if provided; otherwise create one
# MONGO_URL=mongodb://localhost:27017
# DB_NAME=tennant_tms
# EMERGENT_LLM_KEY=sk-emergent-...
# JWT_SECRET=change-me
# EMAIL_FROM=transportation@tennantco.com
# SENDGRID_API_KEY=                    # leave empty to keep email mocked
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
# frontend/.env
# REACT_APP_BACKEND_URL=http://localhost:8001
yarn start
```

Then visit http://localhost:3000. Sign in with the admin credentials in `/app/memory/test_credentials.md`.

---

## Major Features

### Command Center (`/dashboard`)
A single screen the team checks every morning. Live geo-spatial tracker (Leaflet), KPI strip, facility weather (NOAA-style mocks), traffic alerts, news ticker, and a 240px **MiniCalendar** at top-right that fetches `GET /api/calendar/events` and badges every date with shipment/booking events. Click a date to drill into that day's pickups, deliveries, and ETAs.

Every section is **draggable** — each user's layout saves automatically to `/api/user/layouts/dashboard` (debounced 400ms). "Reset Layout" reverts to default.

### Truckload Booking Sheet (`/workbook`)
Excel-style real-time grid backed by `/api/workbook/truckload-bookings`. Click any cell, edit, blur to save. Other dispatchers see the new value within 4 seconds (lightweight version polling).

- **Carrier column is a combobox** — onboarded carriers (status=approved) appear in the dropdown; dispatchers can pick or type a new name.
- **Auto-onboarding** — typing a brand-new carrier name auto-creates a `carrier_onboarding` stub with `status=in_review` so the compliance team can chase down W-9 + COI + contract. Case-insensitive dedupe.

### Shipments (`/shipments`)
One table for every mode. Edit in place, drag-reorder columns, soft-delete with audit trail, SAP deep-links on Order/Material/BOL fields.

### Documents (`/documents`)
- Generate BOLs from any shipment.
- All uploads stored in GridFS with version history.
- Amend with reason + diff trail (audit compliance).
- Mailto/SendGrid send (currently **MOCKED**).

### Routing Guide (`/routing-guide`)
Tennant's Domestic US/CA/MX Inbound Routing Guide (Rev 29, eff. 2026-01-09) seeded into GridFS bucket `routing_guides`. Public PDF endpoint at `/api/routing-guide/pdf` (no auth — so external suppliers can open the link from any mailbox).

- **Email to Customer** — one-click mailto or backend-API send (currently **MOCKED**, logs to `db.outbound_emails`).
- **Admin upload** — drop a new PDF, set revision + effective date, and it becomes the active version.

### Equipment / Yard Tracker (`/equipment`)
Drop the daily Excel yard report and get:
- KPI strip (total on site, doors occupied, loaded in/out, empty trailers, sealed %)
- Live door map (per-door status grid)
- Carrier mix (pie)
- Loaded-inbound dwell histogram + hot-list of stale trailers
- Historical trend across uploaded reports
- 4 sortable tables (loaded inbound · loaded outbound · empty trailers · empty containers)

Powered by `openpyxl` parser in `backend/equipment_module.py`.

### Trade Compliance (`/trade-compliance`)
All 11 **Incoterms 2020** rule cards (FCA, FOB, CFR, CIF, CPT, CIP, DAP, DPU, DDP, EXW, FAS) with risk/insurance/cost breakdowns and Tennant's standard use per term. Plus HTS tariff schedules, Section 301 tracker, Section 232 steel/aluminum scope, USMCA/KORUS/FTZ programs, denied-parties screening status, UPS_SCS broker portal, and key regulations registry.

### Microsoft Copilot (`/copilot`)
Replaces the legacy HUDLINK AI module. Brand-correct Microsoft launcher with:
- 4 surfaces: consumer Copilot, M365 Copilot, GitHub Copilot, Edge Sidebar
- 6 one-click deep-link prompts to `copilot.microsoft.com?q=…`
- Embed attempt + graceful fallback (Microsoft sends X-Frame-Options DENY)

### Machine Catalog (`/machines`)
35 live Tennant models with real CDN images (auto-generated branded SVG fallbacks for missing assets). Linked from shipments and BOLs.

### Carrier Rates (`/carrier-rates`)
80+ carrier rate decks · MSAs · lanes · accessorials. Side-by-side compare before tendering.

### Promo Video (`/promo.mp4`)
A ~97-second offline-rendered `.mp4` ("Built for the Team's Day · v2 Launch") composed of authenticated Playwright screenshots + branded slides via FFMPEG. **Now with AI narration** (OpenAI TTS via Emergent universal key) and a synthesized ambient music bed — fully self-contained, corporate-firewall-safe. Covers all 18 flagship v2 modules including Power BI, SharePoint, Microsoft Copilot, Specialty Carriers, Routing Guide, the 45-metric Carrier Scorecard, the Driver Registry and the Arcade.

Re-build with narration any time:
```bash
python3 /app/scripts/build_promo_with_screens.py
```

Re-generate just the narration:
```bash
python3 /app/scripts/generate_promo_narration.py
```

---

## v2 Launch Capabilities (new since v1.9)

| Module | Sidebar | Highlights |
| --- | --- | --- |
| **Microsoft Copilot** | `/copilot` | In-workspace launcher · 4 surfaces · 6 deep-link prompts · replaces legacy HUDLINK AI |
| **Power BI** | `/powerbi` | Embedded finance / ops / executive dashboards · drill filters carry across tiles |
| **SharePoint** | `/sharepoint` | Native document libraries · M365 AD permissions roll-up · per-shipment deep links |
| **Specialty Carriers** | `/specialty-carriers` | Logix · ArcBest Panther · Fastfrate · Ryan · live status + rates |
| **Routing Guide** | `/routing-guide` | One-click PDF distribution to all suppliers (SendGrid MOCKED) · version history |
| **Supplier Sourcing (manual entry)** | `/suppliers` | Add vendors manually · risk, spend, single-source · 20 seeded + custom |
| **Driver & Trailer Registry** | `/driver-registry` | CDL, medical, endorsements (HAZMAT/TANKER/TWIC), DOT inspection · color-coded expiry |
| **45-Metric Carrier Scorecard** | `/reports` | OTD, on-time pickup, tender accept, claims %, dwell, accessorial spend, +40 more |
| **Arcade · Solo Chess** | `/arcade` | Connect 4 + Chess vs HUDLINK engine · tournaments · leaderboard |
| **Global Search (Cmd-K)** | Topbar | Shipments, BOLs, carriers, suppliers, SAP PO/SO/Invoice deep links |
| **16 Visual Themes** | Topbar palette | Cyan · Forest · Sunset · Arctic · Lavender · Mocha · Solar · Tennant Brand · Neon Tokyo · Matrix · Amber CRT · Midnight Steel · Rose Quartz · Carbon Fiber · Paper White · High-Vis Safety |
| **Weather Radar + Alerts** | Topbar + `/tracking` | NOAA-style storm overlay · severe-weather alert banner |
| **Universal Draggable Tiles** | most pages | Per-user layout persistence to `/api/user/layouts/{page_key}` |
| **Truckload Sheet Carrier Dropdowns** | `/workbook` | Onboarded carriers in combobox · auto-creates onboarding stub on type-new |
| **AI-Narrated Launch Promo** | `/promo` | OpenAI TTS narration + ambient music bed · 18 flagship modules |

---

## API Conventions

- All backend routes are prefixed `/api/` so Kubernetes ingress routes them to port 8001.
- Auth: send `Authorization: Bearer <session_token>` **or** the `session_token` cookie. See `/app/memory/test_credentials.md` for current tokens.
- Roles enforced via `Depends(require_role("admin", "dispatcher", "auditor", "carrier"))`.
- All responses exclude Mongo `_id`.
- Datetimes are stored as ISO strings in UTC.

### Key endpoints (cheat sheet)

| Path | Verb | Purpose |
| --- | --- | --- |
| `/api/auth/login` `/api/auth/me` | POST/GET | Auth |
| `/api/shipments` `/api/shipments/{id}` | CRUD | Shipments |
| `/api/workbook/truckload-bookings` | CRUD + PATCH | Real-time booking grid (auto-onboards new carriers) |
| `/api/workbook/truckload-bookings/version` | GET | Lightweight version poll |
| `/api/calendar/events?start=&end=` | GET | Aggregated pickup/delivery/ETA events |
| `/api/user/layouts/{page_key}` | GET/PUT/DELETE | Per-user draggable layout persistence |
| `/api/equipment/upload` `/equipment/reports` `/equipment/analytics` | POST/GET | Yard tracker |
| `/api/carriers/onboarding` | GET/POST | Carrier compliance pipeline |
| `/api/routing-guide/info` `/pdf` `/email-template` `/send-email` `/upload` `/versions` | mixed | Inbound routing guide |
| `/api/email/send` `/api/email/log` | POST/GET | Generic email (MOCKED) |
| `/api/machines/{model}/image.svg` | GET | Branded SVG fallback for missing catalog images |
| `/api/kpis` `/api/sap/*` `/api/news` `/api/weather/*` | GET | Mocked feeds |

---

## Data Model (key collections)

- `users` — auth + roles
- `shipments` — primary cargo records (all modes)
- `truckload_bookings` + `truckload_bookings_meta` — live booking grid + version counter
- `bol_uploads` — GridFS bucket for generated BOLs
- `routing_guides.files` / `.chunks` — GridFS for inbound routing PDFs
- `carrier_onboarding` — compliance pipeline (status=in_review/approved)
- `carrier_rates` · `lanes` · `freight_audits`
- `yard_reports` — parsed daily Excel uploads
- `outbound_emails` — MOCKED email log (swap to real SendGrid by editing `_do_send_email()`)
- `user_layouts` — `{ user_id, page_key, layout_order }`

---

## Testing

```bash
# Backend
cd /app && pytest backend/tests/

# Frontend smoke (Playwright handled by testing agent)
# Lint
ruff check backend/
eslint frontend/src --ext .js,.jsx
```

Most testing is done by the in-platform **testing agent** which writes results to `/app/test_reports/iteration_*.json`. Latest = `iteration_14.json`.

---

## Credentials & Roles

See `/app/memory/test_credentials.md`. Pre-seeded:
- `Test Admin` (admin) — bearer `test_session_admin_1`
- Dispatcher — bearer `test_disp_session`

The 4 roles are `admin`, `dispatcher`, `auditor`, `carrier`. Sidebar entries are filtered by role.

---

## Production vs Preview

| Environment | URL | Who controls it |
| --- | --- | --- |
| **Preview / Dev** | `clean-logistics-dash.preview.emergentagent.com` | The agent — every code change goes here first |
| **Production** | `livecleans.com` | The user, via the Emergent "Deploy" button |

If a feature looks missing in production, redeploy from the preview environment.

---

## Common Tasks

### Add a new approved carrier
1. POST `/api/carriers/onboarding` with full info, then mark approved.
2. Restart the backend once (or wait for the next dispatcher to refresh) — the carrier will appear in the Truckload Booking Sheet's dropdown.

### Roll out a new Routing Guide revision
1. Go to `/routing-guide` (admin or dispatcher).
2. Click **Upload New Revision**, pick the PDF, set revision label + effective date.
3. The new version becomes "active" immediately (most recent uploadDate wins).

### Flip email from MOCKED to real SendGrid
1. Verify `transportation@tennantco.com` in SendGrid → Sender Authentication (or do full domain auth).
2. Paste the API key into `backend/.env` as `SENDGRID_API_KEY`.
3. Open `backend/server.py`, find `_do_send_email()`, and swap the mock body for the SendGrid SDK call (see the SendGrid playbook in chat history). All call sites (`/email/send`, `/routing-guide/send-email`, BOL emails) pick up the change automatically.

### Add a new draggable page
1. Wrap the page sections in `<DraggableTiles pageKey="my-page" defaultOrder={[…]} tiles={{ … }} />`.
2. Each user's order auto-saves to `/api/user/layouts/my-page`. Done.

---

## Version Log

See `/app/memory/PRD.md` for the running version log. Recent highlights:

- **v2.0 (Launch)** — Power BI · SharePoint · Microsoft Copilot · Specialty Carriers · Driver/Trailer Registry · 45-metric Carrier Scorecard · Solo Chess · Global Search (Cmd-K) · 16 Visual Themes · Weather Radar + Alerts · AI-narrated launch promo (OpenAI TTS + ambient music)
- **v1.9** — Universal draggable tiles · MiniCalendar · new promo video
- **v1.8** — Compact drag-and-drop Command Center
- **v1.7** — Truckload Booking Sheet, Equipment/Yard Tracker, BOL emailing
- **v1.6** — 35-model machine catalog, Incoterms cards, drag-reorder columns
- **v1.5** — Initial production MVP

---

## License & Contact

Internal Tennant Companies tooling. For questions: `transportation@tennantco.com`.

Built with **Emergent** · `https://app.emergent.sh`
