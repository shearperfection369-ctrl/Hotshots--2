# Orisei Freight Solutions TMS · `/app/memory/CHANGELOG.md`

> Append-only changelog. Each session writes new entries at the **top**.

---

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
