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
