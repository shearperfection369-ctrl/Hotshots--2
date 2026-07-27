# Orisei Freight Solutions TMS · `/app/memory/CHANGELOG.md`

> Append-only changelog. Each session writes new entries at the **top**.

## Iteration 69 (Jun 2026) — Day-7 Bug Fix · Company Fleet · Month-Long Sims · Accuracy Assessment

- **FIXED day-7 duplication bug**: tick persisted `sim_day` clamped to duration, so
  post-week settling re-fired the day-rollover every tick (42 dup "day 7" entries,
  over-accrued overhead, market re-walks). True sim_day now persists (display clamps
  in state()), each day closes once (dedupe guard), overhead bills in-week days only.
  Historical sims repaired via one-off migration.
- **Company fleet (own authority)**: `sim_company_trucks` collection seeded with
  2 default trucks (ORISEI 101 Van / 102 Van+Reefer, Minneapolis base).
  GET/POST/DELETE /api/sim/company-trucks (admin/dispatcher/owner). Sim dispatches
  own trucks FIRST (score bonus, ≤600mi deadhead, one load at a time via truck_busy);
  own-fleet economics = fuel(diesel/MPG) + driver $/mi + maintenance $/mi, full rate
  kept (~38% margins vs 17% brokered); weekly truck payment+insurance accrued as
  fleet_fixed_costs in net margin; no fall-through/quickpay/txn-fee on company loads.
  UI: "My Company Fleet" card (stats + add/delete), MY TRUCK badges, leaderboard shows
  ORISEI FLEET units.
- **Month-long sims**: duration_days up to 31, speed up to 360 sim-min/sec, query
  limits raised to 2000. Verified full 31-day run: 208 loads, no dup days, correct
  overhead (226.9×31) and fleet fixed (fleet weekly/7×30).
- **Accuracy assessment** delivered: /app/SANDBOX_ACCURACY_ASSESSMENT.md — sandbox vs
  DAT Week-22 2026 rates (van buy $2.68 exact), margins optimistic ~2×, diesel
  calibrated to 2024-25 era ($3.68 vs real $5.60+ 2026) — recalibration offered.
- Load board source badges (DAT/Truckstop/Convoy/Uber/123LB/Direct) with weights.

---


## Iteration 67-68 (Jun 2026) — Agent Sentinel · Launch Blast · Password Self-Service · Route Optimizer · Sandbox Industry Variables · AI Growth Copilot

- **Agent Sentinel** (`/api/sentinel/*`, /sentinel page): 30-min automated health
  sweeps on all watched deployments (HTTP + latency), live LLM ping w/ budget-error
  detection, rolling API 5xx error rate (middleware), alerts feed w/ ack/auto-resolve,
  red alert banner (SentinelBanner.jsx) across the OS. CRUD watched deployments.
- **Launch Email Blast** (`/api/launch-blast/*`, /launch-blast): launch card → branded
  HTML announcement email; deduped prospect list (revenue+lighthouse+shipper_accounts);
  Resend send or queued_awaiting_key; test-send; owner/admin gated.
- **Password Self-Service**: POST /api/auth/change-password (verifies current, min 8,
  kills other sessions, sets password_self_set so seed never overwrites); sidebar
  key button + ChangePasswordDialog.
- **Route Optimizer** (`/api/route-optimizer/*`, /route-optimizer): Nominatim geocoding
  + OSRM real road routing (no keys), dark Leaflet map w/ route line, margin calc
  (rate/fuel/MPG/driver pay/tolls → net, RPM, GO/CAUTION/NO-GO), saved load history.
- **Sandbox Industry Variables** (sim_week.py): 13-line daily overhead ($226.90/day),
  DOE diesel + spot-market random walks affecting rates/FSC, lumper/layover/reweigh/
  appt-bump exceptions, carrier fall-through rebooks, OS&D claims 1.5%, bad debt 2%,
  quick-pay income, $12/load settlement fees — TRUE net margin; market strip in UI.
- **AI Growth Copilot** (`/api/copilot/*`, /growth-copilot): mission $20k/wk NET margin.
  Live business state (excl. samples), Claude 4-phase master plan w/ checkable tasks,
  weekly AI briefing, multi-turn grounded chat, 20-item freight compliance watchtower
  (FMCSA, BMC-84, BOC-3, UCR, 49 CFR 371.3/370, vetting, double-brokering, tax).
- Owner sidebar rule (owners see all but Admin·Users); test sessions (admin+dispatcher)
  now seeded idempotently on startup when ENABLE_DEV_LOGIN.
- Testing: iteration_66.json (17/17 + 28/28) and iteration_67.json (15/15, frontend 95%
  → the 3 minor items fixed post-test: progress-bar min-width, chat msg testids,
  dispatcher session seed).

---


## Iteration 67 (Jun 2026) — Partner Owner Logins · Doug in Brochure · Launch Cards

- **Partner password logins** (`POST /api/auth/login`, bcrypt + brute-force
  lockout 5 fails → 15 min 429): oliver@oriseifreight.com (admin/primary),
  daniel@ + doug@oriseifreight.com (new `owner` role). Seeded idempotently at
  startup from `PARTNER_*_PASSWORD` env keys. Login page got a
  "Partner sign-in" email/password form.
- **Role hierarchy**: `owner` added (full operational access; 403 on
  admin-only endpoints like /api/admin/users — authorization stays with the
  primary admin). AdminUsers page shows owner role/badge/description.
  `/api/admin/users` no longer returns password_hash.
- **Doug Graham in business plan brochure**: 3-founder cover band (equal
  thirds), contact footers updated; fixed `⅓` glyph → "1/3" across all PDF
  generators (plan_brochure, orisei_docs markdown renderer, receipts,
  brokerage) so agreements print clean.
- **Launch announcement cards** (wide LinkedIn/X + square Instagram) generated
  from the Califia seal, added to Brand Kit launch section.
- Testing: iteration_65.json — 13/13 backend, all frontend flows pass, zero
  regressions.

---


## Iteration 66 (Jun 2026) — Official Logo Pack · Launch Edition

