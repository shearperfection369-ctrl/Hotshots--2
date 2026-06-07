# Tennant Companies TMS — PRD

## Original Problem Statement
Build a transportation management app (TMS) tailored for Tennant Companies. Heads-up dashboard (HUD) feel tracking all shipments across all modes. Integrations/mocks for SAP S/4HANA, SharePoint, PowerBI, and carriers like UPS, FedEx, DHL. Features: 250-user RBAC, load booking, document generation (BOL, invoices), real-time map, live weather/traffic/news, instant messaging, KPI tracking, HS code lookup, trailer sizes, and a workbook-style spreadsheet view.

Subsequent user-requested additions (chronological, all delivered):
- Shipment CRUD (edit/cancel/customize columns + soft delete)
- Weekly weights KPI fix
- In-app PowerPoint user manual
- Lift gates, pallet count, NMFC codes, freight class, length × width × height with density calc
- SAP S/4HANA Delivery picker for Book Load auto-fill
- Freight Payments & Claims tab
- Document Vault (Insurance COI / W-9 / contracts / MSDS)
- Part numbers from S/4HANA on Command tab + S/4HANA quick-access buttons
- Email Routing Guide & Carrier email composers (mailto + copy-to-clipboard)
- Carrier BOL storage (GridFS)
- Carrier Invites with scoped read-mostly portal
- Send Tennant Onboarding Packet email
- Trade Compliance tab (tariff/Section 301/232/sanctions/ACE/FTA)
- Supplier Sourcing tab (20 Tennant suppliers, risk scoring, FTA mapping)
- 100 Inspirational Quotes ticker on Command Center
- KPI report generate (PDF/XLSX) + email
- Tennant Machine Catalog (17 models, full-color images, specs)
- Arcade · Connect 4 with tournaments, brackets, trophies, tiered leaderboard
- Game challenges between any TMS users (inbox/outbox)
- 7 Visual Themes (HUD Cyan, Forest, Sunset, Arctic, Lavender, Mocha, Solar Light)
- Updated User Manual (.pptx) + Promo Video page content to reflect all v1.5 features

## Architecture
- Frontend: React 19, Tailwind, Shadcn UI, Recharts, Leaflet
- Backend: FastAPI (single `server.py`), MongoDB (Motor async), GridFS for vault & BOL storage
- Auth: Emergent Google OAuth + RBAC (admin / auditor / dispatcher / driver / carrier)
- AI: Claude Sonnet 4.5 via Emergent Universal Key
- Email: All mailto-mocked (per user choice) — endpoint returns subject/body/mailto link
- File storage: MongoDB GridFS buckets `vault` and `carrier_bols`

## Roles
- admin — everything
- auditor — read-most + audit + claims
- dispatcher — most write ops except carrier invites
- driver — driver console / mobile
- carrier — read-only scoped portal (only their own shipments)

## Test Credentials
- See `/app/memory/test_credentials.md`

## Implemented (v1.5 — May 2026)
- All 30+ modules listed in original PRD + recent additions
- 100+ API endpoints under `/api/`
- 59-slide in-app + downloadable user manual
- 7 swappable visual themes with localStorage persistence
- Connect 4 arcade with server-authoritative game logic

## Implemented (v1.6 — Feb 2026 hotfix)
- **Promo Video repair** — replaced broken `/promo.mp4` HEAD probe with a robust
  Content-Type check + YouTube iframe embed of the official "Tennant is Everywhere"
  trailer (video ID `mTxE3g7o4aY`). Page now reliably launches a real video.
  If a real Sora 2 `/promo.mp4` is later dropped into `/app/frontend/public`,
  the page auto-swaps to that local file.
- **Incoterms® 2020 section** — added a dedicated card in Trade Compliance covering
  all 11 ICC rules (EXW, FCA, FAS, FOB, CFR, CIF, CPT, CIP, DAP, DPU, DDP) with
  risk-transfer, cost split, insurance obligations, and a Tennant-specific
  usage note for each. Plus an E/F/C/D mnemonic block.
- **Scalable admin allow-list** — `ADMIN_EMAILS` env var (CSV) auto-promotes
  matching emails to `admin` role on Google sign-in (both new accounts and
  idempotently on every login for existing users). Currently seeded with
  `shearperfection369@gmail.com`. Other accounts default to `dispatcher`, keeping
  the 250-user model tidy.

## Implemented (v2.3 — Feb 2026, this session) — Industry-standard KPIs
- **Carrier Scorecard expanded from 5 → 45 metrics per carrier**, aligned with CSCMP / ATA /
  NASSTRAC / ISO 9001 transportation benchmarks. Composite score (weighted) drives an A+/F grade
  and a sortable ranked table. Sections: Service Quality (OTP, OTD, OTIF, tender accept,
  transit variance), Compliance/Quality (claims, damage, shortage, billing accuracy, EDI,
  POD), Safety/Regulatory (FMCSA CSA, OOS%, HOS violations, COI), Cost/Commercial
  (cost per mile, cost per load, FSC/mi, accessorial %, detention $, rate compliance),
  Capacity (utilization, committed loads, spot loads, response time), Sustainability
  (empty miles, CO₂/load, EV fleet %).
- **Network-wide industry metrics dashboard** — 41 KPIs across 6 categories
  (Service Quality · Cost Efficiency · Capacity Utilization · Compliance/Quality ·
  Safety/Regulatory · Sustainability). Every metric carries `value`, `target`, `benchmark`,
  `trend` and shows on-target colouring + delta arrows.
- **Specialty Carriers** — dedicated `/specialty-carriers` tab for Logix Transportation
  (white-glove pad-wrap), ArcBest Panther (expedite), Fastfrate (cross-border), and Ryan
  Transportation (capacity assurance). Each profile carries contact, specialty chips,
  YTD load count, on-time %, claim rate, and a direct tracking lookup that opens the
  carrier's public tracking page in a new tab.

## Implemented (v2.2 — Feb 2026)
- **Auto-onboard new carriers** (P2.1) — Typing a brand-new carrier name into the Truckload
  Booking Sheet's Carrier combobox now auto-inserts a `carrier_onboarding` stub with
  `status=in_review`, `auto_created=true`, and a "(pending)" contact placeholder so the
  compliance team can chase down W-9 + COI + contract. Backed by case-insensitive match on
  `legal_name` OR `dba` — dropdown labels like `"XPO · XPOL"` are stripped of their SCAC
  suffix before lookup, so picking from the dropdown never duplicates. Frontend shows a
  toast: *"New carrier sent to onboarding OB-XXXXXXXX · status: in_review · compliance team
  will gather W-9 + COI"*.
- **Calendar event aggregation** (P2.2) — New `GET /api/calendar/events?start=…&end=…`
  aggregates dated items from `shipments` (pickup_date, delivery_date, eta) and
  `truckload_bookings` (pickup_date, delivery_date) into a single feed with
  per-date count map. MiniCalendar on Command Center fetches the current month, draws
  a cyan badge on every date that has events, and (on click) opens a panel listing each
  event with type icon → react-router `<Link>` to /shipments?focus=… or /workbook.
- **Email send — MOCKED** (P2.3) — New `_do_send_email()` helper + `/api/email/send`,
  `/api/email/log`, `/api/routing-guide/send-email`. Currently writes to
  `db.outbound_emails` with `status="mocked"` and a `mock_<hex>` message_id. From-address
  is `transportation@tennantco.com`. Routing Guide's email dialog has two buttons now:
  **Open Mail Client** (mailto) and **Send Now (MOCKED)**. Flip on SendGrid later by
  pasting `SENDGRID_API_KEY` into `backend/.env` and swapping the body of `_do_send_email()`
  — every call site stays identical.


- **Inbound Routing Guide module** — Tennant's Domestic US/CA/MX Routing Guide (Rev 29, 2026-01-09)
  seeded into GridFS `routing_guides` bucket on first boot. New top-level page at `/routing-guide`
  with one-click "Email to Customer" (mailto + auto-generated subject/body containing a direct
  PDF download link). Admins/dispatchers can upload new revisions; full version history shown.
  PDF endpoint `/api/routing-guide/pdf` is **public** (no auth) so external suppliers can open
  the link from any mailbox.
- **Carrier dropdown on Truckload Booking Sheet** — Carrier column is now a combobox (HTML5
  `<datalist>`) sourced from `carrier_onboarding` records with `status == "approved"`. 13 carriers
  ship out of the box: XPO, ODFL, Saia, Estes, R+L, Knight, Schneider, C.H. Robinson, Werner,
  Lakeshore + 3 historical seeds. Dispatchers can pick an approved carrier OR type a new name.
  Idempotent backfill on every backend boot ensures the roster stays populated.
- **HUDLINK AI → Microsoft Copilot** — replaced the bespoke AI page with an official-branded
  Microsoft Copilot launcher (`/copilot`). Includes the four-square MS logo, 4 launcher tiles
  (Copilot, M365 Copilot, GitHub Copilot, Edge Sidebar), 6 one-click deep-link prompts to
  `copilot.microsoft.com?q=…`, and a graceful X-Frame-Options fallback ("Open Microsoft Copilot"
  CTA) since Microsoft refuses iframe embedding. `/ai-assistant` is now an alias to the new
  page; the legacy HUDLINK AI lives at `/legacy-hudlink` for fallback.


- **Universal per-user draggable tiles** — server-backed via `GET/PUT/DELETE /api/user/layouts/{page_key}`.
  Each user's layout is saved on their account (debounced 400ms) and reconciled against schema changes.
  Pages:
    - `/dashboard` — uses `useUserLayout("dashboard", …)` hook (its bespoke drag handles per section)
    - `/trade-compliance` — wrapped in `<DraggableTiles pageKey="trade-compliance">` with 12 tiles
      (summary, incoterms, tariffs, programs, section301, section232, coo, watchlists, broker,
      regs, alerts, links)
    - `/equipment` — wrapped in `<DraggableTiles pageKey="equipment">` with 5 tiles
      (kpis, charts-top, charts-bottom, tables, history)
  Reset button on each page reverts to default order (DELETE on the endpoint).
- **MiniCalendar on Command page** (`/app/frontend/src/components/MiniCalendar.jsx`) — compact
  240px-wide month grid with today highlighted in cyan, prev/next/today navigation. Placed inline
  with the QuotesTicker at the top-right of the dashboard.
- **Promo video v3** (`/promo.mp4`, 1.98 MB, 39.6s, 10 slides) — copy rewritten for *the team
  that uses this every day*: dispatchers, planners, broker liaisons, yard supervisors.
  Hero: "Built for the Team's Day". Outro: "USED BY THE TEAM · EVERY DAY".
  Script: `/app/scripts/build_promo_with_screens.py` (consumes fresh authenticated screenshots
  from `/app/scripts/capture_tms_screens_pw.py`).

## Implemented (v1.8 — Feb 2026)
- **Drag-and-drop Command Center tiles** restored on a *compact* grid (not the vertical stack).
  Each of 7 sections (sap-quick, news-ticker, video-row, sap-materials, kpis, main-grid,
  recent-shipments) has its own grip handle; CSS flex `order` drives the reorder; localStorage
  `tms-command-section-order` persists; "Reset Layout" button restores defaults.
- **Real Tennant machine photos** · 16 of 35 models now show actual Tennant CDN product
  photos (T7, T16, T7AMR, T16AMR, T12, T17, T20, T300, T500, S3, S5, M17, B5, B7, EX-CAN-7,
  Green Machine 414HS). The remaining 19 models still use the branded SVG fallback
  (always renders, accurate to model). T2's CDN ID returned a brand logo — left on SVG.
- **Promo video v2** · `/promo.mp4` rebuilt at 39.5s / 1.05 MB with **13 slides** covering
  the v1.7 lineup: BOL store/amend/email, Equipment/Yard analytics, drag-drop tile layout,
  35-machine catalog. Plus the existing slides on modes, SAP, trade compliance, HUDLINK,
  Vault. Plays directly from local file — no YouTube dependency.
- **Admin credentials** confirmed — `shearperfection369@gmail.com` is in `ADMIN_EMAILS`
  env var and idempotently promoted to `admin` on every Google sign-in. Documented at
  top of `/app/memory/test_credentials.md`.

## Implemented (v1.7 — Feb 2026)
- **Self-hosted promo.mp4** — `/app/scripts/build_local_promo.py` renders a 28s branded
  cinematic with ffmpeg + PIL (9 slides, fades). Lives at `/app/frontend/public/promo.mp4`,
  plays even on networks that block YouTube. Solves Tennant corporate-network blank-video issue.
