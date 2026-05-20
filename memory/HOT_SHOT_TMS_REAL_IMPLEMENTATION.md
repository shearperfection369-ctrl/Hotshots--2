# What "Real Implementation" Actually Looks Like
**An honest answer to: "Is Hot Shot TMS really plug-and-play?"**

---

## TL;DR

**Yes — and no.** Three different things get conflated under "plug-and-play":

| Layer | "Plug-and-play" claim | Truth |
|---|---|---|
| **Demo (re-theme + connect)** | 60 seconds | **TRUE.** Demonstrably real. |
| **Vanilla SaaS deploy** | 5 days | **TRUE** for shippers with clean data and basic ERP. |
| **Real enterprise rollout** | "Plug and play" | **PARTIALLY FALSE.** Still 3–8 weeks of services work. |

The wedge is real. The wedge is also not the whole sale. Be precise in
your pitch and you'll close more deals — overpromise and you'll burn
references.

---

## What IS Genuinely Plug-and-Play (the wedge — own this)

1. **The Connection layer.** Paste API key + endpoint into the Connections
   Vault, hit Test Connection → green light. Encrypted at rest with Fernet.
   This is real and unique. **2 clicks.**
2. **The Brand layer.** Type a company name → Claude Sonnet writes the
   brand profile → entire app reskins (colors, sample data, document
   headers, ERP context defaults). **60 seconds.** Real.
3. **The pre-wired integrations.** DAT, Truckstop, Convoy, Uber Freight,
   123Loadboard, Triumph, Apex, OTR, Resend, QuickBooks, RMIS, Carrier411,
   FMCSA, Tivly — all already coded. **No engineering for the customer.**
4. **Pre-built document templates.** BOLs, PODs, compliance forms render
   in < 800ms with the active brand's logo, palette, and footer. **No
   custom dev needed for paperwork.**
5. **Auth, RBAC, audit log.** Already production-grade. No customer
   configuration required.

This is the genuine moat. Lead with it.

---

## What is NOT Plug-and-Play (the gap — name it before they do)

These are services hours, not product gaps. But they're real, and every
mid-market buyer has lived through a botched enterprise rollout — they
will sniff out a glossy claim instantly.

### 1. Data Migration (1–2 weeks)
- **Reality**: Customer's existing shipments live in Excel, an old TMS,
  or their ERP. Real shippers have 50K–500K historical rows.
- **What's needed**: ETL scripts to pull → clean → map → load.
- **What Hot Shot has today**: Excel/CSV upload for materials and yard.
  No turn-key SAP/Oracle historical sync yet.
- **Honest fix**: Build a "Data Migration Wizard" page in Q2 that handles
  the top 5 source systems with one-click mapping templates.

### 2. Master Data Mapping (3–5 days)
- **Reality**: Customer's material codes ≠ your material codes. Their
  carrier IDs ≠ FMCSA MC numbers. Their facility codes ≠ your location
  IDs. Their suppliers ≠ your suppliers list.
- **What's needed**: A one-time mapping table linking customer's keys to
  the canonical Hot Shot schema.
- **What Hot Shot has today**: Manual entry via the admin UI.
- **Honest fix**: Add a "Mapping Studio" — paste two CSVs side-by-side,
  auto-match by name + fuzzy logic, save the translation table.

### 3. Custom Fields (2–4 days)
- **Reality**: Every shipper has 3–7 fields specific to their business —
  project code, customer PO format, internal cost center, contract reference.
- **What's needed**: A schema-extension system without forking the app.
- **What Hot Shot has today**: Hard-coded shipment schema.
- **Honest fix**: Add a "Custom Fields" admin page in Q3 — define field,
  data type, on-which-page, save → renders dynamically in the UI.

### 4. User Provisioning & SSO (3–5 days)
- **Reality**: Customer has 30–100 users. They want SSO via Okta, Azure
  AD, or Google Workspace. They have role hierarchies tied to their HRIS.
- **What's needed**: SAML / OIDC SSO + SCIM auto-provisioning.
- **What Hot Shot has today**: Username/password + role-based access.
- **Honest fix**: Add Okta + Azure AD + Google Workspace SSO in Q2.
  SCIM SCIM auto-provisioning in Q4.

### 5. Workflow Customization (1–2 weeks)
- **Reality**: Their BOL-approval flow has 3 steps. Yours has 1. Their
  freight-bill audit has a manager sign-off; you don't.