- Generated Queen Califia seal variations (gold-on-light, navy mono official
  stamp) plus hoodie front/back, structured cap, and trucker+beanie merch
  mockups via Gemini Nano Banana (assets in `backend/routes/_brand_pack/`
  and `frontend/public/brand/pack/`).
- New `backend/routes/logo_pack.py` — `build_logo_pack_pdf()` renders a
  6-page print-ready brand pack (cover, seal story + specs, variations,
  wordmark + palette + typography, hoodie program, headwear program).
- New endpoint `GET /api/brokerage/logo-pack.pdf` (auth-required).
- Brand Kit page: new "Official Logo Pack · Launch Edition" section with
  7 cards (PDF via authed blob download + 6 high-res PNGs), tested e2e.

---


---

## 2026-07 · Iterations 64-65 — Operation Sandbox · Field Manual · Alignment Guardian
- **Operation Sandbox** (`routes/sim_week.py`, `pages/OperationSandbox.jsx`, route `/sandbox`,
  sidebar nav-sandbox): full-fidelity week simulation — 36 nationwide sample carriers,
  current FSC (DOE $3.68 → $0.41/mi), time-compressed clock (default 1 sim day ≈ 2 real
  min, frontend ticks POST /api/sim/tick every 3.5s), AI matching/booking, live GPS
  movement on dark Leaflet map, detention/breakdown/weather exceptions with AI triage,
  POD→auto-invoice→factoring (85%/3.75%)→shipper payment, live ledger + daily P&L +
  carrier leaderboard. Bookings/shipments/invoices mirrored into real collections
  (is_sample + sim_id) so BOL/POD PDFs and main tracking map work. Verified full week:
  $98.8K revenue, $12.7K net margin, 11 loads fully closed. /api/sim/reset purges all.
- **Command Deck Field Manual** (`routes/platform_manual.py`): 7-page colorful brochure
  manual — platform map, carrier integration steps, daily loop, Hunter guide, docs &
  money, Sandbox instructions. GET /api/brokerage/platform-manual.pdf (+ button on
  Sandbox page).
- **Alignment Guardian** (load_hunter.py + LoadHunterTab.jsx): 4-layer reasoning
  architecture against agentic misalignment. L2: reasoning trace (factor contributions,
  top/weakest signal) + data-completeness confidence on every winner. L3: auto-book now
  additionally gated on confidence ≥ threshold. Monitors (GET /api/load-hunter/alignment):
  cherry-picking, margin erosion, shipper concentration, carrier starvation, risk-override
  drift — with recommendations; targets configurable (POST /alignment/config). L4 feedback
  loop (POST /feedback/run): settled-vs-forecast margin variance, late-payer detection,
  carrier relationship scoring (db.carrier_relationship) → weight suggestions that are
  NEVER auto-applied (human approves via POST /feedback/apply → audit-logged retrain).
- LESSON: never batch multiple search_replace edits to the SAME file in one parallel
  call — edits clobber each other (hit twice: Brokerage.jsx tabs, LoadHunterTab import).

---

## 2026-06/07 · Iterations 63 — AI Load Hunter · LTL Rate Cards · AR Engine · Carrier Brochure
- **AI Load Hunter** (`routes/load_hunter.py`, `LoadHunterTab.jsx`, Brokerage "AI Hunter" tab):
  autonomous load selection — scans all boards in one pass (~20ms), scores on 6 weighted
  components (margin %, shipper reliability, lane profitability, fuel economics, detention
  risk, driver match) with modes balanced/high_margin/high_volume/custom; shipper risk
  registry (`db.shipper_risk`) auto-rejects risky freight unless margin overrides; carrier
  pre-match reuses `dispatch_autopilot._score` (`db.dispatch_carriers`, note: `is_active`
  field); review queue + one-click book AND full auto-book under $ cap / score floor /
  daily max; full audit trail + compliance policy endpoint; 45s frontend auto-scan loop.
  Endpoints: /api/load-hunter/{scan,winners,config,risk,audit,compliance,stats}.
- **LTL Rate Card engine** (`routes/ltl_rate_cards.py`, `LtlRateCardsTab.jsx`, "LTL Rates"
  tab): negotiated cards for R+L/SAIA/Dayton/ODFL/XPO/Estes (discount %, FSC %, min charge),
  zone-based CWT rating with NMFC class multipliers + weight breaks + accessorials,
  multi-carrier ranked quotes with suggested sell + margin math, inline card editing,
  quote history. Endpoints: /api/ltl/{cards,quote,quotes}.
- **AR Aging & Collections** (`routes/ar_aging.py`, `components/ARAgingPanel.jsx` in the
  Accounting tab): 30/60/90+ buckets, per-customer rollups with flags
  (watch/escalate/credit_hold), idempotent auto-invoice from delivered/settled bookings,
  sync-risk pushes 61+ day past-due shippers into the Hunter's risk registry, payment
  reminders (dunning log; email pending Resend key), mark-paid.
  Endpoints: /api/ar/{aging,auto-invoice/run,sync-risk,invoices/{id}/mark-paid,invoices/{id}/remind,dunning}.
- **Margin by day**: `daily` series added to /api/brokerage/ops-kpis + AreaChart on
  BrokerageOpsKpis page.
- **Carrier brochure**: 6-page colorful PDF (`routes/carrier_brochure.py`, reuses
  plan_brochure helpers) — value prop, platform, integration (ELD/EDI/API/no-tech),
  load lifecycle, payment options. GET /api/brokerage/carrier-brochure.pdf; download
  button in Drivers tab.
- Tested: testing agent iter63 — 18/18 backend, 5/5 frontend flows, 100%.
- Also this session: Business Plan v2.0 Partnership Edition (Daniel W. Karsor 50/50,
  $10K use of funds), MN partnership agreement PDF, business-plan brochure PDF,
  real News/Traffic feeds on Dashboard (WZDx + RSS).

---

## 2026-06 (June) · Iteration 64 — Real News & Traffic on Dashboard
- **/api/news de-mocked**: now serves real RSS headlines via `routes.freight_news.fetch_all_news()`
  (Transport Topics, Land Line, CCJ, Trucking Dive, Trucking Info) with true relative
  timestamps. Removed the 40-item `MOCK_NEWS` corpus from `server.py`.
