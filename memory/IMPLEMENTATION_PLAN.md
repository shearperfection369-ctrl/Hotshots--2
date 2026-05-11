# Tennant Companies TMS — Technical Implementation Plan
**Document version:** 1.0 · February 2026
**Author:** Tennant TMS engineering · prepared for Kirk & the Tennant transportation team
**Scope:** Roll the cyber-HUD TMS from a working preview build into a production system used daily by the full 250-user Tennant transportation organization across Golden Valley, Holland, and Louisville.

---

## 1 · Executive Summary

The TMS is built and feature-complete on preview at
`https://clean-logistics-dash.preview.emergentagent.com` and snapshotted to production at
`https://clean-logistics-dash.emergent.host`. This document describes how we take it from a working snapshot
into the day-to-day source of truth for Tennant's transportation operations — covering identity,
integrations, data migration, user onboarding, run-the-business support, and the change-management cadence.

**The build covers, today:** 250-user RBAC · Live multi-mode shipment tracking (TL · LTL · Parcel · Ocean ·
Air · Rail) · Document store with BOL amendment audit-trail · Workbook spreadsheet view · Trade Compliance
(Incoterms 2020, Section 301/232, Tariff, ACE/Broker, FTAs) · Supplier sourcing · Freight Claims · Vault
(GridFS) · Carrier Rates · Carrier portal · Equipment / Yard upload + analytics · Machines catalog (35
models, 12 categories) · 7 visual themes · Arcade · Internal messaging · AI co-pilot (Claude 4.5).

---

## 2 · Production Architecture

```
                    ┌────────────────────────────────────────────────┐
                    │           Tennant SSO  (Google Workspace)       │
                    └──────────────────────┬─────────────────────────┘
                                           │ OAuth (Emergent-managed)
                    ┌──────────────────────▼─────────────────────────┐
                    │     TMS Frontend  ·  React 19 / Tailwind / CDN  │
                    └────────────┬────────────────────────┬──────────┘
                                 │ REST + WebSocket (chat)│
                    ┌────────────▼─────────────┐   ┌──────▼────────────┐
                    │  TMS Backend  · FastAPI  │   │  Static assets    │
                    │  /api/* (RBAC, audit)    │   │  promo.mp4 etc.   │
                    └─┬───────┬───────┬────────┘   └───────────────────┘
                      │       │       │
                      │       │       └──► Claude Sonnet 4.5 (Universal Key)
                      │       │
                      │       └─────────────► SAP S/4HANA  (OData / RFC)
                      │                       SharePoint   (Graph API)
                      │                       PowerBI      (REST refresh)
                      │
              ┌───────▼─────────┐
              │  MongoDB Atlas  │   ←  shipments, claims, documents,
              │  + GridFS bucket│       carriers, suppliers, audit log,
              │  (vault, BOLs)  │       equipment_reports, leaderboards
              └─────────────────┘
```

### 2.1 Environment matrix

| Tier | URL | Purpose | DB | Auto-deploy |
|------|-----|---------|----|----|
| Preview / Dev | clean-logistics-dash.preview.emergentagent.com | Daily engineering | dev cluster | yes (every change) |
| **Production** | clean-logistics-dash.emergent.host | 250-user live | prod cluster (separate) | manual ("Save to GitHub" → redeploy from Emergent dashboard) |
| Staging (future) | TBD | UAT, parallel SAP sandbox | staging cluster | promoted from Preview |

### 2.2 Infrastructure ownership

| Layer | Owner | Vendor | Runbook |
|---|---|---|---|
| Frontend hosting | Emergent | Emergent CDN | redeploy via Emergent dashboard |
| Backend hosting | Emergent | Emergent compute | supervisor restart for env changes |
| Database | Tennant IT + Emergent | MongoDB Atlas (M30 dedicated) | Atlas console |
| File storage | Tennant IT | MongoDB GridFS inside Atlas | indexed `vault.files` & `carrier_bols.files` |
| LLM | Emergent Universal Key | Anthropic + Google | budget monitored monthly |
| SAP S/4HANA | Tennant IT | SAP BTP | service account `TMS_SVC` |
| SSO | Tennant IT | Google Workspace (existing tenant) | OAuth client owned by `it-platforms@tennantco.com` |

---

## 3 · Identity, Roles, and the 250-User Plan

### 3.1 Sign-in flow

