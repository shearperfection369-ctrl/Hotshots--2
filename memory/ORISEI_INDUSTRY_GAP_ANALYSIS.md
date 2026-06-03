# Orisei Freight Solutions · TMS Industry Gap Analysis
**Where you stand vs. SAP TM · Oracle OTM · MercuryGate · McLeod · Trimble · 3Gtms**

Built by Oliver Cummins · Plymouth, Minnesota · Confidential

---

## Executive Summary

You have **70–80% of what the industry leaders have at 1/100th of the cost**.
The remaining 20–30% is what separates a "live production TMS" from a "fundable
SaaS product" — and most of it is implementation discipline, not new features.

**Bottom line**:
- For Orisei (your own brokerage): **production-ready today** for 1–10 customers
  with the gaps below filled in.
- For Hot Shot TMS (the white-label SaaS): **ship gap items 1–6** below before
  a mid-market shipper (>$100M revenue) procurement team will sign.

---

## What You Have That Matches the Industry Leaders

| Capability | You | SAP TM | Oracle OTM | MercuryGate | McLeod |
|---|---|---|---|---|---|
| Load tendering & booking | ✅ | ✅ | ✅ | ✅ | ✅ |
| Auto-match (algo-driven) | ✅ Margin Shield | ⚠️ Manual | ⚠️ Add-on | ✅ | ✅ |
| Multi-source rate snapshot | ✅ DAT+TS+historical | ⚠️ Add-on | ⚠️ Add-on | ✅ | ✅ |
| Compliance traffic-lights | ✅ 5-check | ⚠️ Manual | ⚠️ Add-on | ⚠️ Add-on | ✅ |
| Auto-invoice on POD | ✅ idempotent | ✅ | ✅ | ✅ | ✅ |
| Brand-aware documents | ✅ | ❌ | ❌ | ⚠️ | ❌ |
| 60-second re-skinning | ✅ **UNIQUE** | ❌ | ❌ | ❌ | ❌ |
| 9 ERP connectors | ✅ | ✅ (native SAP only) | ✅ (native Oracle) | ⚠️ | ⚠️ |
| 14 launch-day integrations | ✅ pre-wired | ⚠️ partners | ⚠️ partners | ✅ | ✅ |
| Carrier scorecard (45 metric) | ✅ | ⚠️ basic | ✅ | ✅ | ✅ |
| Live tracking (multi-modal) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lane analytics + CPM | ✅ Ops KPIs | ✅ | ✅ | ✅ | ✅ |
| AI co-pilot | ✅ Claude 4.5 | ⚠️ Joule | ⚠️ Oracle AI | ❌ | ❌ |
| White-label / re-theming | ✅ **UNIQUE** | ❌ | ❌ | ⚠️ limited | ❌ |
| Re-deploys in days, not months | ✅ | ❌ 6-18mo | ❌ 6-18mo | ⚠️ 3-6mo | ⚠️ 2-4mo |

**You match or beat them on 12 of 14 capabilities.** The unique columns
(60-sec re-skinning, white-label, days-to-deploy) are the wedge.

---

## What You're Missing · The Honest 11

### 1. Real-Time GPS Tracking (not just driver check-ins) — P0
- **Industry baseline**: project44, FourKites, MacroPoint — automatic
  GPS pings from carrier ELDs every 5–15 min, no driver action required.
- **You have**: driver check-in app (manual), tracking URLs for parcel.
- **Gap**: For TL/LTL, shippers expect to see the truck on a map *without*
  the driver lifting a finger.
- **Fix**: Integrate project44 or FourKites (~$0.30–$0.80 per shipment,
  metered). MacroPoint is cheaper but less coverage. **Build effort**:
  1 week to wire the API + render on existing tracking map. Cost: monthly
  metered.

### 2. EDI Connectivity (204/210/214/990) — P0
- **Industry baseline**: Every Fortune 1000 shipper sends loads as
  EDI 204 (tender) and expects 990 (accept), 214 (status), 210 (invoice).
- **You have**: REST APIs only.
- **Gap**: You can't onboard a single major shipper without EDI. This is
  the #1 reason mid-market TMS pilots stall.
- **Fix**: Integrate with **SPS Commerce** or **TrueCommerce** as your EDI
  VAN. They translate EDI ↔ your REST. ~$1K-$3K/mo + per-document fees.
  **Build effort**: 2-3 weeks for the first 4 doc types. Cost: $36K/yr.