- **/api/traffic de-mocked**: new `routes/traffic_live.py` pulls real active roadwork /
  lane-closure incidents from public state-DOT **WZDx feeds** (no API keys): WI, IA, IN,
  MO, KY, NY, WA, UT, ID, DE, LA. Geo-based — accepts `?lat=&lng=`, picks the 3 nearest
  state feeds, filters active events within 250 mi, dedupes segments, ranks
  severity+distance, caches 10 min. Removed the 25-item `MOCK_TRAFFIC` corpus.
  NOTE: MnDOT's own feed (mn.carsprogram.org) blocks cloud IPs — Twin Cities users see
  adjacent WI/IA/MO corridors (real I-94/I-35 data).
- **Dashboard.jsx**: traffic widget now shows distance (mi) + impact type + agency,
  links to the state 511 site, has an empty state (`traffic-empty`); news items link
  out to the article; `/traffic` call reuses the weather banner's cached geolocation
  (`tms-weather-geo`).
- Tested: curl (30 real WI incidents at MSP coords; real RSS headlines) + dashboard
  DOM screenshot confirms no "Holland MI plant" / "I-394" mock strings remain.

---

## 2026-06 (June) · Iteration 63 — Business Plan v2.0 Partnership Edition
- **Business Plan amended** (`/app/BROKERAGE_BUSINESS_PLAN.md` → v2.0): Daniel W. Karsor
  added as 50/50 co-founder & principal owner (Brooklyn Park MN; barbershop + podcast
  studio owner; West African heritage; software developer). Financials recapitalized
  around his **$10,000 cash infusion** (lean launch: Y1 OpEx $22.5K, cash-flow positive
  Mo5, per-partner Y1 share $28,745). New §10.2 Use-of-Funds breakdown (6 categories
  summing to $10,000 incl. $1,174 Owner Launch Runway Reserve) + §10.3 Owner Launch
  Runway ladder (mirrors Launch Runway tab phases) + §11 Partnership Governance.
- **MN 50/50 Partnership Agreement** (`/app/PARTNERSHIP_AGREEMENT.md`): full
  member-controlled LLC agreement under Minn. Stat. Ch. 322C — capital contributions,
  50/50 allocations, unanimous-consent major decisions, deadlock/shotgun buy-sell,
  ROFR, death/disability buyout, non-compete carve-outs for both members' outside
  businesses, IP assignment, signature + notary blocks.
  Endpoints: `GET /api/brokerage/partnership-agreement` (md) + `/pdf` (branded PDF).
- **Colorful brochure PDF** (`/app/backend/routes/plan_brochure.py`): 6-page
  magazine-style canvas-drawn brochure (cover, at-a-glance stat cards, founder panels,
  use-of-funds bars, launch-runway timeline, 3-year financial spread).
  Endpoint: `GET /api/brokerage/business-plan/brochure.pdf`.
- **Frontend** (`Brokerage.jsx` BusinessPlanTab): new "Brochure PDF"
  (`business-plan-brochure-btn`) and "Partnership Agreement"
  (`partnership-agreement-btn`) download buttons.
- Tested: all 4 endpoints curl 200 via preview URL; brochure pages visually verified
  (fitz render); Business Plan tab screenshot confirms Karsor/$10K content + buttons.

---

## Iter 60 · 61 · 62 — 2026-07-03 · Real geolocation-driven weather (mock removal)

**Status**: ✅ 7/7 backend + 6/6 frontend across three iterations (iter_60/61/62.json). Zero mocked strings in weather widgets.

**User bug**: screenshot showed the top-of-page "LIVE WEATHER FEED" banner still hard-coding old Tennant-era facility mocks (Golden Valley MN, Holland MI, Louisville KY). User demanded real weather scoped to their actual browser location.

**Fix (backend)** — `/app/backend/routes/weather.py`:
- GET `/api/weather/alerts` now accepts optional `?lat=&lng=` query params from the browser's `navigator.geolocation.getCurrentPosition()`.
- Removed the mock/synthetic fallback entirely. Response shape: `{items, count, no_active_alerts, needs_location, resolved_from}`.
- Priority: browser_geolocation → saved user locations → `needs_location: true` (never a fake row).
- Real NWS calls: verified Denver → 3 real Air-Quality Alerts from NWS Denver; Miami → 0 with clean "all clear" state.

**Fix (frontend banner)** — `/app/frontend/src/components/WeatherAlertsBanner.jsx`:
- Full rewrite of the geolocation flow: cached to `localStorage.tms-weather-geo` for 24h, five distinct empty states (idle/requesting/denied/unavailable/unsupported/all-clear), Grant-location CTA button.

**Fix (Dashboard Facility Conditions widget)** — `/app/frontend/src/pages/Dashboard.jsx`:
- Ripped out the `weather` prop that fed the widget mock brand facilities.
- Rewrote `FacilityConditions` to auto-populate a "📍 <your city>" row from `navigator.geolocation` on mount, hitting Open-Meteo `/v1/forecast` for real conditions and BigDataCloud `/reverse-geocode-client` for a human city label (Denver, Colorado / London, England / Tokyo, Japan verified in tests).
- localStorage key bumped v1 → v2 to invalidate stale cache from broken reverse-geocoder.
- Extra cities can still be added manually via the existing Open-Meteo geocode search — no API key needed anywhere.

**Bug caught + fixed via testing agent (iter 62)**: Open-Meteo has NO `/v1/reverse` endpoint (404). Swapped to BigDataCloud (free, CORS-open, no key).



## Iter 59 — 2026-07-03 · Leaflet reliability fix (Uncaught runtime crash killed)

**Status**: ✅ 100% frontend (iter_59.json) — no LatLng pageerror, no red-screen, no AppErrorBoundary trigger under normal conditions. Forced-bad-data test showed graceful degradation with the amber "N shipments · no GPS yet" badge.

**Root cause** (user reported red-screen crash: `Invalid LatLng object: (undefined, undefined) at createMarker → useMutableLeafletElement → useLayer`):
`/app/frontend/src/components/MapView.jsx` was passing `[s.current_location.lat, s.current_location.lng]` straight to `<Marker>` — any shipment lacking `current_location` (a common transient state right after auto-offer/book flows create a fresh Shipment before the tracking simulator populates a location) blew up the entire React tree.