- **What's needed**: A no-code workflow builder, or services hours to fork.
- **What Hot Shot has today**: One workflow per module, hard-coded.
- **Honest fix**: Ship a workflow-step toggle UI in Q3. Full workflow
  builder is a Series A scope.

### 6. Reporting & KPI Customization (3–5 days)
- **Reality**: Their CFO wants a specific cut — cost-per-mile by lane by
  carrier by month. Their ops VP wants tender-accept-rate by carrier vs.
  industry average.
- **What's needed**: A dashboard builder, or hard-coded custom reports.
- **What Hot Shot has today**: 45-metric scorecard + 8 core dashboards.
- **Honest fix**: Add a Looker-style report builder. Series A scope, or
  partner with Sigma / ThoughtSpot.

### 7. Integration Edge Cases (3–7 days)
- **Reality**: Even with pre-wired connectors, the customer's SAP instance
  has 7 customizations the connector doesn't know about — custom IDoc types,
  modified BAPI signatures, non-standard partner functions.
- **What's needed**: 3–7 days of integration QA + remediation.
- **What Hot Shot has today**: Vanilla SAP connector + Custom REST fallback.
- **Honest fix**: Ship a "Connector Diagnostic" page that runs the
  customer's actual API and flags schema deviations.

### 8. Training & Change Management (1–2 weeks)
- **Reality**: Dispatcher Sarah has been booking loads in Excel for 8 years.
  Getting her to switch is not a technical problem — it's behavioral.
- **What's needed**: 2-day power-user training, 4-hour end-user sessions,
  written runbooks, video library, dedicated CS rep for first 30 days.
- **What Hot Shot has today**: Embedded help text + brand-aware user manual.
- **Honest fix**: Hire a Customer Success engineer post-raise (already in
  the $1.5M budget). Build a Loom-style video library.

### 9. Go-Live Cutover (1 week dual-run + 1 week stabilization)
- **Reality**: No competent buyer flips the switch on day 1. They run
  old + new in parallel for 1–4 weeks, reconcile daily, then formal
  cutover with executive sign-off.
- **What's needed**: A "shadow mode" feature where Hot Shot ingests
  shipments from the old system, generates outputs, but doesn't dispatch.
- **What Hot Shot has today**: No shadow mode.
- **Honest fix**: Build shadow mode in Q3. It also doubles as a free-trial
  feature for prospects.

---

## What This Actually Costs (Per Logo)

| Phase | Days | Who does it | Honest billing |
|---|---|---|---|
| Demo + qualify | 1 | Founder | Free |
| Discovery + scoping call | 1 | Founder | Free |
| Connections vault setup | 0.5 | Customer IT + Founder | Free (in license) |
| Data migration | 5–10 | Hot Shot CS | Services bill: $15K–$30K |
| Master data mapping | 3–5 | Customer ops + CS | Services bill: $7.5K–$15K |
| Workflow + custom fields | 5–10 | Customer ops + CS | Services bill: $15K–$30K |
| SSO + user provisioning | 3–5 | Customer IT + CS | Services bill: $7.5K–$15K |
| Training + change mgmt | 5–10 | Hot Shot CS + customer | Services bill: $15K–$30K |
| Go-live + stabilization | 5–10 | Hot Shot CS | Services bill: $15K–$30K |
| **TOTAL** | **27–60 days** | | **$75K–$150K services revenue per logo** |

**This is GOOD news**, not bad news. Services bill = additional revenue.
Industry standard for TMS implementations is **30–50% of license value
in services**. Hot Shot is in line.

---

## How to Talk About This to Investors

**Wrong**: "It's plug-and-play. Customers go live in 5 days."
*VC reaction: "I've heard this 100 times. What's the real number?"*

**Right**: "60 seconds to a fully-skinned live demo on the prospect's
business. 5 days to a vanilla SaaS deploy with one ERP and one load
board. 4–8 weeks to a full enterprise rollout with data migration, SSO,
workflow customization, and change management — same as everyone else,
except our 60-second demo means we win the deal in 3 weeks instead of
9 months."

**The wedge is sales-cycle compression, not implementation compression.**
That's still a 10x improvement. Just don't claim more than you can deliver.

---

## How to Talk About This to Customers

Lead with what's plug-and-play (Connections, branding, integrations,
documents). Be transparent about what isn't (their data, their workflow,
their users). Quote services hours upfront. **No one ever lost a deal
by being honest about implementation timeline; thousands of deals have
been lost by overpromising it.**

---

*Built by Oliver Cummins · Plymouth, Minnesota*
*Confidential. For internal Hot Shot TMS use.*
