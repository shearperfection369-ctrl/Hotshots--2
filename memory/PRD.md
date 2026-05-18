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