**Two-layer fix**:
1. **Defensive filtering** inside `MapView.jsx` — new `hasLatLng()` helper; `safeFacilities`, `safeShipments`, and route-polyline points all pass through it before being handed to Leaflet. Invalid rows are dropped and an amber badge (`data-testid=map-skipped-warning`) counts them.
2. **Two React error boundaries**:
   - `MapErrorBoundary` (`/app/frontend/src/components/MapErrorBoundary.jsx`) — wraps only the map subtree; renders a red-tinted "Map temporarily unavailable" card with a Retry button if anything still slips through.
   - `AppErrorBoundary` (`/app/frontend/src/components/AppErrorBoundary.jsx`) — wraps the whole `<BrowserRouter>` in `App.js`; catches ANY uncaught runtime error site-wide, renders a friendly "Console recovery" card with Try again + Reload + a collapsible diagnostic pane. **No more red-screen-of-death for the user mid-shift.**



## Iter 57 · 58 — 2026-07-03 · Orisei Welcome Kit + Sidebar cleanup

**Status**: ✅ 11/11 backend pytest (iter_58 retest), 100% frontend flows (iter_57.json).

- **Removed** "Shipper Intake" nav entry from Sidebar. Route still exists (no breakage), just not surfaced.
- **New backend endpoints** in `/app/backend/routes/shipper_relations.py`:
  - `GET  /api/shipper-relations/accounts/{id}/welcome.pdf` — instant PDF download (Orisei-branded via `build_branded_markdown_pdf`).
  - `POST /api/shipper-relations/accounts/{id}/send-welcome` — generates PDF + attaches to mocked Resend email + auto-logs an activity note (kind=email, ACT- prefix, into `shipper_activity_log`) + persists to `shipper_welcome_kits` audit table.
  - `GET  /api/shipper-relations/accounts/{id}/welcome-history` — audit trail of kits sent.
- **Auto-greeting**: personalized professional Orisei greeting — parses first name from contact, mentions company_name, references Orisei's TMS strengths (autopilot, aggregator, claims, QBRs), invites reply/call. Uses proper Unicode apostrophes (fixed HTML-entity leakage before ship).
- **PDF sections** in the welcome kit: personal note → Why Orisei → Account snapshot → ROI snapshot (when annual_volume_loads > 0) → Assigned incentives → 30-day onboarding roadmap → next step CTA.
- **Frontend**: cyan-bordered "Orisei welcome kit" card in the account detail modal (below lifecycle mover). Sender input + Preview PDF + Send welcome kit buttons. Green delivery-receipt block appears after send. Send button auto-disables when contact_email missing.
- **Bug caught+fixed via testing agent (iter 58 retest)**: initial version wrote to `db.shipper_activities` while the 360° view reads from `db.shipper_activity_log` — fixed to use the canonical collection + `ACT-` prefix.



## Iter 55 — 2026-07-03 · Dispatch Autopilot + Full ML Integration

**Status**: ✅ 26/26 backend tests pass, 100% frontend flows (iter_55.json). ML AUC 0.944, R² 0.558.

- **Rule-based dispatch engine** (`/api/dispatch/*`) — new `/app/backend/routes/dispatch_autopilot.py`:
  - Carrier availability matrix (CRUD + seed 10 demo carriers)
  - Scoring engine — HARD constraints (equipment, weight, lane, insurance) + SOFT scoring (on-time, damage, rate alignment, idle boost, shipper pref, accept history) → 0–100 score with breakdown
  - Margin engine — load rate − (carrier RPM × miles)
  - Auto-offer to top-N qualified carriers with configurable thresholds (min_score, min_margin_usd, min_margin_pct)
  - Offer pipeline (pending/accepted/declined/expired) with sibling-cancel on accept + 30-min expiry
  - Autopilot tick — sweeps aggregator feed, dedupes against last-2hr offers, fires offers, all logged for ML training
  - KPI dashboard (accept rate, avg time-to-book, margin captured, offers/hr)
  - Twilio SMS + Resend email are MOCKED per user choice — production JSON shape preserved (sid `SM-mock-…`, id `em-mock-…`)
- **Full ML integration** (`/api/dispatch/ml/*`) — new `/app/backend/routes/dispatch_ml.py`:
  - **Accept classifier**: sklearn GradientBoostingClassifier on 9 features (match_score, margin_usd, margin_pct, rate_delta_per_mile, on_time, damage_rate, days_idle, historical_acceptance, miles) → P(accept)
  - **Rate regressor**: GradientBoostingRegressor trained on accepted offers → suggested $/mi
  - Models persisted to `/app/backend/ml_models/` (accept_clf.joblib, rate_reg.joblib, model_meta.json)
  - Heuristic warm-start (no training required to light up)
  - `POST /predict/{load_id}` — ranks carriers by ML expected value (accept_prob × expected_margin)
  - `POST /explain/{load_id}` — **Claude Sonnet 4.5 rationale** via Emergent LLM key (used_llm=true confirmed in tests)
  - Synthetic training data generator (400 deterministic rows) so the models can train from day one
  - Auto-retrain via `POST /train` — reads live dispatch_offers + synthetic seed
- **Frontend `/dispatch-autopilot`** — new page, **6 tabs**:
  - Live Feed (real-time offer stream with delivery receipts + accept/decline)
  - Carriers (CRUD grid with inline form + demo-fleet seed)
  - Offer Pipeline (kanban Pending → Accepted / Declined / Expired)
  - **ML Console** — new tab with model KPIs, seed/train controls, load selector, ML Predict + "Why?" (Claude explain) — TOP PICK highlighted in emerald
  - Dashboard (KPI HUD)
  - Autopilot Cfg (thresholds + toggle switches)
- **Sidebar nav entry** added → "Dispatch Autopilot" (Rocket icon)
- **Dependencies added**: scikit-learn 1.9.0, scipy 1.17.1, joblib 1.5.3, threadpoolctl 3.6.0



## Iter 53 — 2026-07-03 · Aggregator margin $ + Samsara telematics + Mapbox/OSRM routing

**Status**: ✅ Tested 100% backend (11/11 pytest) + 100% frontend flows (iter_53.json)

