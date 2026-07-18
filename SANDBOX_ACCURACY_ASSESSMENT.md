# Orisei Operation Sandbox — Accuracy Assessment vs. Real-World Outcomes
**Assessment date:** June 2026 · **Benchmark sim:** SIM-D79DAD (7 days, 12 loads/day target, autopilot + AI triage)
**Real-world sources:** DAT Freight & Analytics (Week 22, May 2026), U.S. Bank Freight Payment Index Q1-2026, EIA/DOE diesel, industry brokerage benchmarks.

---

## 0. The "Day 7 × 42 entries" anomaly — ROOT CAUSE FOUND & FIXED
Your instinct was right: **that was a simulation defect, not real clustering.**
- **Root cause:** the engine persisted `sim_day` clamped to the week length (`min(sim_day, 7)`). Once the clock entered post-week settlement (days 8–10, while invoices finish paying), every tick saw "day 8 > stored day 7" and **re-fired the day-rollover routine** — duplicating the "day 7" P&L entry every tick (your 42 entries), re-accruing overhead, and re-walking the market.
- **Fix applied:** true `sim_day` now persists; each day closes exactly once; overhead bills only for in-week days; historical sims repaired (48 → 7 daily entries) and verified on a fresh full run: **7 unique daily entries, zero duplicates, overhead capped at $1,588.30.**

---

## 1. Rate accuracy (vs. DAT national spot, Week 22 · May 2026)

| Metric | Sandbox (carrier buy rate) | DAT Real (broker→carrier, all-in) | Δ | Grade |
|---|---|---|---|---|
| Dry Van $/mi | **$2.68** (sell $3.26 − 17.7% margin) | **$2.68** | 0% | A+ |
| Reefer $/mi | **$3.28** | **$3.00** | +9% | B+ |
| Flatbed $/mi | **$3.14** | **$3.26** | −4% | A− |
| Equipment mix | 55% van / 27% reefer / 18% flatbed | ~60/20/20 national spot mix | close | A− |

**Verdict:** Buy-rate realism is excellent. The sim's regional headhaul/backhaul matrix, seasonality, and spot-index walk land within ±10% of live DAT prints.

## 2. Margin accuracy

| Metric | Sandbox | Real world | Verdict |
|---|---|---|---|
| Gross margin % | **17.7%** | 12–15% typical; **9.9%** in the compressed Q1-2026 market | **Optimistic by 3–8 pts** |
| Net margin (% of revenue) | **12.0%** ($37.2k on $310.8k) | 2–6% for established brokerages | **Optimistic ~2×** |

The sim rewards perfect execution (autopilot never fat-fingers a booking, AI triage resolves every exception optimally). Real desks leak margin to re-quotes, missed emails, and concessions. Treat sandbox net as a **best-case ceiling**, not a forecast. Note: a lean 3-partner shop with $1.6k/wk overhead *can* structurally beat industry net %, but 12% assumes flawless weeks.

## 3. Fuel calibration — the biggest gap

| Metric | Sandbox | Real (mid-2026) | Verdict |
|---|---|---|---|
| DOE diesel | $3.05–$4.75 band, avg **$3.68** | **$5.60–$5.86** national (Midwest $4.75–$5.30) | **UNDERSTATED ~35%** |

The sim is calibrated to the 2024–25 diesel era. The 2026 diesel surge is the single biggest driver of today's all-in rates. Because both the sell FSC and carrier cost scale together, *margins* stay roughly correct — but absolute rate levels and fuel-surcharge lines read low vs. today's market. **Recommended recalibration:** DOE avg → $5.25, band $4.60–$6.10.

## 4. Operational friction variables

| Variable | Sandbox setting | Real-world benchmark | Verdict |
|---|---|---|---|
| Cargo claims | 1.5% of delivered loads, $350–$4,200 | 0.5–2% frequency, similar severity | ✔ In range |
| Detention | Probabilistic, $84–$… billed ($6,285 this week) | Affects 10–25% of loads; $50–$100/hr | ✔ In range |
| Carrier fall-through | 6%, rebooked at +5–8% | 3–8% spot fall-through; tender rejection 13.6% (Mar 2026) | ✔ Slightly conservative |
| Bad debt / short-pay | 2% of reserves | 0.5–1.5% with credit-checked shippers | ✔ Conservative (safe) |
| Factoring fee | 3.75% effective | 1.5–3.5% (new-broker tier) | ✔ High side of real |
| Quick-pay income | 2% on ~30% of loads | 1–3% on 20–40% | ✔ In range |
| Lumper / layover / reweigh / appt bumps | Weighted random | Everyday dock reality | ✔ Present & priced right |
| HOS realism | 52 mph × 11/24 duty ≈ 550 mi/day | 500–605 mi legal solo day | ✔ Accurate |
| DSO / cash timing | Factoring advance same-week; reserves on Net-30 | Matches factored brokerage cash cycle | ✔ Accurate |
| Fixed overhead | $226.90/day, 13 expense lines ($1,588/wk) | $1.5k–$3k/wk lean 3-person shop | ✔ Accurate |
| Load sources | DAT 37%, Truckstop 26%, Uber 13%, Convoy 10%, 123LB 12%, direct 2% | DAT-dominant spot sourcing | ✔ Plausible |

## 5. What the sandbox intentionally does NOT model (know the limits)
1. **Sales cycle friction** — real shippers take weeks/months to onboard; the sim hands you a full board on day 1.
2. **Credit approval lag & concentration risk** — no single-shipper blowup scenario.
3. **Cargo theft / double-brokering fraud** — a real and rising 2026 risk (strategic theft up sharply).
4. **Rate negotiation variance** — sim books at posted spread; real buys swing ±10% per phone call.
5. **Regulatory shocks** (English-proficiency enforcement, insurance market hardening) — not event-modeled.
6. **Weekly volume** — 84 loads/wk ≈ a 5–8 person brokerage, not a 3-partner startup's month one. Scale `loads_per_day` to 2–4 for a realistic launch-phase picture.

## 6. Overall calibration scorecard

| Category | Grade |
|---|---|
| Rates & lane economics | **A** |
| Cost/expense stack completeness | **A** |
| Operational exceptions | **A−** |
| Cash-flow mechanics (factoring/DSO) | **A−** |
| Fuel price level | **C** (2024–25 era, needs $5.25 recalibration) |
| Margin realism | **B−** (best-case bias, ~2× real-world net) |
| Volume realism vs. startup phase | **B** (configure lower loads/day) |
| **Overall** | **B+ — directionally excellent, optimistically biased** |

**Bottom line:** the sandbox is a high-fidelity *economics trainer* — its per-load math, cost stack, and cash mechanics mirror a real factored brokerage closely. Read its net margin as your **ceiling under perfect execution**; plan the real business at 50–60% of sandbox net until your desk proves otherwise. That means a sandbox week showing ~$37k net ≈ a real-world expectation of **$18–22k net** — which is exactly your Growth Copilot mission target.