1. User browses `https://clean-logistics-dash.emergent.host`.
2. They click **Sign in with Google** — Emergent-managed OAuth pops the standard `accounts.google.com` consent.
3. Backend `/api/auth/session` validates the token, **idempotently** upserts the user record, and applies the role from `ADMIN_EMAILS` allow-list (already wired in `server.py`).
4. Session lives in MongoDB `user_sessions` with a 7-day TTL.

### 3.2 Role matrix (5 roles)

| Role | Count est. | What they see |
|------|------------|---------------|
| `admin` | 5–8 | Everything · user mgmt · carrier invites · settings |
| `auditor` | 6 | Read-most + audit log + claims approval + freight payments |
| `dispatcher` | ~40 | Book Load · Shipments CRUD · Documents · Workbook · Equipment |
| `driver` | ~120 | Driver Console only (mobile-friendly, mark-on-site, photo-POD) |
| `carrier` | ~80 (external) | Scoped portal: only their own shipments, rate card, invoices |

### 3.3 Onboarding the 250 users

- **Allow-list seeding** — populate `backend/.env` `ADMIN_EMAILS` with the 5–8 admin emails before launch (one is already in: `shearperfection369@gmail.com`).
- **First-time auto-provision** — any other Tennant Google account that signs in is created as `dispatcher` by default. Admin can promote/demote via the Admin · Users page.
- **Carrier accounts** — invited via the existing Carrier Invites flow (token-based onboarding email) with scoped read access.
- **Driver accounts** — bulk-imported from SAP HR via a one-off script (`/app/scripts/seed_drivers.py`) reading the SAP RFC `BAPI_USER_GETLIST`.

---

## 4 · Integration Plan (per system)

### 4.1 SAP S/4HANA  · phase 1 (week 2–4)

Today the SAP widgets show realistic synthetic data. Production needs a live read-only mirror first, then write-back.

| Object | OData service | Direction | TMS endpoint |
|---|---|---|---|
| Sales Orders | `API_SALES_ORDER_SRV` | SAP → TMS (pull every 5 min) | `GET /api/sap/sales-orders` |
| Outbound Deliveries | `API_OUTBOUND_DELIVERY_SRV` | SAP → TMS | `GET /api/sap/deliveries` |
| Purchase Orders | `API_PURCHASEORDER_PROCESS_SRV` | SAP → TMS | `GET /api/sap/purchase-orders` |
| Material Master | `API_PRODUCT_SRV` | SAP → TMS (cached daily) | `GET /api/sap/materials` |
| POD / Delivery confirmation | `API_OUTBOUND_DELIVERY_SRV` | TMS → SAP (write) | triggered on `PUT /api/shipments/{id}` when status=`delivered` |

**Authentication:** OAuth 2.0 client-credentials, service user `TMS_SVC`. Secret stored in `backend/.env` as `SAP_CLIENT_ID` / `SAP_CLIENT_SECRET`. Token refreshed automatically.

**Failure mode:** if SAP is unreachable for >15 min, dashboards show a yellow banner ("SAP feed delayed — last sync HH:MM"), and writes are queued in `pending_sap_writes` collection for retry.

### 4.2 SharePoint  · phase 2 (week 4–6)

Yard reports, COIs, routing guides, and customer onboarding packets live in two SharePoint libraries.

- **Yard report nightly ingest** — Azure-AD app-only token → Graph API → download newest .xlsx in
  `Transportation/Yard/Daily` → POST to `/api/equipment/upload` automatically every night at 02:00 CT.
  Replaces today's manual upload. Stale-trailer alerts auto-DM the dispatcher Teams channel via webhook.
- **Document mirror** — anything dropped in `Transportation/COIs` flows into the Vault GridFS bucket
  tagged `coi`; lifecycle managed in Vault (expiry warnings 60 days out).

### 4.3 PowerBI · phase 2 (week 4–6)

- TMS pushes the KPI snapshot (`GET /api/kpis`) into a PowerBI streaming dataset every 5 min.
- Existing PowerBI dashboards for the executive review continue to refresh against that dataset.
- New "TMS Workbook" PowerBI page sources directly from the Mongo `shipments` view via the Atlas
  PowerBI connector (read-replica, no perf impact on TMS).

### 4.4 Carriers · phase 1 (week 1–3)

Today the Carrier Portal is fully built. Production rollout:

1. Send onboarding packet (existing `POST /api/carriers/{id}/onboarding-email`) to the top 25 carriers Tennant uses (Averitt, Estes, R&L, Saia, XPO, Holland, Dayton, Premier, Challenger, Meisler, Copeland, UPS, FedEx, DHL, + container lines).
2. Carrier logs in via tokenized link, sees ONLY their lanes.
3. Carrier uploads BOL / invoice / POD per shipment → already wired to GridFS.
4. Phase 1b: EDI 204/214/210 integration via an EDI VAN (TrueCommerce or Cleo) → out of MVP scope; documented as Phase 3.