- **Load Aggregator — margin dollar visibility** (`/app/backend/routes/load_aggregator.py`, `/app/frontend/src/pages/BrokerageAggregatorTab.jsx`):
  - `_normalize()` now guarantees every load row exposes `margin_usd` and `margin_pct` (uses `forecast_margin_usd` when available, otherwise derives from `rate_usd - carrier_pay_usd`).
  - `/api/aggregator/feed` response now includes a `margin_summary` object: `total_margin_usd`, `avg_margin_usd`, `avg_margin_pct`, `high_margin_count` (>=18% loads).
  - New sort_by options: `margin_usd`, `margin_pct`.
  - Feed table adds a **Margin** column between Rate and RPM. $ shown color-coded (green ≥18%, amber ≥12%, red <12%). Small % below in mono grey.
  - 4-tile summary strip renders directly above the table.
  - BookLoadDialog updated to display live `margin_usd` + `margin_pct` from the aggregator row (fallback to derived calc for older payloads).
- **Routing service (Mapbox → OSRM → estimate fallback)** — new file `/app/backend/routes/routing_svc.py`:
  - Endpoints: `POST /api/routing/route`, `POST /api/routing/geocode`, `GET /api/routing/provider`, `GET /api/routing/recent`.
  - Provider order: Mapbox Directions (if `MAPBOX_TOKEN` env), then public OSRM (`router.project-osrm.org`), then a haversine × 1.20 detour × 55 mph estimate as ultra-fallback.
  - Geocoding: Mapbox → OSM Nominatim (public).
  - Every request persists to `route_lookups` for audit/reuse.
- **Telematics service (Samsara live → sample fallback)** — new file `/app/backend/routes/telematics.py`:
  - Endpoints: `GET /api/telematics/provider|vehicles|vehicles/locations|drivers/hos|safety/events` + `POST /api/telematics/connect` (admin-only, rotates env token in-process and stores last4 in `telematics_credentials`).
  - When `SAMSARA_API_TOKEN` is set, calls hit `https://api.samsara.com` with Bearer auth. Absent, endpoints degrade to deterministic synthetic vehicles/HOS/safety events across a real US hub map — same JSON shape either way.
- **Fleet · Routing console** — new page `/app/frontend/src/pages/FleetRouting.jsx` mounted at `/fleet-routing` with 4 sub-tabs:
  - Live Fleet · Route Compute · Safety Events · HOS Logs.
  - Provider banner shows LIVE / CONNECTED · FALLBACK / SAMPLE distinctly (fix from testing agent cosmetic note).
  - Samsara token connector card (admin-only inline) → `POST /telematics/connect`.
  - Route compute card accepts address strings, shows Provider · Distance · Drive Time · Avg Speed tiles.
- **Sidebar nav entry** added just below Live Tracking → "Fleet · Routing" (Satellite icon).
- **New backend test**: `/app/backend/tests/test_iter53_routing_telematics.py` — 11 tests covering all new endpoints + margin fields + sample-mode fallbacks.



## Iter 52 — 2026-07-03 · Broken PDF links fix + Lighthouse Outreach + prior iter 50/51 tests passed

**Status**: 🚧 Test pending for Lighthouse

- **Fixed broken PDF downloads/links** in three tabs:
  - `ShipperIntake.jsx` — was calling `authedDownload("/intake/…", "filename.pdf")`; fixed to `authedDownload("/api/intake/…", { filename })`
  - `Boc3Compliance.jsx` — same bug pattern with `/boc3/…/file`; fixed with `/api/` prefix + options object
  - `International.jsx` — House BL + SLI PDFs; same fix
  - Added `PUBLIC_FRONTEND_URL` to `backend/.env` so `/i/:token` submit URLs resolve to the real preview host instead of the placeholder `orisei.example.com`
- **Lighthouse Outreach module** — prospect→customer funnel for TMS BUYERS:
  - Backend `/app/backend/routes/lighthouse.py` — six-stage lifecycle (curious → engaged → demo_scheduled → trial → won | lost), 6 Orisei-branded collateral kinds (product tour, ROI calculator, spec sheet, case study, security brief, 30-day onboarding map). Endpoints:
    - Auth: `/lighthouse/dashboard`, `/prospects` (CRUD), `/prospects/{id}/stage`, `/prospects/{id}/touch`, `/assets/catalog`, `/assets/{kind}.pdf`
    - **Public (no auth):** `/lighthouse/public/tour` (payload for landing page), `/lighthouse/public/interest` (form submit → creates CURIOUS prospect + touch)
  - Frontend `/lighthouse-outreach` — 4 tabs: Command Deck (5-KPI strip + funnel bars), Prospects (CRUD + detail with stage mover + touch log + send-collateral grid that auto-logs downloads as touches), Collateral (previews), Public Landing (share `/tour` link)
  - Public frontend `/tour` — professional landing page with hero, value pillars, module catalog, interest form (submits without auth, lands as CURIOUS prospect)
- **Prior iterations validated** (iter 50 + iter 51 both passed via testing_agent_v3_fork): Aggregator Book button + workflow/tracking sync, Shipper Relations CRM, Claims Master, QBR Studio all green.


## Iter 49 — 2026-06-28 · BOC-3 compliance + Shipper Intake / Onboarding / Check-Call HUD frontends

**Status**: ✅ Tested 100% backend (12/12 pytest) + 100% frontend (testing_agent iteration_49) — one duplicate-import bug auto-fixed by testing agent

- **BOC-3 Compliance module** (competes with Oversize Permits Inc,
  ComplianceIQ, Iron Bow):
  - Backend `/app/backend/routes/boc3_compliance.py` — 51 US jurisdictions
    (50 states + DC), 7 statuses (PENDING_FILE / FILED / ACCEPTED /
    REJECTED / EXPIRED / RENEWAL_DUE / VOID). Endpoints:
    `/boc3/states`, `/filings` (upsert per state), `/filings/{id}/status`
    (advance + rejection reason + history), `/filings/{id}` DELETE (void),
    `/calendar` (24-month grid grouped by expiry), `/alerts` (RED ≤30d,
    YELLOW ≤60d, EXPIRED), `/coverage` (percent of 51 jurisdictions),
    `/filings/{id}/upload` + `/file` (GridFS bucket `boc3_docs`). Auto-
    computes `days_to_expiry` + `alert` on every list.
  - Frontend `/boc3-compliance` — 3 tabs: **Coverage Map** (51-state grid
    with colored status pills + days-to-renew), **Renewal Calendar**
    (24-month grid, YELLOW/RED/EXPIRED cells per state), **Alerts**
    (grouped by severity). Filing dialog with agent details, blanket
    toggle, cert PDF upload/download, status + rejection reason.