- **Drag-and-drop Dashboard tiles** — `SortableTiles.jsx` powers the new Command Center.
  12 reorderable tiles, layout persists via `localStorage`, "Reset Layout" button.
- **YouTube Video tile** (replaces Customs Broker on Command Center) — `YouTubeVideoTile.jsx`
  accepts any YouTube URL/ID, embeds the player, persists last video. Fallback "Open in
  YouTube" button for locked-down networks.
- **Customs Broker moved to Trade Compliance** — enriched with Account #, POA, Bond Type,
  Phone, Email, Escalation contact + UPS_SCS portal deep-link.
- **Drag-and-drop column reordering** — both `Shipments` and `Workbook` tables now have
  grip handles on every column header. Drag to reorder, double-click width for resize,
  Reset button per-tab. Localstorage persistence.
- **BOL store/amend/email overhaul** (`Documents.jsx`):
  - Filter pills (All / BOL / Commercial Invoice / Packing Slip / Weight Cert / COO)
  - View · Download · Email · Amend actions per row
  - Amend dialog captures reason + diff trail (`amendments` array on the doc, version bumps)
  - Email dialog builds mailto with subject + body + PDF link, logs to `db.document_emails`
  - BOL-from-shipment generator: one-click create from any existing shipment record
  - Backend: `PATCH /documents/{id}`, `POST /documents/{id}/email`, `POST /shipments/{id}/generate-bol`
- **Equipment / Yard module** (NEW page `/equipment`):
  - Backend module `/app/backend/equipment_module.py` parses daily yard .xlsx (Doors,
    Loaded Inbound/Outbound, Empty Trailers, Empty Containers)
  - 5 endpoints: upload, list, get, delete (admin), analytics
  - Frontend: drag-drop upload, 6 KPIs (total on site, doors occupied/total, loaded in/out,
    empty trailers/containers, sealed %), live door map grid, carrier-mix pie, dwell-time
    bars + stale-trailer hotlist, multi-report historical trend, 4 trailer/container tables,
    full report history with delete
- **Machine catalog expansion** — 17 → 35 models across 12 categories. Added X-series ROVR
  robots (X4, X6, X16 SWEEP), T7/T12/T17/T20 ride-on scrubbers, T381/T500/T600 walk-behinds,
  S3/S5/S6/S7/S12/S16 sweepers, M20 LPG combo, B10 burnisher, E5/1610 carpet extractors.

## Pending / Backlog (P2)
- Refactor `/app/backend/server.py` (>6900 lines) into routers/modules under `/app/backend/routes/`
- Replace SendGrid mock with real provider when user is ready (`SENDGRID_API_KEY` env var)
- Production deployment health checks
- Deeper Power BI / SharePoint native embeds (currently surfaces + iframe)

## v2.0 Launch Wave (Feb 2026 — this session)
- **Wired ChessGame into Arcade** (`Arcade.jsx` tab `arcade-tab-chess` renders `<ChessGame />`)
- **Wired DriverRegistry into App+Sidebar** (`/driver-registry` route, sidebar nav `nav-driver-registry`)
- **Manual Supplier entry** — `POST /api/suppliers` (admin/dispatcher) + `DELETE /api/suppliers/{id}` (admin only on custom suppliers); UI: `Add Supplier` dialog in `SupplierSourcing.jsx`; custom suppliers persist in `db.suppliers_custom` and merge into the seed list with `is_custom: true` flag
- **AI-narrated Promo Video v2** (`/app/scripts/build_promo_with_screens.py`):
  - 18 flagship scenes (vs. 8 previously) including Power BI, SharePoint, Copilot, Specialty Carriers, Routing Guide, Suppliers, Driver Registry, Reports, Arcade
  - AI narration generated via OpenAI TTS (`tts-1-hd`, voice `onyx`) using Emergent universal key — see `/app/scripts/generate_promo_narration.py`
  - Synthesized ambient music bed via ffmpeg lavfi (A-minor sine pad with tremolo + slow fades) — no external download needed, firewall-safe
  - Final MP4: ~5 MB, 96.6s, h264 + AAC, lives at `/app/frontend/public/promo.mp4`
- **Promo page UX** — `PromoVideo.jsx` now shows a prominent pulsing "Tap for sound" button to unmute, version bumped to v2.0, subtitle lists every v2 module
- **User Manual v2.0** — `manual_content.py` cover bumped to v2.0; 16 new feature slides appended covering Copilot, Power BI, SharePoint, Specialty Carriers, Routing Guide, Truckload Sheet dropdowns, Supplier manual entry, Driver Registry, 45-metric Scorecard, Weather Radar+Alerts, Global Search Cmd-K, Solo Chess, 16 themes, Draggable Tiles, AI-narrated Promo
- **README.md** — overhauled with v2 capability table, narration build instructions, version log entry

## Known Mocks
- Email delivery — mailto: links + copy-to-clipboard (no Resend/SendGrid wired by user choice)
- SAP S/4HANA endpoints (`/api/sap/*`) — curated Tennant-relevant mock data
- Machine catalog images — public Unsplash CDN URLs (replaceable with Tennant product DAM)
- Customs broker, news feeds — mocked


## v2.1 — Multi-Tenant & Server Registry (May 2026 — current session)
- **Tennant Bleed-through Sweep on SAP** — every `/api/sap/*` endpoint now runs
  through `_brand_swap` + a new `_overlay_sap_records` helper. When a non-Tennant
  brand (e.g. Pfizer) is active:
  - `/api/sap/config` → `host: https://s4hana.<slug>.sap.com`, `user: <PREFIX>_TMS_SVC`
  - `/api/sap/sales-orders`, `/api/sap/purchase-orders` → Material, MaterialDescription,
    Plant, Supplier, SupplierName replaced with the brand's `sample_products` /
    `sample_suppliers` / `facilities`
  - `/api/sap/materials`, `/api/sap/sync-logs`, `/api/sap/open-deliveries` brand-aware
  - `/api/integrations` endpoints swap (e.g. `pfizer.sharepoint.com`, `powerbi.com/pfizer`)
- **KPI Brand Drift** — `/api/kpis` `network_metrics`, 14-day trend, and carrier
  scorecard composite scores now drift deterministically per brand seed (±12% on
  values, ±25% on trend). Tennant baseline is untouched. Verified Pfizer
  `on_time_pickup` ≈ 93.0% vs Tennant baseline 95.3%.
- **`_brand_tenant_strings`** extended with catch-all rules so any residual
  `tennantco`, `tennant`, or `Tennant` substring is swapped to the active brand's
  slug / short name.
- **Server Registry** (NEW admin feature) — `/app/frontend/src/components/ServerRegistry.jsx`
  embedded in Admin Control Deck. Auto-detects 4 system servers (TMS Backend API,
  MongoDB Cluster, Emergent LLM Gateway, Kubernetes Ingress) with live MongoDB ping
  + uptime. Admins can register custom servers (EDI gateways, reporting nodes,
  object stores, etc.) with `name / role / hostname / port / protocol / region /
  environment / owner_email / health_url / notes`.
  - Endpoints: `GET /api/admin/servers`, `POST /api/admin/servers`,
    `PATCH /api/admin/servers/{id}`, `DELETE /api/admin/servers/{id}`,
    `POST /api/admin/servers/{id}/ping` (HTTP if `health_url`, else TCP)
  - System servers (`system::*`) are read-only — edit/delete return 400
  - Storage: `db.servers_registry`
- **Promo Video v2.1** — `/app/scripts/capture_tms_screens_pw.py` + 
  `build_promo_with_screens.py` updated with 3 new scenes (SAP Sync, Admin Control
  Deck, Marketing/About). Final MP4: 5.72 MB · 111s · 23 slides · AI narration +
  ambient bed. Lives at `/app/frontend/public/promo.mp4`.

## Tests
- `/app/test_reports/iteration_17.json` — 21/21 pytest passed
- `/app/backend/tests/test_iter17.py`

## Backlog (P2)
- Refactor `server.py` (now ~8514 lines) into routers under `/app/backend/routes/`
- ServerRegistry: replace blocking `socket.create_connection` in ping handler with
  `asyncio.open_connection` to avoid event-loop stalls
- Add Pydantic `Literal[...]` validators on ServerRegistry `role` / `protocol` /
  `environment` to reject invalid enum values
- Move `_brand_tenant_strings` to a marker-template approach long term (substring
  swap is fragile if new content includes the word "Tennant")

## v2.7 — Freight Brokerage Operations Stack + New Default Brand (May 2026)
- **NEW `/brokerage` hub** — 5-tab top-level page (Dashboard · Load Boards ·
  Accounting · Forms Library · AI Assistant) under `/app/frontend/src/pages/Brokerage.jsx`.
- **Backend `routes/brokerage.py`** (665 lines) — mocked-where-it-matters,
  real-where-it-matters: synthetic load feed for 5 boards (DAT One, Truckstop,
  Convoy, Uber Freight, 123Loadboard) with per-board RPM + margin profiles;
  DB-backed margin scorecard (forecast vs settled per board); accounting
  (`brokerage_invoices`, `brokerage_expenses`, P&L, A/R aging, 1099 totals);
  hybrid QuickBooks (mocked OAuth + sync flush flag); 15 fillable compliance
  PDFs via ReportLab (MC Authority, BOC-3, BMC-84 surety, UCR, Rate Conf,
  Load Tender, Carrier Packet, MSA, Customer Invoice, Aging, 1099-NEC,
  Mileage Log, Factoring Assignment, Quick-Pay); AI assistant (Claude
  Sonnet 4.5) wired with live P&L + margin context in every prompt.
- **AI load matching** — `/api/brokerage/loads/match` ranks loads across
  all 5 boards by a margin-vs-market scoring algorithm; tags
  `high-margin`, `above-market`, `fresh-post`, `stale`.
- **New default brand** — created and activated **Apex Freight Solutions LLC**
  via the manual brand template (Dallas TX HQ, 3 facilities, cyan brand
  palette, freight-broker service catalog). Replaces Pfizer/Tennant as the
  default. The brand-reactive engine (v2.3) instantly re-skinned every page.

## Tests
- Verified `/api/brokerage/dashboard`, `/boards`, `/loads/match`, `/forms`,
  `/quickbooks/status` all return correct shapes
- 90 synthetic loads (18 per board × 5 boards) score deterministically with
  a fresh ranking each hour
- Apex Freight visible in topbar; zero Tennant city bleed on /brokerage
- **Continued refactor** — extracted branding endpoints to
  `/app/backend/routes/branding.py` (`build_branding_router`) and SAP
  endpoints to `/app/backend/routes/sap.py` (`build_sap_router`). Both use
  the same factory pattern. `server.py` shrank from 8305 → 7782 lines
  (~520 lines pulled out). `DEFAULT_BRAND` now lives in `routes/branding.py`
  and is re-exported for backward compatibility with the admin dashboard.
- **ServerRegistry Pydantic constraints** — `port` is `ge=1 le=65535`;
  `name/role/hostname` have `min_length=1`; every string field has an
  upper-bound `max_length`. Out-of-range values now return clean 422s
  before they hit the DB.
- **NWS thundering-herd lock** — added `_NWS_LOCKS: Dict[tuple,
  asyncio.Lock]` keyed by rounded coord. The cache lookup is now
  double-checked inside the lock so 50 concurrent users monitoring the
  same city → exactly **1** upstream NWS call. Verified: 5 simultaneous
  `/api/weather/alerts` requests completed in 1.16 s total, all returned
  identical alert_id sets.
