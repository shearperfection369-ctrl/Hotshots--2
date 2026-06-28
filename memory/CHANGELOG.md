# Orisei Freight Solutions TMS · `/app/memory/CHANGELOG.md`

> Append-only changelog. Each session writes new entries at the **top**.

---

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
