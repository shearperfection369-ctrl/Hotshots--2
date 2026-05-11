# Tennant Companies — TMS HUD Dashboard
**Project**: Transportation Management System for Tennant Companies (Minnesota HQ, Holland MI, Louisville KY)
**Version**: v1.0 MVP
**Date**: 2026-05-11

## Original Problem Statement
Build a transportation management app tailored for Tennant Companies of Minnesota (industrial floor scrubbers/cleaners). Parts imported via Kuehne+Nagel. Manufacturing facilities: Louisville KY, Holland MI, Golden Valley MN. HUD-style command center showing all shipping modes. Integrate with Microsoft Suite, SharePoint, S/4HANA SAP, PowerBI, Logix, ArcBest, Fastfrate, UPS, FedEx, DHL, R&L, XPO, SAIA, Kuehne+Nagel, Outlook. Live feeds: weather, traffic, news. 250 users. Book loads, generate BOL/CI/Packing slip/Weight cert/COO. Direct links to DOT sites & ACE portal. HS code lookup. Trailer size graphs. Container tracking. Team chat. KPI reporting. Real-time map. **Added in session**: Freight audit & pay with accessorials, carrier onboarding & vetting, quick carrier toggle, driver mobile check-in.

## User Personas
1. **Dispatcher** — books loads, manages shipments, generates BOL/COI
2. **Freight Auditor** — reviews freight bills, approves/disputes/pays
3. **Compliance** — vets carriers, manages onboarding pipeline
4. **Plant Operations** — monitors inbound K+N containers, plant-specific channels
5. **Driver** — uses mobile check-in (auth-free via deep link)
6. **Executive** — KPI reports & carrier scorecards

## Architecture
- **Backend**: FastAPI + MongoDB (motor) + WebSockets for chat
- **Auth**: Emergent-managed Google OAuth (session_token cookie, 7-day expiry)
- **Frontend**: React 19 + Tailwind + Shadcn UI + Recharts + Leaflet
- **Real APIs**: Open-Meteo (weather, no key), OpenStreetMap tiles
- **Theme**: HUD dark mode — #0B0E14 bg, cyan #00E5FF accents, JetBrains Mono data font, Chivo display font

## What's Been Implemented (2026-05-11)
### Backend (all /api/* routes, 37/37 tests passing)
- Auth: /auth/session, /auth/me, /auth/logout
- Shipments: list/get/create with mode/status/carrier filters; auto-seed 48
- Documents: BOL, Commercial Invoice, Packing Slip, Weight Cert, COO
- KPIs: totals, by_mode, by_carrier scorecards, 14-day trend
- Live feeds: real Open-Meteo weather, mocked news + traffic
- Integrations: 14 mocked carrier/enterprise integration statuses
- Trailers: 8 trailer specs with capacity & use cases
- HS Lookup: 18 Tennant-relevant HS codes
- Quick Links: DOT, ACE Portal, USTR HTS, FAA, etc.
- Chat: REST + WebSocket /ws/chat with 7 channels (general, ops-dispatch, import-export, carrier-issues, louisville, holland, golden-valley)
- **Freight Bills**: list, summary, approve/pay/dispute with accessorial tracking
- **Carrier Onboarding**: vetting form (MC/DOT/SCAC/CSA/safety/insurance), W-9/COI/contract tracking, approve/reject
- **Driver Mobile**: auth-free /driver/checkin, /driver/shipment/{id} — updates shipment status, GPS, progress

### Frontend (15 pages)
1. /login — Google sign-in, HUD aesthetic with Tennant imagery
2. /dashboard — Command Center: live map, KPIs (7), news ticker, weather (3 facilities), traffic alerts, mode donut, 14-day trend, recent manifest
3. /shipments — full table + **carrier quick-toggle pills** + mode/status filters
4. /book-load — booking form with facility origin selection
5. /tracking — full-screen map + ocean container search
6. /documents — 5 document types, generate dialog, archive
7. /hs-lookup — search 18 codes by code/description/category
8. /trailers — proportional length visual + capacity bar charts
9. /integrations — 14 integrations grouped by category
10. /reports — KPI dashboard with line/radar/bar charts, carrier scorecard table
11. /chat — real-time WebSocket chat with 7 channels
12. /links — DOT/ACE/USTR external resources
13. /freight-pay — bills table with carrier toggle, approve/pay/dispute
14. /carrier-onboarding — vetting pipeline, W-9/COI toggles, approve/reject
15. /driver-console — share mobile links, live check-in feed
16. /driver (auth-free) — mobile-optimized check-in: GPS, fuel%, odometer, status

## Tennant Branding
- Recreated iconic blue oval TENNANT® logo as inline SVG (no external dependency)
- User-provided Tennant scrubber imagery integrated on login screen
- Three Tennant facilities mapped: Golden Valley MN, Holland MI, Louisville KY

## P0/P1/P2 Backlog (Next Phases)
### P0 — Production Readiness
- Wire real carrier APIs (UPS/FedEx/DHL OAuth) when keys provided
- SAP S/4HANA OData connector for SO/PO sync
- Role-based access (admin/dispatcher/auditor/driver)
- Audit log for all freight payment actions

### P1 — Enhanced Features
- PDF generation for BOL/COI/Packing using a templating engine
- PowerBI embed via authenticated iframe
- Outlook delegated send for shipment notifications
- SharePoint document drop with metadata sync
- SAML/SSO for 250-user enterprise rollout

### P2 — Nice-to-Have
- Push notifications for driver app via PWA
- Geofencing alerts (auto-status on facility arrival)
- ELD (Electronic Logging Device) integration
- Optimization engine for load consolidation

## Mocked Integrations (Demo-Ready, Production-Pending)
SAP S/4HANA · SharePoint · PowerBI · Outlook · Logix · UPS · FedEx · DHL · ArcBest · Fastfrate · R&L · XPO · SAIA · Kuehne+Nagel
News & traffic feeds also mocked. Weather is REAL via Open-Meteo.