- **Marker-template seed fix** — `_seed_alert_locations_from_brand` now
  strips the `", ST"` state suffix before calling Open-Meteo's geocoder
  (which doesn't accept the comma format), so Pfizer's facilities seed
  correctly to New York, Kalamazoo, Pearl River, McPherson instead of
  silently falling back to Tennant's defaults. Tennant brand is no
  longer special-cased in the function — every brand goes through the
  same code path.

## v2.6 Tests (self-validated 11/11)
- Branding: GET /api/branding, /api/branding/all, /api/branding/template
  (has promo_video_ids), DELETE rejects 'tennant' with 400 — ALL PASS
- SAP: /sap/config returns `s4hana.pfizer.sap.com` + `PFIZER_TMS_SVC`;
  sales/purchase orders use `PFIZ-*` material prefix; sync + sync-logs
  work — ALL PASS
- ServerRegistry: port=99999 → 422; port=-1 → 422; name='' → 422; valid
  POST → 200 + DELETE → 200 — ALL PASS
- Marker-template: clearing locations + GET /api/weather/alerts seeds
  with Pfizer's actual cities (no Tennant city bleed) — PASS
- Thundering-herd: 5 concurrent requests → 1 upstream NWS call, same
  alert_id set returned to all 5, wall-clock 1.16 s — PASS
- **NWS shared cache** — added a 60-second `cachetools.TTLCache(maxsize=512)`
  keyed by rounded (lat, lng) so 100 polling users monitoring the same city
  generate **one** upstream NWS call per minute. Bounded LRU prevents the
  cache from growing forever in long-running pods.
- **Structured NWS logging** — non-200 responses, network errors and geocoder
  failures now log at WARNING with structured fields (lat/lng/status/error
  type). NWS outages are no longer silent.
- **Async ServerRegistry ping** — replaced blocking
  `socket.create_connection` with `asyncio.open_connection` wrapped in
  `asyncio.wait_for`. The event loop is no longer stalled on slow TCP
  connects.
- **Conservative refactor** — extracted weather endpoints to
  `/app/backend/routes/weather.py` (`build_weather_router`) and
  ServerRegistry endpoints to `/app/backend/routes/server_registry.py`
  (`build_server_registry_router`). Both use a **factory-function pattern**
  that takes the shared DB handle + helpers as parameters so there are no
  circular imports. `server.py` shrank from ~8587 → ~8305 lines and
  `socket` is no longer imported in the main file. Pattern is ready for
  the next domain group to be extracted.

## v2.5 Tests
- `/app/test_reports/iteration_20.json` — 17/17 pytest passed
  (`/app/backend/tests/test_iter20_refactor.py`). Cache correctness verified
  with two back-to-back calls; non-blocking ping confirmed by interleaving
  ping with a `/api/branding` call that stayed sub-100 ms during a 3-second
  TCP timeout.

## v2.4 — Real-Time NWS Weather Alerts + Manual Location Control (May 2026)
- **Live NWS feed** — `/api/weather/alerts` now hits the public
  `api.weather.gov/alerts/active?point=<lat>,<lng>` endpoint (User-Agent
  required, no auth) for each user-monitored US location and returns real
  watches/warnings/advisories. Falls back to brand mock alerts when no live
  alerts are active so the UI never goes empty.
- **Manual location control** — new `GET/POST /api/weather/alert-locations`
  endpoints persist a per-user list (capped at 12) in
  `db.weather_alert_locations`. First read auto-seeds from the active brand's
  facilities (geocoded via Open-Meteo). The Command Center banner now has a
  **"Configure Locations"** gear that opens a dialog with debounced
  Open-Meteo geocoder autocomplete + add/remove rows + Save & Refresh.
- **Live indicator** — banner header now shows `LIVE WEATHER FEED · updated
  HH:MM:SS · NWS live` so dispatchers know the data is real-time. Each alert
  card gets a green **LIVE** badge when it came from NWS (vs the fallback
  mock).
- **Brand-reactive** — when the admin switches themes, the banner re-fires
  via `useBrandRefresh()` so the alert locations re-seed from the new
  brand's facilities automatically.

## Tests
- `/app/test_reports/iteration_19.json` — 16/16 pytest passed (real NWS
  call verified for Denver during dev).

## v2.3 — Brand-Reactive Refresh + BOL Preview + Arcade Polish (May 2026)
- **Package A · Brand-Reactive Data Refresh** — `BrandingProvider` now fires a
  `brand-changed` `window` event whenever the active brand actually changes,
  and a new `useBrandRefresh(callback)` hook plugs every brand-aware page into
  the loop. Re-wired pages: Dashboard, Shipments, Tracking, Reports, SAP Sync,
  Specialty Carriers, Machines, Driver Registry (drivers + trailers),
  Documents, Carrier Rates, PowerBI, SharePoint, Integrations, Carrier
  Onboarding, Supplier Sourcing. Every endpoint listed in iteration_18.json
  is brand-aware on the server side AND every consumer page re-fetches on
  theme switch — no full reload required.
- **Package B1 · Facility Conditions Dropdown** — Command Center weather card
  gained an in-card **"+ Add Location"** flow (open-meteo + geocoding API).
  Custom cities persist in `localStorage`. Auto-refreshes from the brand's
  facilities list on every theme switch.
- **Package B2 · Brand-aware Promo Video** — Admin pastes up to 6 YouTube
  video IDs into the brand template (new `promo_video_ids` field on
  `/api/branding/manual` + `/api/branding/template`). `PromoVideo.jsx` reads
  `brand.promo_video_ids` from context and renders a per-brand playlist;
  reset to slot 0 on theme switch; falls back to the Tennant trailer if
  the active brand has no videos configured.
- **Package B3 · Video Tile UX Polish** — Command Center `CompactVideoTile`
  auto-fetches YouTube titles via `oembed` (no more `window.prompt`). The
  standalone `YouTubeVideoTile` was overhauled to a thumbnail-grid playlist
  with hover-to-remove × controls.
- **Package C · BOL Preview + Save** — On `BookLoad.jsx` submit:
  `POST /api/shipments` → `POST /api/shipments/{id}/generate-bol` → opens a
  full BOL preview modal. **"Save BOL (PDF)"** downloads the ReportLab-rendered
  PDF; **"Open in Documents"** navigates to the Document Vault. Backend now
  uses the active brand's `company_name` as the BOL shipper / commodity
  defaults so a Pfizer-active TMS no longer prints "Tennant Company" on its
  BOLs.
- **Package D · Arcade Visual Polish** — Hero banner with gradient title,
  cyan grid backdrop, pulsing orb backgrounds, and a 6-tile personal-stats
  KPI strip (My Trophies / Rank / Tier / Active Games / Live Tournaments /
  Total Players). Leaderboard #1 row glows gold.

## Tests
- `/app/test_reports/iteration_18.json` — 16/16 pytest passed (no regressions)
- Verified: `/api/branding/template` has `promo_video_ids`, `/api/branding/manual`
  accepts & persists them, end-to-end book-then-BOL flow returns a real PDF,
  brand-reactive sweep clean of `Tennant` substring across drivers, trailers,
  specialty carriers, traffic, weather alerts, shipments (cities), KPIs.
- **"Build Your Own" Brand Template** — new dialog in `ManualBrandDialog.jsx`,
  embedded in `CompanyTheme.jsx` next to Generate & Activate. Lets the admin
  manually fill any/all brand fields (name, short, logo letter, tagline,
  industry, HQ, 3 colors, products, suppliers, lanes, facilities) without
  needing the LLM. Two save modes: **Save (Don't Activate)** or **Save &
  Activate** to re-skin the app instantly.
- Backend endpoints: `POST /api/branding/manual`, `GET /api/branding/template`
- **Location Sweep** — `_brand_tenant_strings()` extended with a facility-city
  mapping that auto-swaps every Tennant location token (Golden Valley/Holland/
  Louisville → active brand's facilities) across **all** wrapped endpoints:
  news, weather/alerts, traffic, SharePoint, Power BI, specialty carriers,
  drivers, trailers, integrations, SAP, KPIs.
- `_overlay_shipment()` now also swaps origin/destination cities so the Live
  Tracking page, Shipments page, and shipment tracker all use the active
  brand's facility cities (verified: Pfizer shows New York, Pearl River,
  Kalamazoo, McPherson — no Tennant cities anywhere).


## 2026-02-14 · Freight Brokerage Business Plan (Apex Freight Solutions LLC)
- New comprehensive operating business plan at `/app/BROKERAGE_BUSINESS_PLAN.md`
  (4,932 words · ~28.8 KB markdown). Sections: Exec Summary · Founder (Oliver
  Cummins, bio sourced from launch promo / About page) · Company Overview ·
  Mission/Vision/Values · Industry & MN/Twin Cities Market Analysis · Service
  Offering · Competitive Landscape · Marketing & Sales Strategy · Operations
  Plan · Compliance Calendar · 3-Year P&L (bootstrap solo-agent baseline:
  $432K → $1.0M → $1.9M revenue; $82K → $215K → $441K gross margin) · Cash
  Flow & Break-even · Risk Analysis · KPIs · Step-by-Step Entry Plan
  (Phase 0 pre-launch → Phase 5 Year-3 institutionalize) · Long-Term Vision
  & Exit Options · Glossary & Regulatory References.
- New backend endpoint **`GET /api/brokerage/business-plan`** in
  `routes/brokerage.py` returns `{ filename, size_bytes, updated_at, markdown }`.
- New **Business Plan** tab inside `Brokerage.jsx` (`brokerage-tab-plan`)
  renders the markdown with `react-markdown` + `remark-gfm`. Includes
  Print and Download .md actions.
- New `.brokerage-plan-prose` styling in `index.css` with cyan-accented H2
  underlines, GFM tables, blockquotes, light-theme overrides (solar/paper),
  and a print stylesheet that isolates the prose for clean PDF/paper export.
- Added deps: `react-markdown`, `remark-gfm` (via `yarn add`).

## 2026-02-14 (later) · Rename to Orisei + Connections Vault
- Active brand renamed: `apex-freight` → `orisei-freight` · "Orisei Freight Solutions LLC"
  · HQ Minneapolis, MN · facilities Minneapolis / Saint Paul / Duluth.
  Business plan markdown rewritten (40 occurrences). Brokerage tab header updated.
- New backend module **`/app/backend/routes/connections.py`** — admin-managed
  credential vault for third-party integrations. Fernet-encrypted at rest
  (auto-generates `CONNECTIONS_ENCRYPTION_KEY` into backend/.env on first
  boot). Secrets never returned in plaintext — only masked previews. Endpoints:
  - `GET /api/connections/providers` — merged catalog (built-in + custom)
  - `POST /api/connections/providers/custom` — add a NEW integration at runtime
  - `DELETE /api/connections/providers/custom/{id}` — remove custom (built-ins protected)
  - `GET /api/connections` — full rollup with unconfigured stubs
  - `GET /api/connections/{provider}` — single status
  - `PUT /api/connections/{provider}` — upsert credentials (empty-secret preserves existing cipher)
  - `DELETE /api/connections/{provider}` — disconnect
  - `POST /api/connections/{provider}/test` — sanity-decrypt placeholder
  - Audit log collection `connection_audit_log` for every PUT/DELETE.
- 10 built-in providers shipped: QuickBooks, DAT One, Truckstop, Uber Freight,
  123Loadboard, Stripe, Resend, Twilio SMS, Macropoint/Project44, RMIS.
- New frontend page **`/app/frontend/src/pages/Connections.jsx`** at `/connections`
  with admin-only sidebar entry `Connections · Keys`. Configure dialog per
  provider, secret fields masked on reopen (`••• existing value kept (xxx•••yyy)`),
  Test / Save / Disconnect / Enable-Disable switch.
- New "**+ Add Integration**" flow lets an admin define a brand-new provider
  at runtime — name, ID, category, logo letters, docs URL, and an arbitrary
  list of credential fields (label, snake_case key, secret flag, required flag).
  Custom cards get a purple `CUSTOM` badge and an inline remove button; built-in
  providers are protected from deletion.
- Encryption deps: `cryptography==48.0.0` (already in requirements.txt) + Fernet.
- Tests: `/app/backend/tests/test_iter21_connections.py` — **14/14 passing**
  (catalog, RBAC, masking, encrypted-at-rest in Mongo, empty-secret-preserves,

## 2026-02-14 (later 2) · Cost Analysis Tab
- New `/app/COST_ANALYSIS.md` — 3,800-word operating cost analysis covering
  three load tiers (Solo / Small Brokerage / 50-tenant white-label).
- Backend endpoint `GET /api/brokerage/cost-analysis` (mirrors the
  business-plan endpoint via shared `_read_doc` helper).
- New **Cost Analysis** tab in Brokerage Command Deck
  (`data-testid="brokerage-tab-costs"`).
- Refactored the inline business-plan renderer into a reusable
  `MarkdownDocTab` component so both tabs share one implementation.

  delete-roundtrip, business-plan rename, brokerage regression).

## 2026-02-14 (later 3) · Investor Outreach + Home-Office Plan + Deploy Banner
- Authored **`/app/HOME_OFFICE_SETUP.md`** — 20.5 KB / 14-day self-hosting build guide
  (3 hardware tiers, day-by-day plan, security hardening, vs-cloud cost comparison,
  failure-mode runbook). Backend endpoint `GET /api/brokerage/home-office-setup`
  + new **Self-Host** tab in Brokerage Command Deck (reuses `MarkdownDocTab`).
- **Investor Outreach feature**:
  - `POST /api/brokerage/investor-pitch/preview` returns email HTML + PDF size
  - `POST /api/brokerage/investor-pitch` sends via Resend (creds pulled from
    Connections vault); falls back to dry-run mode when Resend isn't configured.
    Records every send into a new `investor_outreach` collection (id, recipient,
    status, sent_by, pdf attached, message_id from Resend).
  - `GET /api/brokerage/investor-outreach` returns recent outreach history.
  - PDF generated on-the-fly from `BROKERAGE_BUSINESS_PLAN.md` via reportlab
    (~21 KB, professionally styled with section headings + bullets, tables
    replaced by hyperlinks to the online plan to keep the PDF small).
  - HTML email template uses inline CSS / table layout (email-client safe).
    Includes founder bio paragraph, business plan exec summary, "Connect on
    LinkedIn" CTA button, signature, and unsubscribe-friendly footer.
  - Frontend: **"Email to Investor"** button in the Business Plan tab header
    opens a dialog with iframe HTML preview, recent-outreach history list,
    and Send / Dry Run / Preview buttons. LinkedIn URL + founder name + reply-to
    persist to localStorage between sends.
- **`DeployHealthBanner` component** auto-detects "frontend bundle is calling
  preview backend from a production domain" misconfig. Renders a red
  sticky banner (admin-only, dismissible per session) with the exact fix
  instructions ("Save to GitHub → Deploy") and the env-var Emergent Support
  would need to set. Pure client-side — no backend round-trip.
- New deps: `resend==2.30.1`, `Markdown==3.10.2`.

- Custom-provider flow verified end-to-end via curl (add → list as 11 → configure
  with masked preview → built-in protection 400 → delete → back to 10).



## 2026-02-15 · Beautiful Orisei BOL · NEW Proof of Delivery (POD) · QuickBooks OAuth · Landing route public
- **`routes/orisei_docs.py`** (NEW, ~360 lines) — brand-aware ReportLab PDF generators
  for the Bill of Lading and Proof of Delivery. Embeds downsampled Orisei logo +
  wordmark (`_orisei_logo_pdf.png` / `_orisei_wordmark_pdf.png`, ~120KB each so
  final PDFs stay ~300KB email-safe), Moorish-inspired 8-point gold stars in
  all 4 corners, deep-azure (#0E3A6B) + gold-leaf (#C9A24A) palette, parties /
  shipment / freight / charges / signature blocks. POD adds a prominent
  "◆ DELIVERED ◆" azure banner with timestamp + Khatim al-Sulayman accents.
- **NEW brokerage endpoints** in `routes/brokerage.py`:
  - `GET  /api/brokerage/bookings` — list all bookings ready for BOL/POD/mailing
  - `PUT  /api/brokerage/bookings/{id}/customer` — attach customer name/email/phone/addresses
  - `GET  /api/brokerage/bookings/{id}/bol.pdf` — beautiful Orisei BOL PDF (stamps `bol_no` on the doc)
  - `GET  /api/brokerage/bookings/{id}/pod.pdf` — Orisei POD PDF (uses any saved delivery data)
  - `POST /api/brokerage/bookings/{id}/pod/email` — emails POD via Resend (creds from Connections vault),
    persists to `db.pod_outreach`, updates booking.status='delivered' + delivery fields. Supports
    `dry_run=true` to render HTML+PDF without sending. Returns 400 with helpful detail when Resend
    is not configured.
  - `GET  /api/brokerage/bookings/{id}/pod-history` — recent POD send log per booking
- **QuickBooks OAuth wiring** — replaced the mocked "Connect to QuickBooks" with a real flow:
  - `GET /api/brokerage/quickbooks/oauth/start` builds the Intuit authorize URL from the
    Connections vault (`client_id`, `redirect_uri`, `environment`), stores a state in
    `db.brokerage_qb_oauth_state`, returns `{authorize_url, state, environment}`.
  - `GET /api/brokerage/quickbooks/oauth/callback` exchanges the code via `httpx` against
    `oauth.platform.intuit.com/oauth2/v1/tokens/bearer`, stores access/refresh tokens +
    realm_id on `brokerage_qb_config`.
  - The legacy `/quickbooks/connect` (mock) is still available for local dev under the
    "Or use mock connection (dev)" link.
- **Frontend** (`pages/Brokerage.jsx`):
  - New **Booked Loads · BOL & POD · Email Customers** panel inside the Load Boards tab.
    Shows every booking with status pill (booked/settled/delivered), customer chip, and
    four actions per row: CUSTOMER (info dialog), BOL (download PDF), POD (download PDF),
    EMAIL POD (mailing dialog with delivery-confirmation fields + dry-run).
  - `CustomerInfoDialog` captures customer/consignee + shipper info that gets stamped on BOL/POD.
  - `PodEmailDialog` captures delivered_at / received_by / driver_name / pieces / weight /
    seal_intact / condition, plus full email controls (To, CC, Subject, Message). Persists
    delivery details to the booking on send.
  - QbControls now offers **"Connect via Intuit OAuth"** as the primary CTA (opens
    authorize_url in a new tab) and keeps a small "Or use mock connection (dev)" link.
- **`components/TennantLogo.jsx`** — when `brand_id === "orisei-freight"` renders the actual
  Orisei logo PNG inside a gold-ringed azure disc. Other brands keep the colored pill behavior.
- **`App.js`** — `/home` (Landing.jsx) moved out of the ProtectedRoute block so the public
  Moorish-themed landing page is reachable without sign-in.
- **`pages/Landing.jsx`** — eslint pragma broadened so it compiles (the `jsx-a11y/anchor-is-valid`
  rule wasn't loaded in this preset).
- New DB collections: `brokerage_qb_oauth_state`, `pod_outreach`.

### Tests
- `/app/test_reports/iteration_22.json` — 21/21 pytest passed, frontend Playwright smoke OK.
  Covered every new endpoint + regression of dashboard/boards/book/settle/margins/factoring/
  investor-pitch/business-plan/cost-analysis. Verified PDFs render with valid `%PDF` magic,
  sub-1MB sizes, `Content-Type: application/pdf`, BOL stamps `bol_no` on the booking, POD
  email dry-run persists outreach + updates booking status, QB OAuth start without creds
  returns the help message, with creds returns a valid appcenter.intuit.com authorize URL.


## 2026-02-15 (later) · Queen Calafia rebrand · POD Photos · Auto-Mail · Live Load Board
- **Logo rebranded** — Islamic 8-point Khatim al-Sulayman replaced with a Queen Calafia
  + griffin heraldic medallion (regenerated via nano-banana, gemini-3.1-flash-image-preview).
  Files: `/app/frontend/public/brand/orisei_logo.png`, `_pdf.png` (PDF-optimized),
  `orisei_wordmark.png`. `routes/orisei_docs.py` swaps the 8-point star corners for
  heraldic diamond-flourish corners and renames the helper to `_draw_heraldic_border`.
  Landing page caption updated to "◇ Queen Calafia · Mounted on her Griffin ◇".
- **POD Photos** (`routes/brokerage.py` lines 1148–1216) — max-3 dock photos per booking,
  mobile camera-friendly (`<input capture="environment">`), PIL-downsampled server-side
  to ≤1024px @ 82-quality JPEG. Embedded as a 2nd page in `pod.pdf` ("Delivery Photos").
  Endpoints: `POST /api/brokerage/bookings/{id}/pod/photos` (multipart file+caption),
  `GET /pod/photos`, `GET /pod/photos/{photo_id}` (image/jpeg), `DELETE /pod/photos/{photo_id}`.
- **Auto-Mail Automation** — new `brokerage_settings` singleton collection with
  `auto_email_bol_on_book` and `auto_email_pod_on_delivery` toggles + optional
  `bol_message_template` / `pod_message_template`. Endpoints `GET/PUT /api/brokerage/settings`.
  Hooks:
   - `PUT /bookings/{id}/customer` — on a fresh `customer_email` transition, renders the
     BOL and emails via Resend (returns `_auto_bol.auto_email_error` with helpful Resend
     hint when Resend isn't configured).
   - `POST /bookings/{id}/mark-delivered` (NEW) — one-tap "delivered" for dispatchers;
     stores delivery + flips status; if toggle enabled + Resend configured, mails POD
     with embedded photos to the customer.
- **Live Load Board adapters** (`routes/loadboard_adapters.py`) — DAT One, Truckstop,
  Convoy/Flexport Trucking adapters using `httpx`. `board_loads` tries `try_fetch_live`
  with credentials from the Connections vault and falls back to synthetic feed when keys
  are missing or the upstream API fails. Response now exposes `source: 'live'|'synthetic'`.
- **Frontend** (`pages/Brokerage.jsx`) —
   - `BrokerageAutoMailCard` toggles + templates on Dashboard tab.
   - `PodPhotoUploader` inside the PodEmailDialog (live thumbnails + remove buttons).
   - `Mark Delivered` button on each booking row that triggers `/mark-delivered`.
   - `board-source-badge` shows LIVE API FEED / SYNTHETIC FALLBACK in Boards tab.

### Tests
- `/app/test_reports/iteration_23.json` — 24/24 backend tests pass; Playwright smoke confirms
  Calafia emblem + caption render on /home, BrokerageAutoMailCard toggles + auto-mail
  templates render in Dashboard, board-source-badge appears, PodPhotoUploader sits inside
  the email dialog, mark-delivered button + endpoint round-trip works. Test file added at
  `/app/backend/tests/test_iter23_calafia_photos_automail.py` (preview-URL-based).


## 2026-02-15 (later 2) · Documents-page BOL Calafia rebrand · Provider Outreach module
- **`/api/documents/{id}/pdf` BOL fix** — server.py `download_document_pdf` now routes
  BOL doc-types through `routes.orisei_docs.build_bol_pdf` so the Documents page renders
  the Calafia + griffin Orisei BOL (no more Tennant header). For non-BOL types
  (COMMERCIAL_INVOICE, PACKING_SLIP, WEIGHT_CERT, COO), `_header_block` and `_build_pdf`
  now accept `brand` and use `short_name` + `primary_color` so the header text and rule
  color follow the active brand.
- **NEW `/api/provider-outreach/*`** (`routes/provider_outreach.py`) — automated
  launch-day API/key request emails. PROVIDER_CATALOG ships 14 providers across
  Load Boards (DAT, Truckstop, Convoy/Flexport, Uber Freight, 123Loadboard),
  Factoring (Triumph, Apex, OTR), Email Delivery (Resend), Accounting (QuickBooks),
  Carrier Vetting (RMIS, Carrier411), Regulatory (FMCSA), Insurance (Tivly).
  Endpoints:
   - `GET /catalog` — providers + has_credentials cross-ref against Connections vault
   - `POST /send` — bulk-mail via Resend; supports `dry_run`, `to_email_overrides`,
     `note_appendix`, `cc_email`. Persists every attempt to `db.provider_outreach`.
   - `GET /history` — past outreach rows sorted desc
   - `PUT /{id}/status` — manually mark replied / closed when the provider responds
- **Frontend `/provider-outreach`** (`pages/ProviderOutreach.jsx`) — admin-only page:
  - 4 stat cards (catalog total, contacted, with creds, launch-ready)
  - Filter pills (All · Missing keys · Not contacted · per-category)
  - Quick selection (all visible · missing keys · clear)
  - Provider table with checkbox, signup URL, what-we-need, editable per-row email,
    KEYS PRESENT / NEED KEYS badges, and last sent date
  - Compose card with personal note appendix + Dry-Run/Send buttons
  - Outreach history with mark-replied / mark-closed status pills
  - Dry-run preview modal renders the actual rendered HTML in an iframe
- **Sidebar** — added "Provider Outreach" admin-only nav link.

### Tests
- `/app/test_reports/iteration_24.json` — 19/19 backend tests pass; Playwright smoke
  confirms 14 providers render, filter pills + quick-select + compose + history all
  wired, BOL Documents PDF now Orisei-branded. `/app/backend/tests/test_iter24_outreach_bol.py`
  added with full coverage for catalog shape, send dry-run, send-without-resend 400,
  email override honoring, admin RBAC, history sort, status-update happy/sad paths,
  and BOL/non-BOL Documents PDF regressions.


## 2026-02-15 (later 3) · P0 Carrier Onboarding Packet Fix
- **Bug**: `POST /api/carrier-onboarding/{onboarding_id}/send-packet` returned 500
  with the toast "Failed to compose packet". Root cause: the endpoint referenced
  `doc['name']` but `carrier_onboarding` records store the carrier name under
  `legal_name` → `KeyError` → 500.
- **Fix** (`server.py` `send_onboarding_packet`):
  - Resolve carrier display name as `legal_name` → `name` → `dba` → "Carrier".
  - Brand-aware packet body: reads active brand via `_active_brand_doc()` and
    swaps in `company_name`, `short_name`, derived `carriers@{slug}.com`
    contact, and `phone` so packets now read "Orisei Freight Solutions LLC"
    (or any active brand) instead of being hard-coded to Tennant.
  - Cleaner empty-field rendering ("—" instead of "None") for MC/DOT/SCAC/Mode.
  - `mailto:` link now URL-encodes subject + body via `urllib.parse.quote`.
- **Frontend** (`pages/CarrierOnboarding.jsx`): packet modal title now reads
  "{brand_short} Onboarding Packet" via `useBranding()`.
- **Verified**: `curl POST /api/carrier-onboarding/OB-A90459A0/send-packet` → 200
  with full Orisei-branded body.


## 2026-02-15 (later 4) · Warm, full-color carrier invite emails (logo embedded)
- **`POST /api/carrier-invites`** rewritten to be fully brand-aware:
  - Builds a warm, narrative invite (who we are · what carriers gain · trust block ·
    operator-signed signature) that swaps in `company_name`, `short_name`,
    `tagline`, `primary_color`, `accent_color`, and `owner_name` from the active
    brand. No more "Hello ," / "Tennant" leakage.
  - Returns three new response fields: `subject`, `email_html`
    (rich, table-layout HTML — Gmail / Outlook / Apple Mail safe with the
    Calafia + griffin logo embedded via `<img src=".../brand/orisei_logo.png">`),
    and `logo_url`.
  - Smart `_public_app_url(request)` helper resolves absolute URLs by trying
    PUBLIC_APP_URL → FRONTEND_PUBLIC_URL → REACT_APP_BACKEND_URL → forwarded
    headers, so logo images always render on https.
- **NEW `POST /api/carrier-invites/{invite_id}/send-email`** — directly emails
  the rich HTML invite via Resend (credentials pulled from the Connections
  vault). Soft-fails with HTTP 400 + actionable copy when Resend isn't
  configured. Persists every attempt to `db.carrier_invite_emails`, stamps
  `email_sent_at` on the invite, and returns the Resend message ID.
- **Frontend (`CarrierInvites.jsx`)** — full rewrite of the invite modal:
  - Live HTML preview rendered inside a sandboxed `<iframe>` so admins see
    *exactly* what the carrier will receive (logo, header, CTA, signature).
  - Tab toggle between **Full Color** and **Plain Text** previews.
  - **"Send via Email · {brand}"** primary CTA wired to the Resend endpoint.
  - Table gains an **Emailed** column with a checkmark + date, plus an inline
    **Email / Resend** row action so admins can fire from the list view.
  - All accents derived from the active brand (`primary_color` /
    `accent_color`) via `useBranding()`.


## 2026-02-15 (later 5) · Brand-aware printable documents · brand-new Sora 2 promo
- **Bug**: After switching the active company theme, every printed document
  (BOL / POD / compliance form / business plan / cost analysis / home-office)
  still read "Orisei" because `routes/orisei_docs.py` had the company name,
  palette, logo, monogram, footer, and doc-id prefix hardcoded.
- **Fix**: refactored `routes/orisei_docs.py` to a fully brand-aware engine:
  - New `_theme(brand)` helper resolves every visual + textual attribute from
    `company_brand`: company name, short name, azure (=`primary_color`),
    gold (=`accent_color`), light gold (derived), paper tint (derived),
    monogram letter, doc-id prefix (first 3 alpha chars of `short_name`),
    logo path (Orisei → Calafia griffin asset · other brands → `logo_pdf_path`
    when present, else a filled monogram disc), wordmark path, and a footer
    "{company}  ·  {hq}  ·  {ops_email}" line.
  - Every helper (`_draw_heraldic_border`, `_styles`, `_header`,
    `_parties_block`, `_shipment_meta`, `_section_header`, `_signature_block`,
    `_build_doc`) now takes a `theme` and renders all colors/text from it.
  - Public builders (`build_bol_pdf`, `build_pod_pdf`, `build_form_pdf`,
    `build_branded_markdown_pdf`) each accept a new `brand: Optional[Dict]`
    kwarg; defaults stay Orisei-themed when omitted so legacy callers don't
    break.
  - Every caller in `routes/brokerage.py` (`generate_booking_bol`,
    `generate_booking_pod`, `email_booking_pod`, `_send_bol_email`,
    `business_plan_pdf`, `cost_analysis_pdf`, `home_office_setup_pdf`,
    `fill_form` → `_render_form_pdf`, both investor-pitch attachment
    paths) and the `download_document_pdf` BOL renderer in `server.py`
    now resolve `brand = await _active_brand(db)` and pass it through.
  - Doc-id prefixes also follow the active brand: `ORI-BOL-...` for Orisei,
    `FED-BOL-...` for FedEx, `TEN-BOL-...` for Tennant, etc.
  - Orisei keeps its founder contact (`oliver@oriseifreight.com`) in the
    footer; other brands derive `ops@{slug}.com` unless they store a
    custom `contact_emails.ops` or `contact_email`.
- **Verified**: activating FedEx renders BOL with "Federal Express Corporation"
  header / footer / "FED-BOL-…" doc id / `F` monogram / FedEx color palette.
  Restoring Orisei renders with the Calafia griffin logo, navy/gold palette,
  and `oliver@oriseifreight.com` footer.
- **Promo**: regenerated a brand-new 12-second Sora 2 cinematic spot
  (`/app/frontend/public/promo.mp4`, 5.7 MB, 1280×720). The `/promo` page
  auto-detects the file and swaps it in over the YouTube fallback. Prompt
  used heraldic gold/navy palette, Calafia seal close-up, Minneapolis
  golden-hour establishing shot, dispatch desk macro, dock POD photo cut,
  and a final wordmark card.


## 2026-02-15 (later 6) · Investor Boardroom + VC Data-Room ZIP
- **NEW**: `routes/investor.py` (~800 LOC) — fully brand-aware investor toolkit
  with 6 endpoints (all `require_role("admin")`):
  - `GET  /api/investor/boardroom` — TAM/SAM/SOM, monthly_model (36 rows),
    annual_summary (3 yrs), unit_economics, industry_benchmarks (sourced:
    TIA 2024, SBA 2023, FreightWaves 2024, Armstrong & Assoc 2024),
    default_probability scorecard.
  - `POST /api/investor/probability` — Interactive scoring on ProbabilityInputs
    {starting_capital_usd, operator_experience_years,
    monthly_marketing_budget_usd, carrier_pool_size, has_tms,
    has_factoring_partner, has_authority, target_lanes_count} → 0..99 % score,
    band (STRONG / FAVORABLE / WORKABLE / FRAGILE), 9 weighted drivers with
    +/- pts and footnotes. Default Orisei-favorable inputs = 99 STRONG;
    fragile inputs (10K capital, 1 yr exp, no TMS, no authority) = 52 FRAGILE.
  - `GET  /api/investor/deck.pdf` — 15-section brand-aware VC pitch deck.
  - `GET  /api/investor/one-pager.pdf` — at-a-glance teaser PDF.
  - `GET  /api/investor/financial-model.xlsx` — 4 sheets via openpyxl:
    Summary (Year 1–3), Monthly Model (36 rows), Unit Economics, Market
    Sizing — brand-colored headers.
  - `GET  /api/investor/data-room.zip` — bundles all 6 deliverables
    (Pitch Deck PDF · One-Pager PDF · Industry Probability Report PDF ·
    Business Plan PDF · Financial Model XLSX · Cap Table CSV) + README.txt,
    every filename prefixed with the active brand's `short_name`.
- **NEW**: `frontend/src/pages/InvestorBoardroom.jsx` — interactive VC
  analytics page mounted at `/investor-boardroom` (admin sidebar link via
  `Briefcase` icon):
  - VC Data Room banner with one-click ZIP download + 4 individual document
    download pills (Deck, One-Pager, Financial Model, Business Plan).
  - 4 headline metric tiles: TAM $210B · SAM $95B · Year-3 SOM $8.5M ·
    Year-3 EBITDA.
  - **Interactive success-probability scorecard**: 5 sliders + 3 toggles
    debounce-fire `POST /api/investor/probability` on every change, live
    band/colour swap (STRONG green · FAVORABLE cyan · WORKABLE amber ·
    FRAGILE red), score drivers table.
  - 36-month financial waterfall chart (Recharts AreaChart, brand-themed
    gradient fills for Revenue + EBITDA + Gross Profit).
  - TAM/SAM/SOM progress bars + Unit Economics 9-tile grid + Industry
    Reality Check stat blocks (Y1 / Y3 / Y5 failure rates + TMS lift).
- **Tested**: testing agent passed 11/11 backend tests + 100% frontend
  verification (iter25). Brand-swap to FedEx changes ZIP filenames and PDF
  doc-IDs as expected; probability ripple confirmed; admin-gating verified
  on every endpoint.
- **Security tweak post-test**: removed the hard-coded
  `test_session_admin_1` fallback from `InvestorBoardroom.jsx`'s
  `triggerDownload` (the testing agent flagged it as a dev-token leak risk
  for production bundles).


## 2026-02-15 (later 7) · Marketing Pack
- **NEW** `routes/marketing.py` (admin-gated, brand-aware):
  - `GET /api/marketing/carrier-sell-sheet.pdf` — operator-pitched carrier
    recruitment one-pager (quick-pay, named broker, photo PODs, lane focus).
  - `GET /api/marketing/shipper-sell-sheet.pdf` — shipper sell sheet
    positioning {short} as "mega-3PL discipline at small-broker service".
  - `GET /api/marketing/press-release.pdf` — MC-launch press release ready
    for newswire (Cummins quote, market thesis, lane focus, raise mention).
  - `GET /api/marketing/linkedin-posts` — JSON: 3 launch posts (Founder
    Story, Operator Insight on the 32% failure rate, Direct GTM Ask for 5
    anchor shippers). Each post has body, hashtags, audience, CTA.
  - `GET /api/marketing/cold-emails` — JSON: 3 cold-email templates
    (shipper outreach, carrier outreach, investor follow-up) with merge
    tokens and Day-+N follow-up bodies.
  - `GET /api/marketing/pack.zip` — bundles 3 sell-sheet/press PDFs +
    LinkedIn posts PDF + Cold-email templates PDF + .md copies of both for
    paste-into-sequencer use + README. ~1.6 MB.
- **Investor data-room ZIP** extended (`routes/investor.py`) to also include
  the 3 marketing PDFs (Carrier Sell Sheet, Shipper Sell Sheet, Press
  Release) so the VC gets a single download with **9 deliverables**.
- **NEW** `frontend/src/pages/MarketingPack.jsx` mounted at `/marketing-pack`
  with admin sidebar link (Megaphone icon):
  - Hero hub with one-click ZIP + 3 individual download cards.
  - Tabs: **LinkedIn Launch Posts** (live preview of all 3 posts, hashtag
    pills, CTA notes, Copy button per post) and **Cold-Email Templates**
    (subject, body, merge-token pills, Day-+N follow-up box, Copy buttons
    for both main body and follow-up).
- **Tested**: iter26 → 12/12 backend tests + 100% frontend verification.
  Zero bugs. Brand-swap to FedEx renames every PDF and content swaps
  correctly. Investor data-room ZIP now confirmed at 9 docs + README.


## 2026-02-15 (later 8) · Public Investor Executive Summary (`/investors`)
- **NEW** public endpoints (no auth) in `routes/public_site.py`:
  - `GET /api/public/investor-summary` — brand + market sizing + 3-yr
    trajectory + 36-month revenue + probability + ask + use-of-funds +
    proof points (sensitive unit-economics omitted vs. the in-app boardroom).
  - `GET /api/public/deck.pdf` — brand-stamped pitch deck PDF (inline
    disposition so it previews in the browser).
  - `GET /api/public/one-pager.pdf` — brand-stamped one-pager PDF.
  - `POST /api/public/investor-intro` — captures investor intros from the
    public form (honeypot-protected, persists to `db.investor_intros`,
    best-effort Resend email to founder).
  - Bug-fix during iter27: `InvestorIntro` Pydantic model was closure-scoped
    → FastAPI body-detection misfired and returned 422 on every POST. Hoisted
    to module scope alongside `QuoteRequestIn`/`ContactIn`.
- **NEW** `frontend/src/pages/PublicInvestors.jsx` at `/investors`,
  `/press`, and `/exec-summary` (all aliases, all public):
  - Bold hero: "We're rebuilding the freight brokerage for operators who
    actually answer the phone." 99% STRONG probability badge in gold.
  - Download CTAs (Pitch Deck + One-Pager) opening in new tabs.
  - At-a-glance metrics (TAM/SAM/SOM/Y1-failure), three reason cards, 3-year
    trajectory cards + 36-month revenue area chart.
  - "The Ask" section with $500K SAFE @ $4M cap + full use-of-funds breakdown.
  - 5 proof-point checks ("things that already exist in production").
  - Investor-intro form (#intro) with honeypot, green-check thank-you state.
  - Open Graph + Twitter Card meta tags injected on mount so LinkedIn /
    Twitter shares render with the brand logo and a punchy description.
- **PublicNav** updated: `Investors` link added between `Preferred Lanes`
  and `About`.
- **AuthProvider polish**: `/auth/me` is now skipped on public routes
  (`/`, `/home`, `/services`, `/lanes`, `/contact`, `/about`,
  `/investors`, `/press`, `/exec-summary`, `/login`, etc.) so visiting
  VCs / journalists don't see 401 console noise when they open DevTools.
- **OG image** now derived from `brand.logo_url` (falls back to the Orisei
  wordmark) so non-Orisei brands get a correct social-share preview.
- **Tested**: iter27 — 7/7 backend tests pass, full frontend verification,
  zero outstanding bugs. Honeypot drops bot submissions silently; both PDFs
  render valid `%PDF` with inline disposition; investor-intro persists +
  emails the founder via Resend.


## 2026-06-03 (later) · Brokerage Ops KPI Dashboard + Industry Gap Analysis
- **Audit first**: User asked for load tracking, invoice automation,
  carrier portal, shipper reporting, and the 4-KPI dashboard. Audit found
  ~75% already built in `routes/brokerage.py` (bookings/POD/invoices/
  drivers/onboarding/factoring/QBO/margins). Resisted rebuild; surfaced
  the real gap.
- **NEW backend** `routes/orisei_ops_kpis.py` (~170 lines, 2 endpoints):
  - `GET /api/brokerage/ops-kpis?window_days=N` — single payload with
    the 4 headline KPIs (cost-per-mile, gross margin %, fill rate %,
    on-time %), lane breakdown (sorted by volume) with CPM/RPM/margin/
    OTP per lane, and carrier performance table.
  - `GET /api/brokerage/ops-kpis/shipper-report/{shipper}` — same KPIs
    scoped to a single customer for weekly digest emails.
  - Honest defaults: 1-hour grace window on OTP; null instead of 100%
    when no OTP data exists; lane volume sort prevents tiny lanes from
    dominating headlines.
- **NEW frontend** `BrokerageOpsKpis.jsx` (~210 lines, admin/dispatcher):
  - 4 BigKpi cards across the top (CPM, Margin %, Fill Rate, OTP).
  - Window picker (7/30/90/365 days) with refresh button.
  - Lane Performance table — color-codes margin >=15% green, 8-15%
    amber, <8% red; same for OTP >=95/85/<85.
  - Carrier Performance table with cost/mi and OTP per MC#.
- **Sidebar nav** added: `nav-brokerage-ops-kpis`.
- **Seed**: 3 sample bookings inserted (Tennant MN→TX 2x, 3M MN→GA 1x)
  to demonstrate Plymouth→Dallas lane at $2.05/mi cost, 13.6% margin,
  100% OTP.

### Strategic Deliverable
- **NEW** `/app/memory/ORISEI_INDUSTRY_GAP_ANALYSIS.md` (~360 lines):
  - Capability matrix vs. SAP TM, Oracle OTM, MercuryGate, McLeod —
    matches or beats them on 12 of 14 lines.
  - 11 honest gaps prioritized P0/P1/P2/P3 with industry baseline,
    your current state, fix-effort, and cost estimates.
    P0: GPS tracking (project44), EDI 204/210/214/990 (SPS Commerce),
        spot vs. contract rate logic, SSO via WorkOS, SOC 2 Type I.
    P1: Accessorial library, EDI 856 ASN, customer self-service portal.
    P2: Multi-currency/tax, carrier PWA.
    P3: Dock scheduling.
  - Production-readiness checklist (must-have / should-have / nice-to-
    have) with vendor recommendations + price tags.
  - Efficiency + ease-of-use comparison.
  - Strategic recommendation: **stop building, start signing logos.**

## 2026-06-03 · Brokerage Margin Shield · 5-Feature Margin Protection Module
- **Strategic theme**: User pitched margin stability via two tactics —
  TMS automation absorbs labor cost ("when shipper rates drop 3%, my cost
  drops 5%") + carrier loyalty bonus locks predictable capacity. Built
  both in one cohesive module.
- **NEW backend** `routes/margin_shield.py` (~400 lines, 12 endpoints):
  - **Auto-Match engine** (`GET /api/margin-shield/auto-match/{load_id}`):
    weighted scoring (scorecard 35% + lane history 25% + equipment fit 20%
    + loyalty tier 15% + freshness 5%). Returns top-3 carriers with
    component breakdown + compliance flag per match.
  - **One-click tender** (`POST .../tender`): atomically updates load
    status + audit-logs to `db.load_tenders`.
  - **Rate Snapshot** (`GET .../rates/{load_id}`): blends DAT One +
    Truckstop + historical lane average into one view with confidence
    score (40-100). Honest `synthetic_warning` flag when DAT/Truckstop
    creds aren't in Connections Vault.
  - **Compliance Traffic-Lights** (`GET .../compliance/{mc}`): 5-check
    vetting (MC active, CSA, insurance, blocklist, drug clearinghouse)
    with green/amber/red flag. Warn-by-default when CSA data missing.
  - **Auto-Invoice on POD** (`POST .../invoice/auto/{booking_id}`):
    atomically generates invoice + QBO AR queue entry + customer email
    draft. Idempotent — re-call returns `already_invoiced:true`.
  - **Carrier Loyalty Programs** (full CRUD): flat-$ or %-of-line-haul
    bonuses, platinum/gold/silver tiers, configurable first-look window
    (default 30 min).
  - **Carrier tier assignment** (`POST .../loyalty/carriers/{mc}/tier`).
  - **Dashboard** (`GET .../dashboard`): unified KPI snapshot.
- **NEW frontend** `MarginShield.jsx` (~550 lines, admin/dispatcher):
  - 5-tab layout (Auto-Match · Rates · Compliance · Auto-Invoice · Loyalty).
  - KPI row populates from /dashboard endpoint.
  - Tier pills (Trophy/Award/Star icons) + compliance traffic-light pills.
  - Inline match-card with component score bars + one-click tender button
    (disabled when compliance is red).
  - Loyalty program create form + delete with confirm.
- **Test seeds**: 5 carriers inserted (MC-100001 Northland=platinum/clean,
  MC-100002 Prairie=gold, MC-100003 Heartland=silver, MC-100004 Apex=red
  test case w/revoked MC + expired insurance + unknown clearinghouse,
  MC-100005 Lone Star=gold). Auth sessions refreshed for 365 days.
- **Sidebar**: nav-margin-shield entry added under Brokerage · Accounting.

### Tests
- `/app/test_reports/iteration_32.json` — 31/31 backend tests + 100%
  frontend Playwright pass on first run. Zero bugs.
- `/app/backend/tests/test_iter32_margin_shield.py` (31 tests, ~2.1s)
  covers: auth gate, dashboard payload, auto-match scoring (Northland #1
  at score 93), one-click tender + audit log insert, missing-mc 400,
  dispatcher-can-tender, rate snapshot 3 sources + confidence + synthetic
  warning, compliance green/red/404, auto-invoice success/already-invoiced
  /no-pod/404, loyalty CRUD + tier assignment + 404s, brokerage/investor/
  public regression.

## 2026-06-07 (later) · Orisei Brand Identity + Ag/Grain GTM Asset Kit
- **Goal**: equip Oliver with a complete go-to-market package to sign 5
  lighthouse clients in MN's grain belt — no SOC 2 required.
- **NEW SVG logo system** (`/app/frontend/public/`):
  - `orisei-logo.svg` (800×240, horizontal wordmark) — deep navy ORISEI
    in Helvetica Black + gold chevron piercing an O (= freight in motion)
    + monospace tagline "MN · AG · GRAIN · SPECIALTY" + gold dot top-right
    (Minnesota's North Star reference).
  - `orisei-mark.svg` (200×200, square mark) — same concept, condensed for
    favicons/avatars on dark backgrounds. Embeds cleanly in PDFs/emails.
  - Brand colors locked: `#0E3A6B` navy, `#C9A24A` gold, slate `#3A4A5E`.
- **NEW backend** `routes/orisei_gtm_assets.py`:
  - `GET /api/marketing/orisei/brochure-pdf` — branded one-page PDF (~430 KB)
    rendered from internal Markdown via existing `build_branded_markdown_pdf`.
    Covers offering, $1M/$100K insurance line, BMC-84 bond, coverage lanes
    (MN harvest belt → Cargill/CHS/ADM + MSP rail + Gulf + PNW export),
    equipment, "how a load works" 6-step.
  - `GET /api/marketing/orisei/email-templates` — 3 cold-email variants
    keyed for ag/grain prospects: v1 lane-specific ("Plymouth → MSP at
    $2.85/mi"), v2 harvest-overflow ("12-hour roll-out for {city}"),
    v3 break-up ("closing your file"). All include `{first_name}`,
    `{company}`, `{shipper_city}`, `{portal_token}` merge tokens.
  - `GET /api/marketing/orisei/linkedin-profile` — full LinkedIn rewrite:
    headline, About section (2,000 chars), Featured items, Experience
    entry, connection invite template (300-char compliant), Mon/Wed/Fri
    posting cadence.
  - `GET /api/marketing/orisei/video-script` — 30-sec demo video script
    with VO copy ("echo" voice), visual storyboard (6 scenes timestamped),
    distribution channels, music recommendation. Reuses the existing
    `build_hotshot_tms_promo.py` Playwright + FFmpeg + OpenAI TTS pipeline.
- **NEW frontend** `pages/GtmAssets.jsx` + route `/gtm-assets` (admin-only,
  added to Sidebar as "GTM Marketing"):
  - Brand Identity section with both logo previews, color codes, type spec,
    and direct SVG downloads.
  - Brochure download button (fetches PDF blob → triggers browser
    download with proper filename).
  - 3 email templates each with copy-to-clipboard button.
  - LinkedIn rewrite + video script as monospace scrolling blocks with
    copy-all buttons.
- **Tested**: brochure PDF returns 200 + valid %PDF-1.4 (428 KB), all 3
  copy endpoints return JSON without error. Frontend renders all 5 sections
  cleanly, logos load and look professional, no compile errors. Sidebar
  nav-gtm-assets link works.
- **Niche rationale**: User picked ag/specialty grain over building materials,
  food/bev, med-device — copy is calibrated specifically for harvest-overflow
  pitches and Cargill/CHS/ADM crush-plant lanes.

## 2026-06-07 · TMS Competitive Parity — 10 features (A-J) closing the gap with McLeod / MercuryGate / Descartes / TMW
- **Goal**: bring Hot Shot TMS to feature parity with the mid-market TMS field
  so Orisei can pitch enterprise shippers without losing on the spec sheet.
- **NEW backend** `routes/tms_competitive.py` (~720 lines):
  - **A · Customer-portal spot-quote request** — `POST /api/public/customer-portal/{token}/spot-quote-request` token-gated, emails Oliver via Resend when creds present, drafts otherwise. Admin endpoints `/spot-quote-requests` (list) and `/{id}/quote` (mark quoted).
  - **B · Accessorial library** — `/tms-competitive/accessorials` CRUD with idempotent seed of 12 industry-standard codes (DET / LMP / LAY / TONU / DA / STP / FSC / TARP / RES / REWG / INSIDE / OVRDIM). Each code carries label, description, rate_usd, rate_type (flat/per_hour/per_mile/per_pallet), and chargeable_to.
  - **C · FMCSA auto-vetting** — `/tms-competitive/fmcsa/{mc}` hits the public SAFER snapshot API. webKey configurable via `FMCSA_WEBKEY` env var (FREE rejected by FMCSA — graceful degrade returns `fmcsa_unreachable`). Computes RED/AMBER/GREEN verdict from operating_status, safety_rating, broker_authority flags. 6h in-process cache.
  - **D · Lane analytics** — `/tms-competitive/lane-analytics?window_days=N` aggregates every booking by (origin, destination) and emits avg/median rates, $/mi RPM, OTP %, avg miles, and a capacity-tightness signal (high/medium/low) based on load count × RPM.
  - **E · Contract rate matrix** — `/tms-competitive/contract-rates` CRUD scoped by (customer_id, origin_state, destination_state, equipment, effective_from→to) + `/rate-lookup` that auto-prefers contract over spot.
  - **F · Dock / appointment scheduling** — `/tms-competitive/dock-appointments` CRUD with facility name/address, pickup vs delivery, ISO scheduled_at, duration, optional booking/carrier link.
  - **G · Multi-modal mode-shift recommender** — `POST /mode-shift` returns Intermodal (15-18% saves, +2-3d) for ≥800 mi dry/reefer and LTL (45% saves, +1d) for ≤5,000 lbs dry-van, with carrier suggestions per mode.
  - **I · Freight audit & pay** — `POST /freight-audit` reconciles carrier invoice against rate-con + accessorial breakdown; emits RED if diff > 5% & > $25 OR rate-con missing; AMBER if accessorials present but not itemized. Falls back across `carrier_rate_usd / rate_usd / settled_carrier_pay_usd / forecast_carrier_pay_usd`.
  - **J · Public RFP / digital RFQ board** — admin `/rfps` CRUD; public `/api/public/rfps` list + `/api/public/rfps/{id}/bid` submit. Per-IP rate limit (5 bids/hr) for abuse mitigation. Bid counter increments atomically.
  - **H · Driver PWA endpoints** — `/api/driver-pwa/booking/{id}?pin=` + `/status?pin=` with PIN auth. Admin endpoint `/api/brokerage/bookings/{id}/driver-pin` generates a 4-digit PIN and returns the share-link template.
- **NEW frontend pages**:
  - **`/competitive-tms`** (admin, protected) — `pages/CompetitiveTms.jsx` 9-tab module. Each tab has its own create form + list with proper test-ids. RFP tab now has a fully-wired **Create RFP dialog** with dynamic lane rows (add/remove).
  - **`/rfp-board`** (public, no auth) — `pages/PublicRfpBoard.jsx`. Lists open RFPs with deadlines + bid counts. Click "Submit bid" → dialog with per-lane rate inputs + name/email/MC.
  - **`/driver`** (public, PIN-auth) — `pages/DriverPwa.jsx`. Driver opens link from dispatcher text. Geolocation ping with every status update.
- **Customer portal upgrade** (`pages/CustomerPortal.jsx`):
  - Routing Guide tab — each lane card now has an amber **"Request quote"** button → opens `QuoteRequestDialog` modal that POSTs to the public spot-quote-request endpoint.
- **App.js + Sidebar + auth public-route list** updated to wire `/competitive-tms`, `/rfp-board`, `/driver`.
- **Tested** (iteration_34): backend 12/13 pytest pass (1 skipped intentional — requires pre-existing booking with carrier_rate_usd); frontend 100% — all 9 tabs render, default accessorials visible, FMCSA gracefully degrades, mode-shift returns Intermodal for 1900mi/42000lbs, RFP board live, customer portal Request-quote button verified.
- **Known**: FMCSA needs a real webKey from FMCSA — set `FMCSA_WEBKEY=…` in `/app/backend/.env` to enable production verdicts. Resend creds needed in `/connections` for portal spot-quote email notifications.

## 2026-06-04 (later) · Customer Portal Tracking + Routing Guide + Weekly Auto-Digest
- **Goal**: replace mid-tier TMS portals (Turvo / Parade / Revenova) with a
  self-publishing routing guide inside the existing Customer Portal — shippers
  log in and see the lanes we run, live pricing bands, and ranked carrier
  performance. Plus a Tracking tab with timeline + delivery photos, and a
  weekly auto-digest email so shippers get a recap of their freight without
  having to log in.
- **Backend** (`routes/orisei_operations.py`):
  - Portal data response now enriches every booking with a `tracking` object
    `{timeline, photo_count, current_status, eta}`. Timeline derived from
    seven canonical timestamp fields (booked_at, tendered_at, bol_generated_at,
    pickup_actual_at, in_transit_at, delivered_at, created_at fallback).
  - `GET /api/public/customer-portal/{token}/bookings/{booked_id}/photos` —
    token-gated photo list, scoped by `customer_id`/`customer_name` match so
    one token can never read another shipper's photos.
  - `GET /api/public/customer-portal/{token}/bookings/{booked_id}/photos/{photo_id}`
    streams JPEG bytes directly (supports both bytes and base64 storage).
  - `GET /api/public/customer-portal/{token}/routing-guide` — aggregates
    every brokerage_booking by `(origin, destination)` lane, computes pricing
    bands (low/median/high $ + $/mi when avg miles known), ranks the top-3
    carriers per lane by `OTP + 2*loads` composite score, and sorts lanes by
    `your_loads` desc → `total_loads` desc so the shipper's active lanes
    surface first.
- **NEW backend** `routes/orisei_auto_digest.py` (~290 lines, admin-only):
  - `POST /api/orisei/auto-digest/preview` — render one customer's recap
    as HTML email + PDF (PDF size + email_html returned)
  - `POST /api/orisei/auto-digest/run` — execute for every active customer
    with a primary contact email; supports `dry_run`, `customer_ids` filter,
    custom `week_start_iso`. Persists every run to
    `db.orisei_auto_digest_runs` with per-customer result rows (sent /
    drafted / failed / render_failed).
  - `GET /api/orisei/auto-digest/history` + `/{run_id}` — read-only audit.
  - KPI math: per-customer delivered-count, on-time%, A/R outstanding,
    invoices paid this week, top lanes moved. Skips customers with no email.
  - Cron hookup: `POST /api/orisei/auto-digest/run` with admin bearer is
    safe to call from any external cron (K8s CronJob / GH Actions /
    Vercel cron). Recommended schedule: Mondays 13:00 UTC = 6 AM Central.
- **Frontend** (`pages/CustomerPortal.jsx`):
  - Converted to tabbed layout: Overview · Tracking · Routing Guide ·
    Invoices · Quotes.
  - Tracking cards render the canonical timeline (CheckCircle bullets) and
    a lazy-loaded thumbnail grid of delivery photos. Each thumbnail opens
    the full image in a new tab via the same token-gated URL.
  - Routing Guide tab pulls `/routing-guide` and shows 4 mini-stats (Lanes
    You Ship · Lanes We Run · Last Refreshed · LIVE pill) + lane cards
    with pricing-band tile (Low / Median / High with $/mi) and ranked
    carrier list.
- **Smoke tested**: `routing-guide` endpoint returns 4 lanes, 3 with no
  rates → "request a spot quote" placeholder; Plymouth MN → Dallas TX
  with $2,580–$2,640 band + $2.4/mi + 2 ranked carriers. Tracking tab
  renders timeline; portal-tab-routing renders successfully.
- **Known still-pending**: Resend creds not yet in Connections vault, so
  auto-digest sends return `status='drafted'` until user pastes Resend API
  key.


### Earlier this same day (2026-06-04) — Orisei Operations wiring
- **Goal**: bridge "I have a TMS" → "I dispatched my first paying load" by wiring
  the in-progress Orisei Operations module (Customers · Quotes · Rate Cons) into
  the app and exposing a token-gated public Customer Portal for shippers.
- **Frontend wiring**:
  - `App.js` — imported `OriseiOperations` and `CustomerPortal`; added protected
    `/orisei-operations` route and public `/customer-portal` route (outside
    `ProtectedRoute`).
  - `lib/auth.jsx` — added `/customer-portal` to `PUBLIC_ROUTE_PREFIXES` so
    `/auth/me` is skipped on portal visits (no 401 console noise for shippers).
  - `Sidebar.jsx` — added `nav-orisei-operations` link (Building2 icon) for
    admin + dispatcher roles.
- **NEW page `pages/CustomerPortal.jsx`** — public (no auth) token-gated view
  at `/customer-portal?token=…`. Renders customer header (name + token-verified
  badge), 4 stat tiles (active shipments · delivered past 30d · outstanding
  A/R · open quotes), and three sections (Your shipments · Invoices · Quotes)
  with `StatusPill` color coding. Uses raw axios (not `api` wrapper) so it
  truly sends no auth header.
- **Bug fix** (testing agent iter33 HIGH-priority): customer/quote/rate-con
  create forms spread `{...form}` into payload — empty optional `EmailStr`
  fields became `""`, FastAPI 422'd, and `toast.error(detail)` (where `detail`
  is the validation array) crash-rendered the entire CustomersTab subtree
  (blank page). Added `clean()` helper to strip empty strings before POST and
  `errText()` helper that gracefully formats array-shaped FastAPI details for
  sonner toasts. Applied to all three tabs.
- **Verified end-to-end** (Playwright): submitting "TEST FixCheck Co" with
  only the name field populated now creates the customer, page stays alive,
  success toast fires, customer appears in list.
- **Backend** (already in place, re-verified by testing agent 16/16 backend
  pytest):
  - `/api/orisei/customers` full CRUD with deactivate
  - `/api/orisei/quotes` create + list + PDF + send (drafts when Resend creds
    missing)
  - `/api/orisei/rate-confirmations` create + PDF + send (404 when booking
    missing)
  - `/api/orisei/customers/{id}/portal-link` → `{token, share_url, expires_at}`
  - `/api/public/customer-portal/{token}` (no auth) → customer dashboard JSON
    with summary, bookings, invoices, quotes + appends visit-log entry
- **Tests**: `/app/test_reports/iteration_33.json` → backend 16/16 PASS,
  frontend 100% post-fix. Test file
  `/app/backend/tests/test_iter33_orisei_operations.py`.
- **Known minor (not blocking)**: portal `share_url` is built from
  `request.headers.get('origin')` — when the admin's browser hits the cluster
  preview host the share URL uses that host. Future cleanup: derive from a
  `PUBLIC_APP_URL` env var.


## 2026-02-20 (later) · Hot Shot TMS · One-Time-Link Gate
- **Per-VC personalized URLs**: founder generates `/tms-investors?token=abc`
  links from a new admin page at `/investor-invite-links`. Each token
  carries firm_name + optional contact_name + optional max_visits + optional
  days_valid expiry. Tokens are 22-char `secrets.token_urlsafe(16)`.
- **What the token does on the public page**:
  - Welcome banner: "Welcome, [Firm] · [Contact]" at top of hero.
  - Pre-fills the investor-intro form firm + name fields.
  - Swaps all 3 download CTAs to personalized endpoints which stamp
    "Confidential · Prepared for [Firm]" banner + diagonal CONFIDENTIAL
    watermark on every PDF page (ZIP also gets per-firm filenames).
  - Logs every visit + download event with IP, user-agent, scroll depth,
    referrer to `tms_investor_invite_links.visits[]`.
  - First page-view / first download triggers a real-time Resend alert to
    `oliver@livecleans.com` (skipped silently if Resend not configured).
- **Failure modes** (HTTP-correct):
  - Unknown token → 404.
  - Disabled token → 410 ("disabled").
  - Expired (past `expires_at`) → 410 ("expired").
  - Visit cap reached → 423 ("locked").
  - Bad token gracefully falls back to non-personalized downloads on the page.
- **NEW backend** (`routes/tms_invite_links.py`, ~400 lines):
  - Admin endpoints: `POST/GET /api/investor/invite-links`,
    `POST /api/investor/invite-links/{token}/disable`,
    `DELETE /api/investor/invite-links/{token}`.
  - Public endpoints: `GET /api/public/tms-link/{token}` (validate),
    `POST /api/public/tms-link/{token}/visit` (log event),
    `GET /api/public/tms-link/{token}/deck.pdf` (personalized),
    `GET /api/public/tms-link/{token}/one-pager.pdf` (personalized),
    `GET /api/public/tms-link/{token}/data-room.zip` (personalized).
  - `_resolve_origin()` derives share URLs from browser `Origin`/`Referer`
    headers so admins always get a public preview URL (not the in-cluster
    Kubernetes hostname).
  - Whitespace-only firm names rejected via custom validator.
- **NEW frontend** `TmsInviteLinks.jsx` (~250 lines, admin-only at
  `/investor-invite-links`): full CRUD with stats grid (visits, unique
  IPs, per-doc download counts, last-visit timestamp), share-URL copy
  buttons, disable + delete with confirm prompts. Sidebar nav entry
  added under Investor Boardroom.
- **TmsInvestors.jsx** updated with `useSearchParams` + token handshake +
  download-event tracking + welcome banner + graceful fallback when token
  is invalid.

### Tests
- `/app/test_reports/iteration_31.json` — 15/15 backend tests pass (100%),
  full frontend Playwright pass (100%), zero bugs found.
- `/app/backend/tests/test_iter31_invite_links.py` — covers admin CRUD,
  auth gating, validation, visit/download logging, all 4 HTTP failure
  modes (404/410/410/423), personalized PDF/ZIP filenames + watermark,
  full Orisei + non-personalized regression.

## 2026-02-20 · Hot Shot TMS Rebrand + Public VC Pitch Page
- **Renamed TMS platform** from "LiveCleans · TMS" → **"Hot Shot TMS"**.
  Logo letter L → H. Cyan accent retained.
- **Fixed broken "Launch the Demo" CTA**: previously routed VC visitors to
  `/login` (the protected app gate). Now reads "Watch the Live Demo" and
  routes to the dedicated public pitch page at `/tms-investors`.
- **NEW** public Hot Shot TMS investor page at `/tms-investors` (aliases:
  `/tms-pitch`, `/demo`) — completely separate from the Orisei brokerage
  investor page at `/investors`. Sections:
  - Hero with auto-rotating brand reel (Tennant, Walmart, FedEx, Caterpillar,
    Apple, Amazon, Tesla, Coca-Cola, Boeing, Nike) — demonstrates the
    re-theming wedge visually.
  - Embedded promo.mp4 (autoplay, muted, loop) with tap-for-sound overlay.
  - 7-column stats bar (50+ modules · 200+ APIs · 9 ERPs · 14 integrations
    · 16 themes · 77-brand directory · 45-metric scorecard).
  - **Plug-and-play** section: 9 ERP connector cards (SAP, Oracle, D365,
    NetSuite, Infor, Sage, Epicor, IFS, Custom REST) + 14 launch-day
    provider cards (DAT, Truckstop, Convoy, Uber Freight, 123Loadboard,
    Triumph, Apex, OTR, Resend, QuickBooks, RMIS, Carrier411, FMCSA, Tivly)
    + Fernet-encryption security callout.
  - **Changeability** section: dual list of what re-themes instantly (6
    items) vs. what stays put (4 security/audit items).
  - 10-feature grid with brand-cyan iconography.
  - Founder section with 13-year tenure, Plymouth MN, international
    specialist, all 6 modes.
  - The Ask: $1.5M seed SAFE @ $8M cap, 20% discount. 3 milestone cards.
    TAM/SAM/SOM ($15.3B / $4.2B / $12M).
  - Investor intro form reusing existing `/api/public/investor-intro`.
- **NEW** backend `routes/tms_investor.py`:
  - `GET /api/public/tms-pitch-summary` — JSON payload for the page.
  - `GET /api/public/tms-deck.pdf` — Hot Shot TMS pitch deck PDF (15 sections).
  - `GET /api/public/tms-one-pager.pdf` — at-a-glance PDF.
  - `GET /api/public/tms-data-room.zip` — bundled deck + one-pager + README.
- Updated `lib/auth.jsx` PUBLIC_ROUTE_PREFIXES with `/tms-investors`,
  `/tms-pitch`, `/demo` so /auth/me doesn't fire on those public routes.
- Fixed Plymouth MN (was "Minneapolis · MN") in About.jsx founder pill +
  footer.

### Tests
- `/app/test_reports/iteration_30.json` — 9/9 backend tests pass (100%),
  full frontend Playwright pass (100%), zero bugs found on first run.
- `/app/backend/tests/test_iter30_tms_investor.py` — covers all 4 new
  public endpoints + Orisei regression (3 endpoints) + shared intro form.

## 2026-02-18 (later) · Personalized Investor PDF · "Prepared for [VC]" stamps
- **Feature**: Admin can now generate VC-firm-personalized versions of the
  pitch deck, one-pager, or full data-room ZIP in a single click. Every
  page of every personalized PDF gets:
    1. A top center banner: "CONFIDENTIAL · Prepared for [Firm] · Attn: [GP] · [Date]"
    2. A faint diagonal "CONFIDENTIAL · [FIRM]" watermark (gold, 7% alpha)
  The kind of small touch GPs notice and remember.
- **Backend** (`routes/investor.py`):
  - `PersonalizationIn` Pydantic model: firm_name (required, 1-120 chars),
    contact_name (optional), prepared_date (optional, defaults to today),
    doc_type ("deck" | "one-pager" | "zip").
  - 4 new admin-gated endpoints:
    `POST /api/investor/personalized-deck.pdf`
    `POST /api/investor/personalized-one-pager.pdf`
    `POST /api/investor/personalized-data-room.zip`
    `GET  /api/investor/personalized-outreach` (audit history)
  - The personalized ZIP contains 4 personalized PDFs (deck + one-pager +
    industry probability + business plan, all with "for_{firm_slug}" in
    filename) + clean XLSX + clean CSV (analysts can still copy/modify
    the model without watermarks) + README.txt with "Prepared for: [Firm]".
  - Every generation is audit-logged into `db.investor_personalized_outreach`
    with id, doc_type, firm_name, contact_name, prepared_date, generated_at.
- **Backend** (`routes/orisei_docs.py`): `_draw_heraldic_border()`,
  `_build_doc()`, and `build_branded_markdown_pdf()` now accept an optional
  `personalization` kwarg that flows through to the page decoration callback.
  Diagonal watermark + top banner are drawn only when personalization is
  supplied — every existing caller (BOL/POD/forms/non-personalized investor
  PDFs) is unchanged.
- **Frontend** (`InvestorBoardroom.jsx`):
  - "Personalize for VC" CTA (gold-bordered, dashed) inside the Data Room card.
  - Polished dialog with firm-name input (required), GP/contact input
    (optional), prepared-date input (optional, shows today as placeholder),
    and 3 doc-type tiles (Pitch Deck · One-Pager · Full Data Room).
  - Live audit history shows recent personalized sends (firm + contact +
    doc-type pill + date) inside the dialog.
  - data-testids: personalize-for-vc-button, personalize-dialog,
    personalize-firm-name, personalize-contact, personalize-date,
    personalize-doctype-{deck|one-pager|zip}, personalize-generate,
    personalize-cancel, personalize-history.

### Tests
- `/app/test_reports/iteration_29.json` — 9/9 backend tests pass (100%),
  full frontend Playwright pass (100%), zero bugs found on first run.
- `/app/backend/tests/test_iter29_personalized_investor.py` — covers
  PDF magic bytes, Content-Disposition firm-slug filenames, ZIP entries
  (4 personalized PDFs + clean XLSX/CSV + README with firm name),
  empty-firm validation 422, no-auth 401, history sort + admin gating,
  and non-personalized-endpoint regression.

## 2026-02-18 · Brutally Honest VC Package · Pre-Revenue Framing
- **Rewrote investor financials to reflect actual pre-revenue / pre-launch
  reality** so the VC package is due-diligence-ready and won't blow up the
  moment a real GP starts pulling threads.
- `routes/investor.py` changes:
  - NEW `CURRENT_STATUS` dict surfaces `stage="Pre-revenue · Pre-launch"`,
    `live_loads_booked=0`, `live_revenue_usd=0`, `built_to_date` (6 items
    already in production), `filed_in_progress` (3 items pending raise),
    and `key_risks` (6 honest risks).
  - `_financial_model_rows()` reset to honest cold-start ramp: Y1 M1–M3 = 0
    loads (authority filing period), Y1 total = ~144 loads ($310K revenue);
    Y2 = ~579 loads; Y3 = ~1,189 loads at industry-median 15% gross margin.
    Y3 EBITDA modeled at +$157K / 6% margin (was prior $441K / 23%).
  - Gross-margin keys renamed to be explicit: `avg_gross_margin_pct_y1`
    (10%, new-broker reality), `avg_gross_margin_pct_mature` (15%, industry
    median by Y3). LTV renamed to `ltv_per_customer_3yr_usd` ($6,500).
    Break-even moved from Month 9 → Month 22 (honest).
  - Probability cap lowered 99% → **90%** to reflect irreducible freight-
    market volatility (recessions, fuel shocks, key-customer bankruptcies).
    TMS contribution dropped from +9pts → +5pts (operator estimate, not
    peer-reviewed). Industry-benchmark key renamed
    `ai_powered_broker_success_lift_pct` → `ai_tooling_estimated_lift_pct`
    + new `honesty_note` field.
  - Deck markdown + one-pager rewritten to explicitly tag every Y1/Y2/Y3
    number as "Forecast" / "Target" — never as realized revenue. Added
    section 5 "Current Status (the honest read)" listing built vs. filed
    work + carrier/shipper counts at zero.
  - **Bug fix**: XLSX builder + deck markdown were crashing on stale keys
    `UNIT_ECONOMICS['avg_gross_margin_pct']` / `ltv_per_customer_year3_usd`
    after the rename. Both repaired; downloads now succeed.
- `InvestorBoardroom.jsx`:
  - NEW `pre-revenue-banner` (amber-bordered) at top of page with stage
    pill, 4 live-zero stats (loads/revenue/carriers/shippers), built-to-
    date + filed-in-progress lists.
  - Unit-economics card extended to 12 metrics including Y1 + Y3 gross
    margin, break-even month, Y3 EBITDA-margin target, honesty note.
  - Industry benchmark card now shows `ai_tooling_estimated_lift_pct`
    (+5pt, marked operator estimate) and surfaces the
    benchmarks `honesty_note` italicized below sources.
  - NEW red-bordered `key-risks-card` listing all 6 honest risks (customer
    acquisition slippage, gross-margin compression, carrier liquidity,
    freight-market cycle, customer concentration, authority timing).
- `PublicInvestors.jsx`:
  - Animated `public-stage-pill` ("PRE-REVENUE · PRE-LAUNCH · ALL FIGURES
    FORWARD-LOOKING") prominently rendered under the hero subhead.
  - NEW `public-key-risks` section with 6 risk cards above the intro form.
  - Y3 trajectory headline reframed: "From pre-revenue today to $2.6M
    revenue and 6.1% EBITDA by Year 3" (was: bootstrap-to-$3.8M @ 23%).
  - Probability badge now caps at **90% STRONG** instead of 99%.

### Tests
- `/app/test_reports/iteration_28.json` — 16/16 backend pytest pass.
- `/app/backend/tests/test_iter28_investor_honesty.py` — 5 test classes
  covering current_status block, renamed unit-economics keys, renamed
  industry-benchmark keys, probability cap at 90, fragile-band scoring,
  XLSX/PDF/ZIP regression, public investor summary, marketing-pack
  regression.
- Frontend `/investors` public: visually verified — stage pill, 6 risk
  cards, 90% STRONG badge (no 99% anywhere), Y3 ~$2.6M trajectory.
- Frontend `/investor-boardroom` admin: 13/13 data-testids present in
  DOM, 0 console errors.


## 2026-02-15 (later 9) · Real per-brand logos in every printable document
- **Bug**: After theme switch, BOL/POD/forms still showed the Orisei
  Calafia griffin (and Orisei brand kept rendering inside a visible gray
  bitmap "box" because the source PNG was RGB with no alpha channel).
- **Fix 1 — generate brand-themed monogram logos** for every non-Orisei
  brand in `backend/scripts/generate_brand_logos.py`:
  - 512×512 public-served + 200×200 PDF-optimized PNGs per brand.
  - Disc gradient using `primary_color → lighten/darken`, accent-color
    outer ring + thin inner ring, serif-bold monogram (1-2 chars) in the
    accent color, twin diamond flourishes.
  - Saved to `/app/frontend/public/brand/logos/{brand_id}.png` (public) and
    `/app/backend/routes/_brand_logos/{brand_id}.png` (PDF). DB
    `company_brand` doc updated with `logo_url` + `logo_pdf_path`.
  - Already generated for: fedex (purple/green), walmart (blue/yellow),
    acme (slate test).
- **Fix 2 — auto-generate on new brand creation**: `routes/branding.py`
  `_generate_brand_logo()` helper invoked from both
  `POST /api/branding/generate` and `POST /api/branding/manual` so any new
  brand created in-app immediately gets a proper logo without manual
  intervention.
- **Fix 3 — `_brand_logo_path()` fallback chain**: explicit
  `brand.logo_pdf_path` → auto-generated `/_brand_logos/{brand_id}.png` →
  inline text monogram (last resort).
- **Fix 4 — Orisei gray-box repair**: new
  `backend/scripts/repair_orisei_logo.py` strips both gray (~205,207,206)
  and white (~255) background pixels from `orisei_logo.png` /
  `orisei_wordmark.png` using HSV-based "bright + low-saturation" detection,
  preserves the navy-and-gold griffin pixels, soft-feathers the edges, and
  saves true RGBA transparency. The wordmark PNG had a navy background; the
  script auto-detects dark vs. bright backgrounds and switches matching
  strategies. Original PNGs are backed up to `*.png.bak` for safety.
- **Verified**: FedEx BOL now embeds the purple/green FedEx-monogrammed
  logo (1 image on page); Orisei BOL embeds both the griffin disc + the
  navy wordmark (2 images) with clean transparent edges. Homepage hero
  shows the griffin floating cleanly inside its blue card with no gray
  bitmap box.