- **Shipper Intake frontend**:
  - `/shipper-intake` admin page — list/create/email/copy-link, download
    branded PDF template.
  - Public `/i/:token` route (NOT behind auth) — branded hero, 4-section
    form (Shipper/Pickup/Delivery/Freight), submit creates a
    `pending_review` booking in the broker's Workflow inbox.
- **Onboarding Checklist frontend** `/onboarding-checklist` — 25 items
  across 6 groups (Legal, FMCSA Authority, Insurance, Tools, API Keys,
  Ops). Click-to-toggle, priority badges (P0/P1/P2), progress bar,
  deep-link to resource URLs + env_var hints for API keys.
- **Check-Call HUD** — `<CheckCallHud>` component injected into
  `/workflow`. 7-step lifecycle rail (DISPATCHED → AT_SHIPPER → LOADED →
  IN_TRANSIT → AT_RECEIVER → UNLOADED → DELIVERED · + EXCEPTION), compose
  form (status, location, miles remaining, ETA, driver, notes),
  auto-updates the booking's `transit_status` on POST.

(Sidebar entries added: `nav-shipper-intake`, `nav-boc3`, `nav-onboarding`,
plus the existing `nav-international`. Routes registered in `App.js` — the
public `/i/:token` route sits outside the `ProtectedRoute` wrapper.)

## Iter 48 — 2026-06-28 · Export/Import documentation suite + AES ITN capture

**Status**: ✅ Tested 100% backend (18/18 pytest) + 100% frontend (testing_agent iteration_48)

- New backend module `/app/backend/routes/intl_documents.py` attaches onto
  the existing `/api/international/*` router via
  `attach_intl_documents_router()`. 16 doc types · 6 statuses · 3 sources.
- **10 branded PDF generators** (all heraldic-styled via
  `build_branded_markdown_pdf`):
  AES Filing Worksheet · Commercial Invoice · Packing List · Certificate of
  Origin · Phytosanitary Application (USDA Form 572) · Letter of Credit
  (UCP 600) · Shipper's Export Declaration · ISF-10 · CBP 7501 Entry
  Summary prep · Customs Broker Cover Letter. Each PDF ~428 KB, visually
  verified Orisei-branded.
- **AES ITN capture**: `POST /container-bookings/{id}/aes/filing` stores
  the ITN on the booking and auto-creates an `ITN_RECEIPT` tracker entry.
  Includes a 20-field AES help cheat sheet (`GET /aes/help`) + 12-field
  Phytosanitary cheat sheet (`GET /phyto/help`).
