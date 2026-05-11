# Tennant Companies — TMS HUD Dashboard
**Project**: Transportation Management System for Tennant Companies (Minnesota HQ, Holland MI, Louisville KY)
**Version**: v1.4
**Date**: 2026-05-11

## Original Problem Statement
Build a transportation management app tailored for Tennant Companies of Minnesota (industrial floor scrubbers/cleaners). Parts imported via Kuehne+Nagel. Manufacturing facilities: Louisville KY, Holland MI, Golden Valley MN. HUD-style command center showing all shipping modes. Integrate with Microsoft Suite, SharePoint, S/4HANA SAP, PowerBI, Logix, ArcBest, Fastfrate, UPS, FedEx, DHL, R&L, XPO, SAIA, Kuehne+Nagel, Outlook. Live feeds: weather, traffic, news. 250 users. Book loads, generate BOL/CI/Packing slip/Weight cert/COO. DOT sites & ACE portal. HS code lookup. Trailer size graphs. Container tracking. Team chat. KPI reporting. Real-time map.

**Added incrementally in session**:
- Freight Audit & Pay with accessorials
- Carrier Onboarding & Vetting
- Quick carrier toggle
- Driver Mobile Check-In (auth-free)
- PDF rendering for all 5 document types (ReportLab)
- RBAC: admin / auditor / dispatcher / driver
- SAP S/4HANA OData connector (Sales Orders, Purchase Orders, sync logs)
- Cisco Webex integration (Spaces, Meetings, Notify, Schedule)
- HUDLINK AI Co-Pilot (Claude Sonnet 4.5 via emergentintegrations)
- Promotional video page (Sora 2 — generation triggered, blocked by budget cap; page renders with content)
- Workbook module — 13 Excel-style renameable tabs mirroring Tennant's legacy XLSX, single-tab and full-workbook Excel export

## Architecture
- **Backend**: FastAPI + MongoDB (motor) + WebSockets + ReportLab + openpyxl + emergentintegrations
- **Auth**: Emergent-managed Google OAuth + RBAC; first user auto-promoted to admin
- **Frontend**: React 19 + Tailwind + Shadcn UI + Recharts + Leaflet
- **AI**: Claude Sonnet 4.5 (text) + Sora 2 (video, requires budget top-up)
- **Real APIs**: Open-Meteo weather, OpenStreetMap tiles
- **Theme**: HUD dark (#0B0E14) + cyan (#00E5FF), JetBrains Mono / Chivo

## User Personas & RBAC
- **admin** — Full access: user management, integrations config, freight ops, carrier decisions
- **auditor** — Freight bill approve/pay/dispute, view all reports & shipments
- **dispatcher** — Book loads, manage shipments, generate documents, SAP sync, chat (DEFAULT)
- **driver** — Mobile check-in only (auth-free deep link `/driver/SHP-XXXX`)

## 19 Pages
1. `/login` Google sign-in
2. `/dashboard` Command Center — live map, KPIs, weather, traffic, news, mode mix, manifest
3. `/workbook` 13 renameable tabs (Outbound TL/LTL, Expedites, Crate Spots, Seafreight 25M, 25 Import, 25 Quotes, Plant Hubs, IN Primary Carrier, IN Supplier Contacts, IN Carrier Contacts, Info, Volume Overview) + Excel export
4. `/ai-assistant` HUDLINK Claude Sonnet 4.5 co-pilot
5. `/shipments` table + carrier-toggle pills
6. `/book-load` create new shipment
7. `/tracking` live map + container search
8. `/driver-console` share driver mobile links + activity stream
9. `/freight-pay` bills audit, approve/pay/dispute (auditor)
10. `/carrier-onboarding` vetting pipeline (admin decides)
11. `/documents` 5 doc types with PDF download
12. `/hs-lookup` 18 Tennant HS codes
13. `/trailers` 8 trailer specs with visual scale + charts
14. `/integrations` 14 connectors (admin)
15. `/sap-sync` SAP S/4HANA OData mock — SO, PO, sync logs (admin/dispatcher)
16. `/webex` Cisco Webex — Spaces (7), Meetings (4), notify/schedule
17. `/reports` KPI charts + carrier scorecard
18. `/chat` Real-time WebSocket chat (7 channels)
19. `/links` External resources (DOT, ACE, USTR, FAA, etc.)
20. `/promo` Tennant launch promo (video + feature/tech walkthrough for Kirk Juergins)
21. `/admin/users` Role management (admin)
22. `/driver` / `/driver/:id` Mobile check-in (auth-free)

## Testing Status
- **iteration_1.json**: 37/37 passing (initial MVP)
- **iteration_2.json**: 64/64 passing — covers iter 2 (PDF, RBAC, SAP), iter 3 (AI, Webex), iter 4 (Workbook)
- Zero critical issues across both reports

## What's Pending / Known Limits
- **Sora 2 video**: generation completed but download blocked by Emergent key budget — top up to retrieve. Script: `python /app/scripts/generate_promo_video.py`
- **server.py is 1962 lines** — recommend modularizing into routers/* for next major refactor (per testing agent code review)
- **Real carrier/SAP APIs**: all mocked with realistic data; production deployment will need OAuth credentials for each
- **PDF rendering**: ReportLab-based; functional but could be enhanced with custom letterheads / barcodes / QR codes for BOLs

## Next Action Items
- Top up Emergent LLM key budget → re-run video generation
- Wire real SAP S/4HANA OAuth + OData credentials when available
- Real carrier API integrations (UPS/FedEx/DHL OAuth first)
- Modularize backend into routers for maintainability
- Add PWA manifest so Driver Mobile can be installed on iOS/Android home screens

## Mocked vs Real
**REAL**: PDF generation (ReportLab), Excel export (openpyxl), Weather (Open-Meteo), Map tiles (OSM), Auth (Emergent Google), AI text (Claude Sonnet 4.5), WebSocket chat, Workbook CRUD, RBAC enforcement, MongoDB persistence
**MOCKED**: SAP S/4HANA, Cisco Webex, UPS, FedEx, DHL, XPO, SAIA, ArcBest, R&L, Fastfrate, Logix, Kuehne+Nagel, SharePoint, PowerBI, Outlook, Industry news, Traffic alerts, Quotes data, Supplier/Carrier contacts
