# Orisei TMS · Cost Analysis · Real-World Operating Cost

**Scope:** Total cost to run the Orisei Freight Solutions TMS / Brokerage Command Deck (the React + FastAPI + MongoDB app you're looking at right now) under three realistic load profiles.
**Currency:** USD · **Year:** 2026 prices · **Last updated:** 2026-02-14

> **TL;DR**
> - **Solo broker (Year 1, Oliver only):** **~$385 / month** infrastructure + **~$1,750 / month** all-in including load boards, accounting, tracking, and compliance subscriptions = **~$2,135 / month ($25.6K / year)**.
> - **Small brokerage (5 seats, ~1,200 loads/yr):** **~$840 / month** infra + **~$3,950 / month** all-in = **~$4,790 / month ($57.5K / year)**.
> - **Multi-tenant white-label (50 tenants, ~25K loads/yr):** **~$4,400 / month** infra + **~$18,500 / month** all-in = **~$22,900 / month ($274K / year)** before LLM overage.
> - **Hardware:** none on-premise required. Cloud-only. Field users need a phone or laptop with a modern browser.

---

## 1 · App Architecture (what we're costing)

| Layer | Technology | Where it runs |
| --- | --- | --- |
| Frontend | React 19 · Vite · Tailwind · Shadcn UI | Static asset host + CDN |
| Backend | FastAPI · Python 3.11 · uvicorn | Container / app platform |
| Database | MongoDB · Motor async driver | Managed MongoDB Atlas |
| File storage | GridFS (BOLs, COIs, MSDS, vault, podcasts) | Inside the MongoDB cluster |
| Background work | None today — all sync/async in-process | n/a |
| AI / LLM | Claude Sonnet 4.5 · Gemini Nano Banana · GPT Image 1 · Sora 2 via **Emergent Universal Key** | External (Emergent gateway) |
| Live data | National Weather Service (free) · DAT / Truckstop / Convoy / Uber Freight / 123Loadboard · QuickBooks Online · Resend · Twilio · Macropoint · RMIS · Stripe | External SaaS APIs |
| Auth | Emergent-managed Google OAuth + cookie sessions | External |
| Logo / colors / sample data | Mongo `company_brand` collection (multi-tenant) | Mongo |

There is **no on-premise component** — no NAS, no physical server, no on-prem ELD relay. Drivers and dispatchers use any modern browser, including iOS Safari and Android Chrome.

---

## 2 · Tier A · Solo Broker (Oliver, Year 1)

### Profile
- 1 active broker user · 1 admin (same person) · 2–3 carrier read-only invites.
- 4 → 16 loads/week ramp. ~480 loads/year.
- ~100 MB document storage Y1 (BOLs, COIs).
- AI usage: occasional brand generation, ~50 HUDLINK conversations/month, 5–10 image gens.

### Recommended hosting topology
- **Emergent native deployment** (single container, autoscale 0→1) OR Railway Hobby
- **MongoDB Atlas M10** (2 GB RAM, 10 GB storage, dedicated, daily backup) — minimum for production
- **Cloudflare** for DNS + CDN + DDoS (free tier)
- **Custom domain** `oriseifreight.com`

### Infrastructure monthly cost — Tier A

| Line item | Provider | Monthly | Annual | Notes |
| --- | --- | ---: | ---: | --- |
| App hosting (FastAPI + static React) | Emergent / Railway / Render | **$25** | $300 | 1 vCPU, 1 GB RAM, autoscale to zero off-hours |
| MongoDB Atlas M10 (dedicated, 2 GB RAM) | Atlas | **$57** | $684 | Includes daily PITR backup, 10 GB storage |
| Atlas backup retention bump (30 days) | Atlas | $5 | $60 | optional |
| Domain + DNS (.com) | Cloudflare / Namecheap | $1.25 | $15 | $12–18/yr ÷ 12 |
| Cloudflare DNS + CDN + WAF | Cloudflare | **$0** | $0 | Free tier covers everything |
| SSL cert | Let's Encrypt via host | $0 | $0 | Auto-renewed |
| Email send (transactional, low volume) | Resend / SendGrid free | $0 | $0 | <3K emails/mo free |
| Uptime monitoring | UptimeRobot free | $0 | $0 | 50 monitors free |
| Error tracking | Sentry free tier | $0 | $0 | 5K events/mo free |
| Object storage (overflow PDFs, video clips) | Cloudflare R2 (10 GB) | $1.50 | $18 | optional — GridFS handles most |
| **Subtotal — Infrastructure** | | **~$90 / mo** | **~$1,077** | |
| Emergent LLM Key (Claude/Gemini/Whisper/Sora) | Emergent Universal Key | **~$25** | $300 | Per-call billing; estimate based on usage profile below |
| **Subtotal — Infra + LLM** | | **~$115 / mo** | **~$1,377** | |

### Third-party SaaS / API subscriptions — Tier A
These are required to **operate the brokerage** (not the app itself), but they plug into the Connections vault you just built.

| Service | Plan | Monthly | Annual | Why |
| --- | --- | ---: | ---: | --- |
| **DAT One** — Power | Power | **$279** | $3,348 | Primary load board |
| **Truckstop** — Premium | Premium | $199 | $2,388 | Secondary board + BookIt Now |
| **Convoy / Uber Freight / 123Loadboard** | Combined | $120 | $1,440 | Digital posting + matching |
| **RMIS** — Carrier vetting | Standard | $100 | $1,200 | Insurance verification + onboarding |
| **Carrier411** | Pro | $60 | $720 | Fraud + double-broker screening |
| **QuickBooks Online** | Plus | $90 | $1,080 | Accounting + invoicing |
| **Macropoint / Project44** | Starter | $150 | $1,800 | ELD-tracking aggregation |
| **HubSpot** (optional CRM) | Starter | $125 | $1,500 | Sales pipeline |
| **Google Workspace** | Business Starter | $18 | $216 | Email, drive, calendar |
| **Twilio SMS** (driver pings) | Pay-as-you-go | $40 | $480 | ~5K SMS at $0.0083 |
| **Stripe** (customer ACH/card) | Pay-as-you-go | $0 + 2.9% | — | Per-transaction; no monthly |
| **OTR Capital factoring** | Pay-per-use | 0–3% | — | Only when used (carrier quick-pay) |
| **BMC-84 surety bond ($75K)** | New entity rate | ~$94 | $1,125 | Year-1 premium 1.5% of bond |
| **Commercial GL + Cargo + E&O package** | Standard | $350 | $4,200 | Required for property broker |
| **Subtotal — SaaS & Compliance** | | **~$1,625 / mo** | **~$19,497** | |

### **Tier A · All-in monthly** = **$115 (infra+LLM) + $1,625 (SaaS) = ~$1,740 / month** = **~$20,880 / year**

### Tier A · Hardware required
| Item | Cost | Notes |
| --- | ---: | --- |
| MacBook Air M3 or business laptop | **$1,099–1,499** one-time | Founder's workstation |
| iPhone 16 Pro (business line) | $999 one-time + ~$95/mo plan | Required for 24/7 on-call |
| Dual 4K monitor (optional) | $500–800 one-time | Two-board comparison workflow |
| **Total upfront hardware** | **~$2,600** | One-time |
| Phone plan + home internet (business) | $190 / mo | $2,280/yr |

---

## 3 · Tier B · Small Brokerage (5 seats, ~100 loads/month)

### Profile
- 5 active users (founder + 2 carrier-sales + 1 ops + 1 AR)
- 80–120 loads/month · ~1,200 loads/year
- 1 GB document storage by year-end
- AI usage: 20× HUDLINK convo/day, ~5 brand generations, ~100 LLM lookups/day
- 2 office locations (HQ + co-working desk)

### Recommended hosting topology
- **Two-container deployment** (frontend + backend) on Emergent Pro / Railway Pro / Render Pro
- **MongoDB Atlas M20** (4 GB RAM, 20 GB storage, dedicated)
- Cloudflare Pro ($20/mo) for higher rate-limits and analytics
- Sentry Team plan ($26/mo) for error tracking

### Infrastructure monthly cost — Tier B

| Line item | Monthly | Annual | Notes |
| --- | ---: | ---: | --- |
| App hosting (2 vCPU, 4 GB RAM, autoscale 1→3) | $80 | $960 | Render Pro / Railway Pro |
| MongoDB Atlas M20 | $158 | $1,896 | 4 GB RAM, includes M20 perf |
| MongoDB Atlas backup (continuous PITR) | $30 | $360 | 7-day PITR window |
| Cloudflare Pro (CDN + WAF) | $20 | $240 | Higher rate limits |
| Sentry Team | $26 | $312 | Error tracking + traces |
| Better Stack uptime + on-call SMS | $29 | $348 | 24/7 incident alerts |
| Domain + SSL | $1.50 | $18 | |
| Cloudflare R2 (50 GB overflow + backups) | $7.50 | $90 | |
| Email send (Resend Pro) | $20 | $240 | 50K emails/mo |
| Logging (Better Stack Logs 50 GB/mo) | $24 | $288 | Optional — host logs cover most |
| **Subtotal — Infrastructure** | **~$396 / mo** | **~$4,752** | |
| Emergent LLM Key — heavier usage | **~$120** | $1,440 | ~$4/day average |
| **Subtotal — Infra + LLM** | **~$516 / mo** | **~$6,192** | |

### Third-party SaaS / API subscriptions — Tier B

| Service | Monthly | Notes |
| --- | ---: | --- |
| DAT One Power (multi-seat) | $479 | 3-seat license |
| Truckstop Premium (2 seats) | $349 | |
| Convoy + Uber Freight + 123Loadboard | $180 | Volume-based |
| RMIS Pro | $200 | Higher carrier volume |
| Carrier411 Pro | $120 | 2 seats |
| QuickBooks Online Advanced | $200 | 5 users + classes |
| Macropoint Pro | $400 | More tracked loads |
| HubSpot Sales Hub Starter | $300 | 3 paid seats |
| Google Workspace (5 seats) | $90 | Business Standard |
| Twilio SMS (heavier use) | $120 | ~14K SMS/mo |
| 1Password Teams (5 seats) | $40 | Secret sharing |
| Slack Pro (5 seats) | $42 | Team comms |
| BMC-84 renewal | $94 | Year-2 rate, same bond |
| Commercial GL + Cargo + E&O | $450 | Higher revenue tier |
| **Subtotal — SaaS & Compliance** | **~$3,064 / mo** | **~$36,768/yr** |

### **Tier B · All-in monthly** = **$516 + $3,064 = ~$3,580 / month** = **~$42,960 / year**

### Tier B · Hardware required
| Item | Quantity | Cost | Notes |
| --- | ---: | ---: | --- |
| MacBook Air / Pro M3 | 5 | $7,500–10,000 | Per seat |
| iPhone (business line) | 5 | $5,000 | + plans $95/mo each = $475/mo |
| Dual 4K monitors | 5 | $3,500 | Each seat |
| Co-working desk (Loring Park MN) | 1 | $400/mo | Or home office stipend |
| Office printer + scanner | 1 | $600 | One-time |
| **Total upfront hardware** | | **~$16,600** | One-time |
| Phone plans + office internet | | **~$575 / mo** | Recurring |

---

## 4 · Tier C · Multi-Tenant White-Label (50 tenants, ~25,000 loads/yr)

### Profile
- 50 tenant brokerages on one shared TMS instance (the design intent of the multi-tenant `company_brand` system).
- ~250 active users across tenants.
- ~25,000 loads brokered/year (mix of small + medium customers).
- ~50 GB document storage in GridFS.
- Heavy AI: each tenant's HUDLINK + brand generation + image gen.
- 99.95% uptime SLA expected.

### Recommended hosting topology
- **3-container backend** behind a load balancer (autoscale 3→12)
- **MongoDB Atlas M40** (16 GB RAM, 80 GB storage, replica set + read replicas)
- **Cloudflare Enterprise** OR Cloudflare Pro + custom CDN rules
- **Dedicated Redis** for rate-limit + session store (optional but recommended)
- **S3 / R2** for cold-storage document archive
- 24/7 on-call rotation with PagerDuty

### Infrastructure monthly cost — Tier C

| Line item | Monthly | Annual | Notes |
| --- | ---: | ---: | --- |
| App hosting (3-12 containers, 4 vCPU/8GB ea.) | $750 | $9,000 | AWS Fargate / GCP Cloud Run / Render Team |
| MongoDB Atlas M40 + read replica | $1,000 | $12,000 | 16 GB RAM, replica set |
| Atlas continuous backup + PITR (35 days) | $200 | $2,400 | |
| Cloudflare Pro + advanced WAF | $200 | $2,400 | |
| Redis (Upstash Pay-as-you-go) | $80 | $960 | Rate limit + session cache |
| S3 / Cloudflare R2 (500 GB cold archive) | $25 | $300 | Document overflow + offsite backup |
| Sentry Business | $80 | $960 | Higher quota |
| Better Stack uptime + logs | $99 | $1,188 | Aggregated logs |
| PagerDuty (5-seat) | $115 | $1,380 | On-call rotation |
| Datadog APM (optional) | $200 | $2,400 | Performance traces |
| GitHub Team + Actions | $40 | $480 | CI/CD |
| Domain + multi-subdomain SSL | $5 | $60 | |
| Resend Pro (200K emails/mo) | $99 | $1,188 | Multi-tenant invoicing |
| **Subtotal — Infrastructure** | **~$2,893 / mo** | **~$34,716** | |
| Emergent LLM Key — heavy multi-tenant | **~$1,500** | $18,000 | Scales linearly with tenants |
| **Subtotal — Infra + LLM** | **~$4,393 / mo** | **~$52,716** | |

### Third-party SaaS / API subscriptions — Tier C
At this scale, you would typically **negotiate enterprise contracts** with DAT, Truckstop, RMIS, etc. Below are list-price estimates.

| Service | Monthly | Notes |
| --- | ---: | --- |
| DAT One Enterprise (negotiated) | $4,500 | 50-tenant pooled license OR per-tenant pass-through |
| Truckstop Enterprise | $3,200 | 50-tenant API access |
| 123Loadboard + Uber Freight + others | $1,500 | Combined |
| RMIS Enterprise | $2,500 | Higher carrier vetting volume |
| Carrier411 Enterprise | $800 | Pooled |
| QuickBooks Online Advanced (pass-through to tenant) | varies | Each tenant pays own QBO |
| Macropoint Enterprise | $2,500 | Higher tracked-load count |
| Twilio (high volume) | $400 | ~50K SMS/mo |
| 1Password Business (25 seats) | $200 | |
| Slack Business+ | $300 | 30 seats |
| Notion Team | $200 | |
| Cumulative E&O + GL umbrella | $1,200 | Enterprise-grade coverage |
| **Subtotal — SaaS & Compliance** | **~$17,300 / mo** | **~$207,600/yr** |

### **Tier C · All-in monthly** = **$4,393 + $17,300 = ~$21,693 / month** = **~$260,316 / year**

> At 50 tenants, **per-tenant blended cost ≈ $434 / month**, well below typical mid-market TMS subscription pricing ($800–2,500 / tenant / month).

### Tier C · Hardware required
- **Founder + ops headquarters:** 25–30 workstations, ~$50,000 one-time, plus standard office hardware (printers, displays, conference rooms).
- **No dedicated server hardware** required — fully cloud.
- **Optional:** Dedicated firewall / SD-WAN if HQ has more than 20 staff: ~$150/mo Meraki MX.

---

## 5 · LLM / AI Cost Modeling (Emergent Universal Key)

The Emergent Universal Key meters all of these centrally. Real cost is **per token / per image / per second of video**, not a flat subscription.

| Model | Use case in this app | Price (Emergent gateway) | Per-call estimate |
| --- | --- | --- | ---: |
| Claude Sonnet 4.5 | Brand generation, HUDLINK chat, AI Assistant tab | ~$3 / 1M input · ~$15 / 1M output tokens | $0.005 / chat turn |
| Gemini 3 Pro | Lower-cost background drafts | ~$1.25 / 1M in · ~$5 / 1M out | $0.002 / call |
| Gemini Nano Banana (image gen) | Brand logos, marketing graphics | ~$0.04 / image | per gen |
| GPT Image 1 | High-fidelity hero images | ~$0.07 / image | per gen |
| Sora 2 (video gen) | Promo video clips | ~$0.30 / second | usually one-off |
| OpenAI Whisper | Audio transcripts (driver voice notes — future) | ~$0.006 / minute | per minute |

**Monthly LLM cost by tier (estimated):**

| Tier | HUDLINK msgs/mo | Brand gens | Images | Video sec | LLM cost / mo |
| --- | ---: | ---: | ---: | ---: | ---: |
| A (solo) | ~1,500 | ~5 | ~10 | 0 | **~$25** |
| B (5-seat) | ~12,000 | ~25 | ~40 | 30 | **~$120** |
| C (50-tenant) | ~150,000 | ~250 | ~500 | 600 | **~$1,500** |

> Auto top-up the Emergent Universal Key in Profile → Universal Key → Add Balance to avoid mid-month interruption.

---

## 6 · Storage & Bandwidth Scaling

### MongoDB document storage growth assumptions
- Avg BOL PDF: **120 KB**
- Avg COI PDF: **180 KB**
- Avg load record + linked docs: **~400 KB**
- Brand logos / videos: **2–5 MB per tenant**

| Tier | Load count | Doc storage Y1 | Atlas storage tier |
| --- | ---: | ---: | --- |
| A | 480 loads | ~250 MB | 10 GB (M10) ✓ |
| B | 1,200 loads | ~1.2 GB | 20 GB (M20) ✓ |
| C | 25,000 loads | ~40 GB | 80 GB (M40) ✓ |

### Egress bandwidth
- Tier A: < 50 GB / mo → free on Cloudflare
- Tier B: ~200 GB / mo → free on Cloudflare
- Tier C: ~2 TB / mo → use Cloudflare R2 + Cloudflare CDN for free egress

---

## 7 · One-Time Setup / Implementation Costs

| Item | Tier A | Tier B | Tier C |
| --- | ---: | ---: | ---: |
| Hardware (laptops, phones, monitors) | $2,600 | $16,600 | $50,000 |
| LLC formation + MC authority + bonds (one-time) | $2,500 | $2,500 | n/a (tenants do own) |
| Legal: master broker/carrier agreement template | $1,800 | $4,000 | $15,000 |
| CPA engagement setup | $1,200 | $3,000 | $20,000 |
| Logo + 1-page site (or use built-in Build-Your-Own theme — $0) | $1,500 | $3,000 | $40,000 (full brand) |
| QuickBooks data migration (if existing books) | — | $1,500 | $25,000 |
| Carrier pre-onboarding (15+ carriers) | $0 | $0 | $0 |
| Staff training | $0 | $2,000 | $25,000 |
| **One-time total** | **~$9,600** | **~$32,600** | **~$175,000** |

---

## 8 · "What if" Scenarios

### A: Stay on Emergent platform vs. self-host on AWS

| Aspect | Emergent Native | AWS Fargate + RDS-Mongo |
| --- | --- | --- |
| Tier B monthly compute | $80 | ~$220 |
| Engineering time to maintain | ~0 h/mo | ~8–16 h/mo |
| Cold-start latency | <1s (warm pool) | 2–5s |
| Multi-region failover | manual today | $$$ to enable |
| Verdict | **Cheaper + faster** through Tier B | Crossover ~ Tier C |

### B: Drop a load board to save cost

| If you drop... | Savings | Risk |
| --- | ---: | --- |
| Truckstop | $199–349/mo | Less coverage on west-coast lanes |
| Convoy / Uber Freight | $120–180/mo | Lose digital instant-book |
| Macropoint | $150–400/mo | Manual driver tracking via SMS only |

### C: Move from Macropoint to driver-text-in via Twilio

- Reduces tracking subscription to ~$40/mo (Twilio only).
- Costs ~30 min/load operational overhead chasing check-ins.
- Only viable at Tier A (solo founder bandwidth).

---

## 9 · Comparison vs. Off-the-Shelf TMS

| Solution | Monthly (5 seats, ~100 loads/mo) | Custom branding | Multi-tenant white-label |
| --- | ---: | --- | --- |
| **Orisei TMS (this app)** | **$3,580 all-in** | ✓ AI Themer (60 seconds) | ✓ Native |
| McLeod LoadMaster | $3,500–6,000 + setup | Limited | No |
| Aljex Web | $1,500–3,000 + setup | Limited | Partial |
| Tai TMS | $1,250–4,500 | Limited | No |
| Turvo | $4,000–8,000 | No | No |
| Build your own from scratch | $250K–800K dev + $3K/mo run | n/a | yes |

> The competitive moat is the **AI Themer**: an Orisei white-label tenant can stand up a new branded TMS instance in **60 seconds**. Tai/McLeod implementations average 4–6 months.

---

## 10 · Summary Table

| Tier | Users | Loads/yr | Infra+LLM | Operating SaaS | All-in monthly | All-in yearly | One-time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **A · Solo** | 1 | 480 | **$115** | $1,625 | **$1,740** | **$20,880** | $9,600 |
| **B · Small** | 5 | 1,200 | **$516** | $3,064 | **$3,580** | **$42,960** | $32,600 |
| **C · 50-tenant** | 250 | 25,000 | **$4,393** | $17,300 | **$21,693** | **$260,316** | $175,000 |

### Cost-per-load (a useful broker metric)

| Tier | All-in monthly | Loads/mo | **Cost / load** |
| --- | ---: | ---: | ---: |
| A | $1,740 | 40 | **$43.50** |
| B | $3,580 | 100 | **$35.80** |
| C | $21,693 | 2,083 | **$10.41** |

> At Tier A, with average $171 gross margin / load, infrastructure consumes **~25%** of margin. By Tier C, infrastructure is **~6%** of margin — the unit economics get dramatically better with scale, which is exactly the white-label thesis.

---

## 11 · Recommendations

1. **Stay on Emergent native deployment** through Tier B. The combination of integrated LLM gateway + autoscale + zero-ops is worth a 2–3× premium over raw AWS.
2. **Use the Connections vault** (already shipped) to onboard each SaaS as Oliver gets contracts — no .env edits, no redeploys.
3. **Defer Macropoint** until ~Mo6 — start with Twilio-driven driver pings to save ~$150/mo at launch.
4. **Negotiate enterprise contracts** for DAT and Truckstop only after hitting 100+ active monthly carriers; pre-Tier-B, public Power and Premium plans are correct.
5. **Cap LLM auto-top-up** at $300/mo via the Universal Key dashboard until tenant 10 — the rate of inadvertent runaway spend on AI is the #1 surprise cost in 2026 SaaS.
6. **Buy E&O + Cyber rider** even at Tier A. The insurance bump is small (~$50/mo) and the regulatory and reputational protection is enormous.

---

## 12 · Document Control

| Version | Date | Author | Note |
| --- | --- | --- | --- |
| 1.0 | 2026-02-14 | Orisei Freight Solutions LLC | Initial cost analysis based on Q1-2026 SaaS list pricing. |

*All prices are list-rate as of February 2026 and exclude state/local taxes and currency-conversion fees. Negotiated enterprise contracts typically discount 20–45% below the list prices above at scale.*