### 3. Spot vs. Contract Rate Logic — P0
- **Industry baseline**: Shippers have **contract rates** (annual lane
  agreements with primary carriers) and fall back to **spot** for overflow.
  TMS distinguishes them and routes loads accordingly.
- **You have**: One unified rate snapshot.
- **Gap**: Without contract management, you can't onboard a shipper that
  has 50+ lane agreements (which is every $100M+ shipper).
- **Fix**: Build `routes/contract_rates.py`: upload lane × carrier × rate
  table, prioritize contract carriers in Auto-Match, log spot vs. contract
  on every booking. **Build effort**: 1 week.

### 4. Accessorial Charge Library — P1
- **Industry baseline**: 50+ accessorial codes (detention, layover, lumper,
  TONU, fuel surcharge, hazmat fee, residential delivery, after-hours,
  liftgate, weekend delivery, etc.) auto-apply per tariff.
- **You have**: Manual accessorial entry on invoice.
- **Gap**: This is where carriers nickel-and-dime your margin. Without
  pre-defined accessorial library, billing leaks 2–5%.
- **Fix**: Add an accessorial catalog (you have ~10 already from compliance
  forms), wire to invoice generation. **Build effort**: 4 days.

### 5. SSO + SCIM Provisioning — P0 for enterprise
- **Industry baseline**: Okta, Azure AD, Google Workspace integration is
  table-stakes for any customer with > 30 users.
- **You have**: Username/password + session tokens.
- **Gap**: Tennant's IT security team will not approve a system that
  doesn't talk to their identity provider.
- **Fix**: WorkOS or Auth0 (~$200/mo at startup tier). SAML SSO ships in
  2-3 days; SCIM auto-provisioning is another week.

### 6. SOC 2 Type I Report — P0 for enterprise
- Covered in the separate compliance memo. Sign with Vanta this week.

### 7. EDI 856 Advance Ship Notice (ASN) — P1
- **Industry baseline**: When a shipment leaves origin, the receiving DC
  expects an ASN with carton-level detail 24-48 hours before arrival.
- **You have**: POD only (after delivery).
- **Gap**: WMS-driven receivers can't process your shipments without ASN.
- **Fix**: Bundled with EDI work (item 2).

### 8. Multi-Currency + Multi-Tax — P2 for US-only, P0 for international
- **Industry baseline**: USD/CAD/MXN/EUR pricing with FX, US sales tax
  + Canadian GST/PST + Mexican IVA + EU VAT.
- **You have**: USD only.
- **Gap**: Blocks any cross-border shipper.
- **Fix**: Stripe Tax + an FX feed for receivables. **Build effort**:
  2 weeks for a clean implementation.

### 9. Customer Self-Service Portal (no login, link-gated) — P1
- **Industry baseline**: Every customer expects to log in, see all their
  loads, click any one for tracking, download POD, see invoices, dispute.
- **You have**: Marketing/intro page only. No customer-side portal.
- **Gap**: You'll get 30+ emails/week per customer asking "where's my load?"
  if you don't ship this.
- **Fix**: Build `/customer-portal/?token=…` that mirrors the Hot Shot
  invite-link pattern. Shows their loads, real-time map, POD download,
  invoice history. **Build effort**: 1 week.

### 10. Carrier Mobile App (or PWA) — P2
- **Industry baseline**: KeepTruckin / Motive / Samsara / Trucker Tools
  have driver-facing apps for check-in, ePOD, signature capture.
- **You have**: Driver check-in page (responsive web).
- **Gap**: Drivers are on phones in cabs. They want a real app.
- **Fix**: Wrap your existing `/driver` route in a PWA manifest (add to
  home screen, offline-capable). **Build effort**: 2 days. Native app =
  Series A.

### 11. Dock Scheduling / Yard Management — P3
- **Industry baseline**: C3 Solutions, Open Dock, Project44 Dock.
- **You have**: Yard map upload (Excel).
- **Gap**: Larger shippers want dock appointments to prevent yard chaos.
- **Fix**: Series A. Until then, send appointment requests via email
  with a Calendly link.

---

## Production-Readiness Checklist (Real Business Use)

For Orisei Freight Solutions to operate as a fully-running brokerage today:

### Must-Have (do these in next 30 days)
- [ ] **MC authority active** — file FMCSA Form OP-1, $300, ~21 days.
- [ ] **Surety bond ($75K)** — Coverwallet, Lance Surety, Pacific Surety.
- [ ] **General + cargo + contingent liability insurance** — Tivly,
      Reliance Partners, GreatHorn (~$8K-$15K/yr).