- **Document tracker** per container: list / record / upload (GridFS
  bucket `intl_docs`) / download / status-update / delete. Soft-delete
  cleans up orphan GridFS chunks. Each tracker entry stores doc_type,
  status, source (INTERNAL_GEN/EXTERNAL_UPLOAD/PARTNER_PORTAL),
  reference number (ITN/Phyto cert#/LC#), counterparty, filed_with_agency,
  filed_at, expires_at.
- New frontend `<DocumentsDrawer>` opens from each container booking row
  via the "Docs ({count})" button. Surfaces: AES ITN capture form (with
  AESDirect deep-link), 10 one-click PDF generators, external file upload
  with type/ref/counterparty/agency fields, and a live tracker list with
  status dropdowns + delete.

(Prior iterations retained below — see CHANGELOG.md history.)

---

## Iter 47 — 2026-06-28 · International (Ocean + Intermodal Rail) module

**Status**: ✅ Tested 100% backend (16/16 pytest) + 100% frontend (testing_agent_v3_fork iteration_47)

- New backend module `/app/backend/routes/international.py` (~620 lines)
  mounted at `/api/international/*`. Reference data:
  20 ocean carriers (Maersk MAEU, MSC, CMA CGM, Hapag-Lloyd, ONE,
  Evergreen, COSCO, OOCL, HMM, Yang Ming, ZIM, PIL, Wan Hai, T.S. Lines,
  Matson, APL, Hamburg Süd, Safmarine, Antillean, SeaLand) ·
  12 rail carriers (BNSF, UP, NS, CSXT, CN, CPKC + regionals) ·
  46 intermodal rail yards across every Class-I network ·
  12 ISO container types (20DC/40DC/40HC/45HC/RF/HR/OT/FR/TK).
- Full ocean lifecycle: **BOOKED → GATE_IN_ORIGIN → ON_VESSEL → DISCHARGED
  → AT_RAIL_RAMP → OUTGATED → DELIVERED → EMPTY_RETURNED** with
  `status_history` audit trail.
- Container booking CRUD + gate event log (auto-advances status on
  ingate/outgate) + rail waybill attachment endpoint.
- Branded **House BL** + **SLI** (Shipper's Letter of Instruction) PDFs
  via `build_branded_markdown_pdf` — same heraldic gold border + ◆ section
  headers + azure/gold label-value tables as the inland BOL. Auto-archived
  to doc_vault with `doc_type='HOUSE_BL'` / `'SLI'`.
- New frontend page `/international` (4 tabs · Container Bookings · Ocean
  Carriers · Rail Yards · Gate Events). Sidebar entry "International ·
  Ocean/Rail" added.

## Iter 46 — 2026-06-28 · Branded PDFs (everywhere) + NMFC expansion + Tennant wipe + auto-route to /workflow

**Status**: ✅ Tested

- **PDF branding** (recurring complaint, now resolved): All non-BOL doc
  types (COMMERCIAL_INVOICE, PACKING_SLIP, WEIGHT_CERT, COO, generic)
  now flow through `build_branded_markdown_pdf` via the new
  `_doc_to_branded_markdown` helper in `server.py`. They share the
  heraldic gold border, ◆ diamond section headers, azure/gold label-value
  boxed tables, and gold-banner Totals previously only on the BOL. Verified
  visually via `analyze_file_tool` (Orisei branding confirmed, no Tennant
  artifacts, High sophistication).
- **NMFC catalog**: Replaced `TENNANT_NMFC_CODES` (20 entries, scrubber-
  specific) with `GENERIC_NMFC_CODES` (82 entries across 17 categories —
  Food & Beverage, Apparel & Textiles, Electronics, Pharmaceuticals,
  Furniture, Building & Construction, Metals, Machinery, Hazmat
  Class 3/8/9, Automotive, Paper & Print, Consumables, FAK catch-all).
- **Tennant wipe**: 30+ files updated. Login page, About, RoutingGuide,
  Documents, TradeCompliance, ServerRegistry, S4Link, CompanyTheme,
  branding.py, server.py FastAPI title and emails. Default brand_id
  changed from "tennant" to "orisei-freight". CSS theme renamed.
- **Auto-route to Workflow on book**: After `POST /brokerage/loads/book`
  succeeds, frontend now navigates to `/workflow?booked_id=BK-xxx`.
  `WorkflowChecklist` reads `?booked_id=` via `useSearchParams` and
  pre-selects the booking.

## Iter 45 — 2026-06-28 · Carrier directory + autocomplete app-wide

**Status**: ✅ Tested

- **Backend**: Two new rich endpoints — `/api/autocomplete/carriers/directory`
  (returns name + SCAC + MC# + DOT# + contact_email + contact_phone +
  use_count + source) and `/api/autocomplete/customers/directory`
  (returns name + payment_terms + AP email + credit limit). Merged from
  brokerage_bookings + rate_confirmations + curated big-board list.
- **Frontend**: New `<CarrierCombobox>` and `<CustomerCombobox>` smart
  pickers with dropdown showing rich metadata. Wired into:
  Brokerage Book Load dialog (auto-fills MC# on carrier select),
  Orisei Operations Rate Confirmations form, Invoice dialog, BookLoad
  page (carrier + commodity autocomplete), Quote form (cities + equipment
  + commodity autocomplete).
- The PDF branding upgrade also landed in this iteration:
  `build_branded_markdown_pdf` now renders `## H2` as ◆ section headers,
  coalesces `- **Label**: value` bullets into branded shipment-meta
  boxed tables, and renders `## Total ...` as gold-banner callouts.

---

(Earlier iterations 38–44 documented in main PRD.md until this file
exists. Going forward, append new iteration blocks at the top of this
file.)

## 2026-06 (fork) · Hot Shot TMS SaaS package complete (iter68)
- `/hotshot` landing moved BEHIND login (user choice "b") — ProtectedRoute, no Layout chrome.
- Landing page expanded into a full capability showcase: animated live-stats strip,
  "Value in the first 7 days" timeline (5 day cards), FULL CAPABILITY MAP (5 categories ×
  28 module cards: AI Suite / Live Operations / Money & Back Office / Paperwork & Compliance /
  Intelligence & Reporting), Operational Sandbox spotlight with sample month P&L,
  3 founder-rate pricing tiers ($390/$975/$2,600), lead-capture demo form.
- One-pager PDF enriched: sandbox, KPI intelligence, Dispatch Autopilot, money-on-autopilot lines.
- CRITICAL FIX: Sidebar.jsx used the Zap lucide icon (Hot Shot nav item, added by prior fork)
  WITHOUT importing it — top-level NAV array evaluation threw "Zap is not defined" and crashed
  the ENTIRE frontend bundle. Added Zap to the lucide import; every logged-in page restored.
- require_role on /api/hotshot/leads GET + status now explicitly includes "admin".
- Tested: iteration_68.json — 9/9 backend pytest + 100% frontend (auth-gating, all landing
  sections, lead→pipeline round trip, status persistence, Zap regression cleared). Test leads purged.

## 2026-06 (fork) · Multi-Tenant White-Label Platform + Solo Arcade + ROI + Demo Video (iter69)
- **Hot Shot TMS Tenant Platform** (`routes/tenant_platform.py`): DATABASE-PER-TENANT isolation
  (`hs_tenant_{slug}` MongoDB dbs). Master endpoints /api/hotshot/tenants/* (provision, list w/
  usage, suspend/activate, delete+drop-db, activity feed). Tenant APIs /api/t/{slug}/*: JWT auth
  (bcrypt + HS_JWT_SECRET, 12h tokens, brute-force 5-strike lockout keyed slug:email), roles
  admin/dispatcher/viewer, team CRUD, branding (logo b64 + colors), loads/carriers/invoices CRUD,
  dashboard KPIs, help guide. Public uptime probe /api/hotshot/status (UptimeRobot-ready).
- **Stripe billing** (Flow A claimable sandbox, SMP tax mode w/ auto-fallback): catalog via
  setup_stripe.py (hotshot_starter/growth/dwy_monthly at $390/$975/$2600), checkout per tenant,
  /api/payments/status/{id} poll flips tenant billing to active, webhook /api/stripe/webhook.
  Env: STRIPE_* + HS_JWT_SECRET added to backend/.env.
- **Frontend**: /tenant-command (Orisei admin: provision, MRR, health, suspend, activity feed);
  tenant portal /t/{slug}/login + /t/{slug}/app/{tab} — branded shell (runtime colors/logo),
  Dashboard/Loads/Carriers/Invoices/Team/Settings(branding+billing+password)/Help.
- **Solo Arcade**: 3 canvas games (Freight Runner snake, Load Stacker 2048, Dock Breaker breakout)
  + /api/arcade/solo scores + per-game leaderboards. New "Solo Arcade" tab in /arcade.
- **ROI calculator** on /hotshot landing (sliders → monthly value + ROI multiple vs $975 tier).
- **Demo video**: chunked upload (4MB chunks → GridFS hotshot_media) from /hotshot-sales, Range-
  supported streaming /api/hotshot/demo-video, auto-plays in landing demo box when uploaded.
- Post-test fixes: brute-force ident no longer uses client IP (k8s pod rotation); dispatcher
  hitting admin-only tab URLs redirects to /app; /t/* added to public route prefixes (401 noise).
- Tested: iteration_69.json — 29/30 backend, 100% frontend incl. full Stripe checkout with 4242
  card, cross-tenant isolation, suspend/reactivate, role gating. Both post-fixes self-verified.
- Demo tenant: acme-freight-co (admin@acmefreight.com / AcmeDemo123!) — in test_credentials.md.

## 2026-06 (fork) · Welcome Email + Self-Serve Signup + Tenant PDFs (iter70)
- Welcome email on provisioning (branded HTML, queues to db.tenant_emails as queued_no_resend
  when Resend key missing); POST /api/hotshot/signup — PUBLIC self-serve trial (honeypot +
  3/hr/IP limit) auto-provisions growth-trial tenant, returns JWT, lands user in their portal.
- Landing page: "Start free trial" section (hs-trial-section). Branded PDFs: GET
  /t/{slug}/loads/{id}/ratecon.pdf + /t/{slug}/invoices/{id}/pdf (routes/tenant_pdfs.py,
  tenant colors/logo). Download buttons in TenantLoads/TenantInvoices.
- Fixes: brute-force ident slug:email (no IP), dispatcher redirect off admin tabs, /t added to
  public route prefixes. INCIDENT: importing routes outside dotenv regenerated
  CONNECTIONS_ENCRYPTION_KEY into .env (duplicate line) — removed duplicate, original preserved.
- Tested iteration_70.json: 17/17 backend, frontend 100%.

## 2026-06 (fork) · Platform Readiness + Prospect Hit List + View-as-Client (iter71)
- routes/readiness.py: POST /api/hotshot/readiness/run — deep functional flow (provision
  throwaway tenant → auth → load → PDFs → branding → team/role gates → Stripe session →
  teardown, 20 checks) + live probes of 27 landing-page modules (route introspection via
  request.app.routes since /openapi.json 500s app-wide). Metrics: score, pass rate, avg/p95
  latency, slowest check, verdict READY_TO_SELL. History in db.readiness_runs.
  Current: score 100, 47/47 checks, ~4s runtime. UI: /platform-readiness (Recharts trend).
- Prospect hit list (routes/hotshot.py): 12 SAMPLE small-broker prospects seeded, CRUD +
  status pipeline + personalized cold-email drafts (copy/mailto). UI card on /hotshot-sales.
- Impersonation: POST /api/hotshot/tenants/{slug}/impersonate (2h token, imp claim) — Eye
  button in Tenant Command opens client portal with purple CLIENT VIEW banner.
- Tested iteration_71.json: 14/14 backend, frontend 100%, zero issues.
- KNOWN COSMETIC (3x recurring, unfixed): 4-6 401 console errors on tenant portal first load.

## 2026-06 (fork) · Readiness PDF Report + Nightly Watchdog (self-tested)
- GET /api/hotshot/readiness/report.pdf — 3-page branded Verification Report (verdict banner,
  score, metric tiles, category bars, "what this proves", full check log). PDF button on
  /platform-readiness (blob download). Layout verified via extraction — no overflow.
- Nightly self-test: start_nightly loop (server startup task) runs full suite daily at 08:00 UTC
  via temp system session in db.user_sessions (deleted after). Below sell-ready → alert in
  db.readiness_alerts + activity log + email (queued w/o Resend key). Endpoints: GET /nightly
  (next run, last nightly, open alerts), POST /alerts/{id}/ack. UI: watchdog card + red alerts
  card w/ acknowledge. Runs now tagged trigger=manual|nightly.
- Self-tested: PDF 200 (11KB, %PDF), system-session run READY_TO_SELL 100, alert seed→ack flow,
  UI screenshot (PDF download works, watchdog shows next run).

## 2026-07-27 (fork session)
- RESTORED corrupted server.py from git (2,723 lines recovered) — backend bootable again
- Wired NMFC expanded db (163 codes), Weigh Stations + Lane Notes (/api/reference/*), Niche Cargo AI (/api/niche-cargo/*), QBR Exec Summary PDF
- Full shipper/consignee addresses on shipments → BOL data → branded PDF
- Weekly KPI digest background scheduler started (Mon 07:00-08:00 CT auto-run)
- Sample Data Wiper with category checkboxes (9 categories) in Admin Settings
- CarrierCombobox rolled out to Claims, COI, Dispatch Autopilot, Aggregator, Carrier Invites, Brokerage driver form
- Fixed autocomplete carriers/directory 500 (None carrier name)
- "Degraded" health resolved (was fallout from crashed backend); sentinel shows ok
- Operation Sandbox: carrier utilization model (per-carrier truck capacity, full carriers skip matching, ≥50% utilized quote premium, utilization panel + network-wide %) and detailed overhead cost stack (13 lines + fleet insurance + truck payments, all in net margin, reconciles to the penny)
- NEW: Carrier Relationship Network (/carrier-network) — 4-category pipeline (owner-ops, regional overflow, specialty, backhaulers), stage tracking, discovery Q&A, capacity-window board, pitch scripts, live scoreboard vs "realistic play" (loads/mo + gross projections, referral unlock). Seeded 16 Twin Cities prospects (is_sample)
- Testing: iteration_81.json — backend 13/13 pass, frontend 95%; all 3 minor issues fixed
- NEW: Live Competitive Scorecard — /api/competitive/scorecard auto-scores Automation, Margin Visibility, Carrier Match, Integration Breadth from actually-connected integrations in /connections; head-to-head table vs McLeod/Alvys/Tai/Rose Rocket/Ascend, revenue impact projection, and score-unlock gap list. Default tab on /competitive-tms.
- NEW: Carrier Lane Rate Cards (/api/carrier-rate-cards + Rate Cards tab on /carrier-network) — pre-negotiated flat or per-mile carrier costs per lane/equipment with expiry & committed weekly capacity. WIRED INTO FIRST STRIKE: contracted lanes bid off real carrier cost with a hard min-margin floor, margin-killers auto-skipped, contracted lanes strike first, and won loads auto-book to the contracted carrier (verified e2e in the live loop: bid $2,475 vs $2,050 contract = locked 17.2% margin, booking carried Schneider + MC + contract cost).
