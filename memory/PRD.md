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

## Pending / Backlog (P2)
- Promo Video file regeneration via Sora 2 (BUDGET-BLOCKED — user must top-up the Universal Key first; script ready at `/app/scripts/generate_promo_video.py`)
- Production deployment health checks
- SharePoint / PowerBI deeper visual integrations
- Additional games (Tic-Tac-Toe, Chess) in the Arcade

## Known Mocks
- Email delivery — mailto: links + copy-to-clipboard (no Resend/SendGrid wired by user choice)
- SAP S/4HANA endpoints (`/api/sap/*`) — curated Tennant-relevant mock data
- Machine catalog images — public Unsplash CDN URLs (replaceable with Tennant product DAM)
- Customs broker, news feeds — mocked