- [ ] **Operating agreement + carrier broker contract template** — your
      lawyer reviews; you already have the form skeleton in
      `/forms/master-bcsa`.
- [ ] **W-9 + EIN** — register with IRS, takes 1 day online.
- [ ] **Business bank account** — Mercury, Chase Business Complete.
- [ ] **EDI VAN account** — SPS Commerce or TrueCommerce (item 2 above).
- [ ] **Factoring agreement** — Triumph Financial, Apex Capital, or OTR
      Capital. 1-3% per load. Already wired into Connections Vault.
- [ ] **QuickBooks Online subscription** — $30/mo, already integrated.
- [ ] **DAT One subscription** — $149/mo for the most basic broker tier.
- [ ] **Truckstop subscription** — $49/mo for the broker basic.
- [ ] **Carrier411 subscription** — $59/mo, vetting + monitoring.
- [ ] **Resend email account** — already wired, $20/mo for 50K emails.
- [ ] **Domain + business email** — oriseifreight.com + Google Workspace.

### Should-Have (do these in next 60 days)
- [ ] **Real-time GPS tracking** — project44 starter plan (~$2K/mo).
- [ ] **Spot vs. contract rate management** — item 3 above, you build.
- [ ] **Customer self-service portal** — item 9 above, you build.
- [ ] **First named reference customer signed** — Tennant 90-day pilot
      (see 90-day GTM playbook).
- [ ] **SOC 2 Type I in audit** — Vanta + Prescient Assurance.

### Nice-to-Have (do these in next 90 days)
- [ ] **Accessorial charge library** — item 4 above.
- [ ] **SSO via WorkOS** — item 5 above.
- [ ] **Carrier PWA** — item 10 above.
- [ ] **Weekly customer auto-digest email** — wires existing Ops KPI
      endpoint into a Monday-morning Resend cron.

---

## How Your TMS Compares on Efficiency

| Metric | Industry leader | Hot Shot TMS | Advantage |
|---|---|---|---|
| Time from contract sign → live in production | 4–18 months | 5–30 days | **20–50× faster** |
| Re-theme for a new tenant | Not supported | 60 seconds | **Unique** |
| Implementation team needed | 3–6 FTE | 0–1 FTE | **3–6× cheaper** |
| Annual license cost (mid-market) | $250K–$1M | $80K–$240K | **3–4× cheaper** |
| Integration time (first ERP) | 6–12 weeks | 2 hours | **100× faster** |
| Mobile-first UX | ⚠️ Add-on apps | ✅ Native responsive | Comparable |
| AI features | Mostly hype | Claude 4.5 in production | Better |

---

## How Your TMS Compares on Ease of Use

| User type | Industry leader | Hot Shot TMS |
|---|---|---|
| **Dispatcher** | 2-week training, dense Java UIs | 1-hour training, intuitive React |
| **Customer ops** | Often no portal, email-driven | Portal pending (item 9) |
| **Carrier driver** | Manual app login per ELD | Token-gated PWA pending (item 10) |
| **Shipper procurement** | Quarterly business reviews via PowerPoint | Weekly auto-digest pending |
| **CFO** | Custom reports via Excel exports | Ops KPI dashboard live today |
| **IT admin** | 6-mo deployment project | 2-click Connections Vault |

**Where you win**: dispatchers and IT admins onboard 10× faster.

**Where you tie**: drivers — current responsive web is on par with most.

**Where you're behind**: customer-facing self-service. Item 9 fixes it.

---

## Strategic Recommendation

### Stop building features. Start signing logos.

You have **more than enough product** to land your first 5 customers.
Every hour spent on item 8 (multi-currency) or item 11 (dock scheduling)
is an hour NOT spent calling Tennant.

**Real priority order for the next 60 days**:

1. ✅ **Sign Tennant or one comparable MN industrial** — 60-day pilot,
   50% discount, full case-study rights.
2. ✅ **Ship items 1, 2, 3, 9** — these are the four "no" answers procurement
   gives you for #2 through #50.
3. ✅ **Start SOC 2 with Vanta** — runs in parallel, takes founder time but
   not engineering time.
4. 🟡 **Defer items 4, 5, 7, 8, 10, 11** until you have a customer asking
   for them in writing.

The fastest way to know what to build next is to have a paying customer
tell you. Don't speculate.

---

*Confidential. For Hot Shot TMS / Orisei Freight Solutions strategy use.*
*Last updated: June 2026 · Oliver Cummins · Plymouth, MN*