### 4.5 Trade compliance · phase 2 (week 5–7)

- Customs broker (UPS_SCS) — daily entry-summary CSV drop into SharePoint, mirrored into the
  `customs_entries` Mongo collection. Trade Compliance page reflects live numbers.
- HTS tariff updates — daily scrape of `hts.usitc.gov` via the existing job at `/app/backend/jobs/hts_update.py`
  (run as a cron in production via a `scheduler.py` background task).

### 4.6 Communications · phase 3 (week 8+)

- **Resend or SendGrid** — replace today's `mailto:` builders with real outbound email so dispatchers can
  hit "Send" once and the email leaves the building. Document amend-notifications also go through
  this channel.
- **Twilio SMS** — driver pickup/delivery reminders (`POST /api/driver-console/notify`).
- **Webex** — already mocked; production hook into the Webex Teams API for the chat module.

---

## 5 · Data Migration

| Source | Object | Volume | Method | Owner |
|---|---|---|---|---|
| SAP S/4HANA | open Sales Orders | ~600 | one-shot OData export → `import_orders.py` | SAP team |
| SAP S/4HANA | open Outbound Deliveries | ~250 | one-shot OData → `import_deliveries.py` | SAP team |
| Existing Excel BOL log | historical BOLs | ~12,000 since 2024 | `import_bol_archive.py` reads .xlsx + .pdf attachments, lands in GridFS + `documents` collection | TMS team |
| Legacy carrier list | carriers, MSAs, COIs | ~80 carriers | `import_carriers.py` | TMS team + sourcing |
| TMS user list | from Google Workspace | 250 | first-login auto-provision + bulk role assignment | IT + TMS admin |
| Yard reports | last 90 days | ~90 files | reuse `equipment_module.parse_yard_xlsx` in batch | TMS admin |

All migration scripts live in `/app/backend/scripts/migrations/` and emit a JSON report (rows imported,
rows skipped with reason) for sign-off.

---

## 6 · Security, Compliance, Observability

### 6.1 Security
- All traffic HTTPS, TLS 1.3 (terminated by Emergent CDN).
- Backend never trusts a session token from the URL; cookies are `httpOnly`, `Secure`, `SameSite=None`.
- RBAC enforced on every write endpoint via `require_role()` decorator (already present).
- Secrets only in `backend/.env`, never in code. Production secrets rotated quarterly.
- GridFS file uploads scanned by ClamAV in a pre-write hook (phase 2).

### 6.2 Audit log
- Every `POST` / `PUT` / `PATCH` / `DELETE` already logs to `audit_log` collection (`user`, `endpoint`, `payload`, `ts`). Retention 7 years for trade-compliance and freight-payment integrity.

### 6.3 Backups
- MongoDB Atlas continuous backup, 7-day point-in-time restore.
- Monthly snapshot exported to Tennant's encrypted S3 bucket.
- GridFS buckets included in the same backup plan.

### 6.4 Observability
- Backend logs → supervisor file → forwarded to Datadog (Tennant tenant).
- Frontend errors → Sentry with `release` = current git SHA.
- Uptime monitored via Pingdom (preview + production), 1-min interval, paged to on-call admin.

---

## 7 · Rollout Plan — 12 Weeks

| Phase | Weeks | Goals | Exit gate |
|---|---|---|---|
| **0 · Hardening** | 1 | Penetration test, accessibility audit (WCAG 2.1 AA), load test (250 concurrent users) | Pen-test PASS, p95 latency < 500 ms |
| **1 · Internal pilot** | 2–4 | 5 admins + 10 dispatchers in Golden Valley use TMS in PARALLEL with current spreadsheet workflow. SAP read-only feeds live | Dispatcher NPS ≥ 8, zero data-loss incidents |
| **2 · Holland & Louisville** | 5–6 | Roll dispatcher seats to all 3 sites. PowerBI + SharePoint integrations live | All shipments booked through TMS for 14 consecutive days |
| **3 · Drivers + Carriers** | 7–8 | Driver Console mobile launch, top-25 carriers in their portal | Driver POD upload rate ≥ 95 % |
| **4 · Cutover** | 9 | Decommission legacy spreadsheet. SAP write-back enabled. | 1 week of clean operations |
| **5 · Hyper-care** | 10–12 | Daily standups, bug triage SLA 4 h, refinements | Backlog of P0 issues = 0 |
| **6 · Optimization** | 13+ | Resend/SendGrid email, EDI VAN, AMR-fleet telemetry, X-series ROVR integration | Quarterly review |

---

## 8 · Training & Change Management

### 8.1 Training assets (already in-app)
- **User Manual** — 59-slide PPTX (`/api/manual/download`) + in-app live viewer at `/manual`.
- **Promo Video** — 28-second branded cinematic at `/promo`, plays even on locked-down corporate networks.
- **HUDLINK AI Co-pilot** — Claude 4.5-powered assistant Tennant employees ask questions to (e.g., "What's the HS code for a T16AMR?").

### 8.2 Training schedule

| Audience | Format | Duration | Cadence |
|---|---|---|---|
| Admins | Live + recorded | 90 min × 2 sessions | weeks 1–2 |
| Dispatchers (40) | Live, by site | 2 hrs | weeks 2–3 |
| Auditors | Live | 90 min | week 3 |
| Drivers (120) | Self-serve video + 15-min QR-code mobile demo | 30 min | weeks 6–7 |
| Carriers (80) | Self-serve PDF + onboarding email | 20 min | weeks 7–8 |

### 8.3 Support model

- **Tier 1** — TMS admin in Golden Valley (Slack / Teams `#tms-help` + 24-hr SLA)
- **Tier 2** — Tennant IT (escalation for SSO, network, SharePoint)
- **Tier 3** — Emergent engineering (platform / deployment / DB)

---

## 9 · Cost & Capacity

| Line item | Monthly | Notes |
|---|---|---|
| Emergent platform (compute + CDN + LLM key) | ~$1,800 | 250-user tier |
| MongoDB Atlas M30 + 1 read-replica | $720 | with daily backup |
| Anthropic Claude usage (HUDLINK) | $200–$400 | 250 users × ~30 turns/mo |
| Pingdom / Sentry / Datadog | $250 | shared Tennant tenants |
| Twilio SMS (phase 3) | $120 | 5,000 driver msgs/mo |
| **Subtotal** | **~$3,100–$3,300** | excludes existing SAP/SharePoint/PowerBI |

Load test target: 250 concurrent + 50 carrier-portal sessions, p95 < 500 ms on key endpoints.

---

## 10 · Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SAP service-account auth changes | M | H | Wrap SAP client in a single module with health-probe; on-call paged |
| Tennant corporate network blocks third-party content | H | M | Self-host promo.mp4 ✓ done; provide "Open in YouTube" fallback ✓ done |
| User adoption resistance from spreadsheet veterans | H | M | Parallel run for 3 weeks before cutover; Workbook view feels like Excel |
| BOL / customs error rate climbs | L | H | Audit trail + amendment workflow + Vault retention ✓ done |
| LLM cost spikes | L | M | Universal Key budget caps + monthly review; turn off auto-suggest if needed |
| Production deployment lag | M | L | "Save to GitHub" + Emergent redeploy ≈ 5-min window, low-risk |

---

## 11 · Open Items / Phase 3 Backlog

- Resend / SendGrid migration (real outbound email)
- EDI VAN connection (204 / 214 / 210)
- Twilio SMS for driver notifications
- AMR fleet telemetry (X4 / X6 / X16 ROVR + T7AMR / T16AMR ingestion into the Equipment module)
- Per-user dashboard layouts (currently `localStorage` per browser)
- Mobile native wrapper for the Driver Console (Capacitor / React Native shell)

---

## 12 · Acceptance Criteria — what "done" looks like

- [ ] 250 Tennant users sign in via Google SSO; correct role assigned within 5 sec
- [ ] All 3 sites (Golden Valley · Holland · Louisville) book 100 % of new loads through TMS for 14 consecutive days
- [ ] SAP S/4HANA two-way integration live for SO + Delivery + POD write-back
- [ ] Top 25 carriers active in the carrier portal with 95 %+ POD upload rate
- [ ] Daily yard report ingested automatically from SharePoint at 02:00 CT
- [ ] Trade Compliance + Customs Broker pages reflect real (not synthetic) entry data
- [ ] BOL archive contains ALL active BOLs; amendments fully audit-trailed
- [ ] Audit log retained 7 years; backups verified by quarterly restore drill
- [ ] Pen-test report signed off by Tennant IT security

---

*End of plan. Update via Save to GitHub → land in `/app/memory/IMPLEMENTATION_PLAN.md`.*
