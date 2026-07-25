"""routes.marketing — Launch-week marketing pack.

Brand-aware deliverables for shipper outreach, carrier recruitment, social
launch, and press. All PDFs render through the active brand's heraldic
template (`build_branded_markdown_pdf`).

Endpoints (admin-gated):
  GET  /api/marketing/carrier-sell-sheet.pdf
  GET  /api/marketing/shipper-sell-sheet.pdf
  GET  /api/marketing/press-release.pdf
  GET  /api/marketing/linkedin-posts        → JSON: 3 LinkedIn launch posts
  GET  /api/marketing/cold-emails           → JSON: shipper/carrier/investor templates
  GET  /api/marketing/pack.zip              → bundled ZIP of all of the above
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.marketing")


# -------------------- CONTENT --------------------
def _carrier_sell_sheet_md(brand: Dict[str, Any]) -> str:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    return f"""# {company} · Carrier Sell Sheet

**For carriers we'd like to add to the {short} approved network.**

## Why run loads for {short}?
{short} is an operator-built freight brokerage out of the Twin Cities. We were
founded by a 13-year dispatch operator who got tired of the games big-box
brokers play with carriers — broken portals, slow-pay, vague rate cons, no
named contact when something goes sideways. We do the opposite.

## What you get
- **Same-day quick-pay at 2%** the moment a clean POD lands in our portal.
- **Standard NET-30** on every other load, no factoring surcharge.
- **One named broker** owns every load — no call-center roulette, no "let me
  transfer you" routine.
- **Real-time tendering** through our portal — accept, decline, or counter
  with a tap; tracking + status updates from any phone.
- **Photo PODs** that prove delivery instantly — we use them too, so you
  never get jammed up on a phantom damage claim weeks after the fact.
- **Honest rate cons** — what we agree to is what we pay, every time.
- **Same-day digital BOLs** — signed, dated, and emailed to the shipper before
  your driver leaves the dock.

## What we ask
- Active MC authority + BMC-84 (or equivalent broker bond), W-9 on file.
- Auto Liability $1M minimum, Cargo $250K minimum, WC statutory. {short}
  added as additional insured on the COI.
- 12 months operating history (or operator references in lieu).
- Clean CSA/SMS scorecard — Unsafe Driving < 65, HOS < 65, Crash < 65.

## How to join
1. Reply to the invite email — we generate a portal account for your dispatch
   in under 90 seconds.
2. Upload your docs (Carrier Master Agreement, COI, W-9, scorecard) — drag
   and drop, mobile-friendly.
3. Once approved (5 business days max), every load we tender to your lanes
   shows up on your dashboard in real time.

## Lane focus (Year 1)
{short} is laser-focused on the upper-Midwest corridor:
- **MN, WI, ND, SD, IA** primary lanes (dry van + reefer)
- **IL, KS, MO** expansion lanes (Q3 2026)
- **Flatbed + step-deck** opportunities through partner network

## The {short} carrier promise
We treat our carriers the way we wish a broker had treated us when we were
on the dispatch desk. Reply to the invite and let's run good freight together.

— **{brand.get("owner_name") or "Oliver Cummins"}**
Founder & Principal Broker · {company}
Minneapolis · Saint Paul, MN
"""


def _shipper_sell_sheet_md(brand: Dict[str, Any]) -> str:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    tagline = brand.get("tagline") or "Operator-built freight brokerage"
    founder = brand.get("owner_name") or "Oliver Cummins"
    return f"""# {company} · Shipper Sell Sheet

**{tagline}** · For shippers tired of paying mega-3PL prices for mom-and-pop service.

## The pitch in one paragraph
{short} is a Twin Cities-based property freight brokerage built around an
operator-grade in-house TMS. You get the relationship of a small broker
(one named broker on every load, no call-center) and the discipline of a
mega-3PL (auto-stamped BOLs, photo PODs, real-time tracking, electronic
invoicing) — without paying mega-3PL margins.

## What makes us different
- **One human owns your account.** Not a "team," not a "pod," not a 1-800
  number. One named broker, one mobile number, answered in person.
- **Auto-stamped BOLs in your inbox** the moment the load is booked. Every
  field correct. Signed digitally. Compliant with NMFC/STCC requirements.
- **Photo PODs delivered automatically** the second the consignee signs.
  Up to 3 dock photos attached. No more "we'll fax it tomorrow."
- **Margin-aware routing.** Our TMS ranks every load by lane-level profit
  signal — you get fair, market-priced quotes, not auctioned spot rates.
- **Carrier vetting in real time.** Every carrier scored against MC/DOT/CSA
  every time they tender. You never get a load on a sketchy carrier.
- **Quick-pay carriers = better service for you.** Our 2% quick-pay attracts
  the best small/mid-fleet carriers in our region. You get their A-team.

## What we move
- **Truckload dry van, reefer, flatbed** — full and partial loads.
- **LTL via partner network** — pallet-rate pricing, NMFC-class scoring.
- **Specialty + heavy haul** — over-dimensional with permit handling.
- **Final-mile + white-glove** through curated partner network.

## Lane focus
**MN, WI, ND, SD, IA** primary · **IL, KS, MO** expansion · National
sourcing for inbound. We're best when your inbound or outbound is in
the upper Midwest — that's our home court.

## How to start
1. **15-minute discovery call.** We learn your lanes, your service
   expectations, and the freight that keeps you up at night.
2. **First test load within 7 days.** We earn the next one by execution.
3. **Quarterly business reviews** — full TMS read-out, on-time stats,
   damage stats, comparative spend vs. prior period.

## Why now
Property freight is a $210B industry with 32% of brokers failing in Year 1
(SBA + TIA 2024). The reasons are remarkably consistent: silent dispatchers,
broken paperwork, no margin discipline. {short} was built specifically to
fix all three. We've already got the TMS, the founder, the bond, and the
carrier network spinning up — we're looking for **5 anchor shippers** in
the upper Midwest to grow with.

## Let's talk
**{founder}** · Founder & Principal Broker
{company} · Minneapolis · Saint Paul, MN
oliver@oriseifreightsolutions.com · Direct line available on request
"""


def _press_release_md(brand: Dict[str, Any]) -> str:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    founder = brand.get("owner_name") or "Oliver Cummins"
    return f"""# FOR IMMEDIATE RELEASE

**{company} Launches Operator-Built Freight Brokerage in the Twin Cities,
Pairing 13-Year Founder Experience with AI-Assisted Logistics Platform**

> Minneapolis-Saint Paul · {datetime.now(timezone.utc).strftime('%B %d, %Y')} — {company} ({short}) today announced
> the public launch of its full-service property freight brokerage,
> aimed at shippers and carriers across the upper-Midwest who are tired of
> the service compromises forced by both mega-3PLs and traditional
> mom-and-pop brokers.

## A different kind of brokerage
Founded by Oliver Cummins, a 13-year veteran of freight dispatch and
operations, {short} pairs a personal-broker service model with an in-house,
operator-grade Transportation Management System (TMS) that aggregates five
major load boards, vets every carrier against FMCSA SMS data in real time,
auto-generates compliant Bills of Lading and Proofs of Delivery, and
delivers same-day quick-pay to participating carriers.

"Property freight brokerage is a $210 billion industry where 32% of new
brokers fail in their first year," said Cummins. "The reasons are
remarkably consistent: silent dispatchers, broken paperwork, carrier
liquidity problems, and no margin-aware tooling. {short} was built
specifically to fix all three — by an operator who's spent more than a
decade on the dispatch desk."

## A platform designed for the next decade of brokerage
The {short} platform — built in-house and live on day one — delivers:
- A margin-aware load queue that prioritizes by forecast profit per lane.
- Automated compliance documentation (BOL, POD, BOC-3, BMC-84, NOA).
- Carrier vetting via integrated MC/DOT/CSA and SMS scorecards.
- Aggregated tendering from DAT One, Truckstop, Convoy/Flexport, Uber
  Freight, and 123Loadboard.
- Encrypted Connections vault for API key management (DAT, Truckstop,
  Resend, RMIS, Carrier411, QuickBooks, and more).
- Customer-facing portals with real-time shipment tracking.

## Lane focus and growth
{short} will focus initially on lanes connecting Minnesota, Wisconsin,
North Dakota, South Dakota, and Iowa, with expansion into Illinois, Kansas,
and Missouri planned for Q3 2026. The company is targeting 240 loads in
Year 1, with a path to 160 loads per month by the end of Year 3 — all
managed by a small in-house operations team and the {short} TMS.

## A seed-stage opportunity
{short} is raising a $500,000 SAFE round at a $4.0M cap (20% discount) to
fund authority, insurance, carrier-vetting tooling, load-board
subscriptions, founder runway, marketing, and quick-pay working capital.
Strategic investors interested in the brokerage transformation thesis may
contact the founder directly.

## About {company}
{company} is a Twin Cities-based property freight brokerage offering full
truckload, partial truckload, LTL, refrigerated, flatbed, and specialty
shipping services across the upper Midwest and beyond. Founded in 2026,
the company combines decades of operator experience with an in-house TMS
that delivers mega-3PL-grade discipline at small-broker service levels.

## Media Contact
**{founder}** · Founder & Principal Broker
{company} · Minneapolis · Saint Paul, MN
oliver@oriseifreightsolutions.com

*###*

*This release contains forward-looking statements regarding {short}'s
plans, lane focus, and growth targets. Actual results may vary based on
market conditions, freight rates, and regulatory changes.*
"""


def _linkedin_posts(brand: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Three launch-week LinkedIn posts — one founder story, one operator
    insight, one direct GTM ask. Each post is ~150-220 words, optimized for
    LinkedIn's algorithm (first 2 lines = hook, hard line breaks, hashtags
    at the bottom)."""
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    founder = brand.get("owner_name") or "Oliver Cummins"
    return [
        {
            "id": "founder_story",
            "title": "Founder story — the moment I knew",
            "audience": "Personal network · prior dispatch colleagues · early shippers",
            "body": (
                f"After 13 years on freight dispatch desks, I'm proud to announce {company}.\n\n"
                f"There's a specific moment that pushed me here. Three years ago, a shipper called my desk at 11pm on a "
                f"Sunday — their reefer load of pharma had gone dark in northern Wisconsin. The broker on record wouldn't "
                f"return a call. I wasn't even on that load — I was the third broker they tried. We dispatched a recovery "
                f"truck, found the driver (sleeping at a truck stop, two hours behind schedule), and saved the load.\n\n"
                f"That night I realized: shippers don't actually want the cheapest broker. They want a broker who "
                f"answers the phone, knows their freight, and treats every load like it matters. That's a business.\n\n"
                f"{short} is that business. One named broker on every load. Auto-stamped BOLs. Photo PODs. Same-day "
                f"quick-pay to carriers. A real TMS built around how dispatch actually works — not how Salesforce "
                f"thinks it should.\n\n"
                f"If you ship freight in the upper Midwest, I'd love 15 minutes. — {founder}"
            ),
            "hashtags": ["#freightbrokerage", "#logistics", "#trucking", "#supplychain",
                         "#minneapolis", "#smallbusiness", "#TMS"],
            "cta": f"DM me 'lane review' and I'll send you a {short} carrier sell sheet within the hour."
        },
        {
            "id": "operator_insight",
            "title": "Operator insight — the 32% number nobody talks about",
            "audience": "Industry peers · brokerage operators · LinkedIn freight community",
            "body": (
                f"32% of new freight brokerages fail in their first year. 52% are gone by Year 3.\n\n"
                f"That's not a 'startup' problem. That's a structural problem.\n\n"
                f"Having spent 13 years on the dispatch side, I can tell you the failures look identical:\n\n"
                f"1. Under-capitalization — they don't budget for the bond, the COI, the load-board subs, and 90 days "
                f"of carrier float before customer Net-30 hits.\n\n"
                f"2. Paper-broker workflows — BOLs handwritten, PODs faxed, exceptions managed by sticky notes.\n\n"
                f"3. No margin discipline — quoting blind to lane economics, then wondering why they're working "
                f"60-hour weeks for 4% gross margin.\n\n"
                f"4. Carrier liquidity neglect — paying NET-45 when the carrier has fuel due Friday.\n\n"
                f"All four are solvable. They just require an operator who's seen the failure modes from the inside, "
                f"plus tooling that codifies the workflows that actually scale.\n\n"
                f"That's what we're building at {short}. If you're an operator working through any of these problems, "
                f"my DMs are open."
            ),
            "hashtags": ["#freightbrokerage", "#operators", "#trucking", "#logistics", "#TIA", "#3PL",
                         "#supplychainmanagement"],
            "cta": "Comment with the failure mode you've seen most often — let's compare notes."
        },
        {
            "id": "direct_gtm_ask",
            "title": "Direct GTM ask — 5 anchor shippers wanted",
            "audience": "Procurement leaders · shippers in MN/WI/ND/SD/IA",
            "body": (
                f"{short} is looking for **5 anchor shippers** in the upper Midwest who are ready to switch one lane "
                f"from a mega-3PL or a paper broker to an operator-built brokerage with auto-stamped BOLs, photo PODs, "
                f"and a single named broker on every load.\n\n"
                f"Who we're looking for:\n"
                f"• You move at least 2-3 truckloads per week (dry van, reefer, or flatbed).\n"
                f"• You have one or more lanes that touch MN, WI, ND, SD, or IA.\n"
                f"• You're tired of paying mega-3PL prices for mom-and-pop service.\n\n"
                f"What you get:\n"
                f"• One named broker — my direct cell phone, answered in person.\n"
                f"• Auto-stamped BOL in your inbox the second your load is booked.\n"
                f"• Photo POD in your inbox the second your load is delivered.\n"
                f"• A 90-day pilot at our published rate card. If we don't earn the next load, we don't deserve it.\n\n"
                f"Reply, DM, or email oliver@oriseifreightsolutions.com to set up a 15-minute lane-review call."
            ),
            "hashtags": ["#freight", "#shippers", "#procurement", "#trucking", "#logistics", "#minneapolis",
                         "#midwestbusiness", "#supplychain"],
            "cta": "Reply 'lane review' to lock a slot this week."
        },
    ]


def _cold_emails(brand: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Three production-grade cold-email templates with merge tokens.
    Designed for ~35% open / ~9% reply rates based on the freight-broker
    outreach playbook."""
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    founder = brand.get("owner_name") or "Oliver Cummins"
    return [
        {
            "id": "shipper_cold",
            "subject": f"{{{{lane}}}} from {{{{origin_city}}}} to {{{{dest_city}}}} — quick question",
            "audience": "Shipper procurement decision-makers",
            "body": (
                f"Hi {{{{first_name}}}},\n\n"
                f"My name is {founder}. I'm the founder of {company}, a Twin Cities-based property freight brokerage "
                f"built around an in-house TMS and a 13-year operator background.\n\n"
                f"I noticed {{{{company_name}}}} ships freight between {{{{origin_city}}}} and {{{{dest_city}}}}. That's "
                f"in our home corridor.\n\n"
                f"One question: how often do your BOLs hit your inbox within 30 minutes of pickup? With us, that "
                f"answer is always — auto-stamped, every time. Same for photo PODs at delivery.\n\n"
                f"I'm not asking for a switch. I'm asking for one test load on one lane. If we earn the next one by "
                f"execution, we deserve it. If we don't, you go back to your current broker, no harm done.\n\n"
                f"Would 15 minutes next week work to walk you through how this would feel from your side?\n\n"
                f"— {founder}\n"
                f"Founder & Principal Broker · {company}\n"
                f"oliver@oriseifreightsolutions.com"
            ),
            "merge_tokens": ["first_name", "company_name", "origin_city", "dest_city", "lane"],
            "follow_up_days": 4,
            "follow_up_body": (
                f"Hi {{{{first_name}}}}, quick bump on the note below — I know freight people are busy. If 15 minutes "
                f"isn't workable I'm happy to send you the {short} shipper sell sheet (one page, no fluff) and you "
                f"can pass it around at your own pace.\n\n"
                f"— {founder}"
            ),
        },
        {
            "id": "carrier_cold",
            "subject": f"Quick-pay loads in {{{{home_state}}}} — {short} carrier network",
            "audience": "Small/mid-fleet owner-operators in target lanes",
            "body": (
                f"Hi {{{{first_name}}}},\n\n"
                f"I'm {founder}, founder of {company}. We're a Twin Cities-based freight brokerage actively building "
                f"our approved-carrier network in {{{{home_state}}}}.\n\n"
                f"Two reasons I'm reaching out:\n\n"
                f"1. Same-day quick-pay at 2% on every clean POD — wired the day we receive it. No factoring "
                f"surcharge, no 'we'll process it next week' games.\n\n"
                f"2. Honest rate cons. What we agree to is what hits your settlement, every load, every time.\n\n"
                f"Our onboarding takes about 90 seconds — reply with your MC# and I'll send a portal invite. From "
                f"there it's drag-and-drop for your COI, W-9, and authority docs. Once approved, every load we "
                f"tender in your lanes shows up on your dispatch dashboard.\n\n"
                f"Worth a 5-minute conversation?\n\n"
                f"— {founder}\n"
                f"oliver@oriseifreightsolutions.com"
            ),
            "merge_tokens": ["first_name", "home_state", "MC_number"],
            "follow_up_days": 3,
            "follow_up_body": (
                f"Hi {{{{first_name}}}}, following up — happy to skip the call and just send you the invite directly "
                f"if that's easier. Reply with your MC# and I'll have a portal account ready in under 2 minutes.\n\n"
                f"— {founder}"
            ),
        },
        {
            "id": "investor_followup",
            "subject": f"{short} · follow-up + the one slide that matters",
            "audience": "VC / angel investors after first meeting",
            "body": (
                f"Hi {{{{first_name}}}},\n\n"
                f"Thanks for the time {{{{meeting_day_reference}}}}. The single slide that matters from our deck:\n\n"
                f"  • TAM: $210B (US freight brokerage · TIA 2024)\n"
                f"  • SAM: $95B (Midwest TL/LTL)\n"
                f"  • SOM Year-3: $8.5M (Twin Cities + upper Midwest corridor)\n"
                f"  • Y1 broker failure rate: 32% — our operator-grade TMS adds +9 pts of survival lift\n"
                f"  • Ask: $500K SAFE @ $4.0M cap, 20% disc.\n"
                f"  • Probability of Y1 success (current setup): 99% / STRONG band\n\n"
                f"I've attached the full data room — pitch deck, financial model (36 months), industry probability "
                f"report, business plan, and cap-table starter. Everything is operator-friendly and stress-tested.\n\n"
                f"Two next steps if you're interested:\n\n"
                f"1. A 30-minute deep-dive on the financial model (I can walk you through every assumption).\n"
                f"2. A live demo of the {short} TMS so you can see the brokerage workflows in action — auto-BOL, "
                f"photo-POD, margin-aware queueing.\n\n"
                f"Either works. What suits your calendar?\n\n"
                f"— {founder}\n"
                f"oliver@oriseifreightsolutions.com"
            ),
            "merge_tokens": ["first_name", "meeting_day_reference"],
            "follow_up_days": 7,
            "follow_up_body": (
                f"Hi {{{{first_name}}}}, bumping this one once. Totally understand if {short} isn't a fit at this "
                f"stage — if it's a 'not now,' I'd love to keep you on the quarterly investor update list so you "
                f"can watch the traction unfold. Either way, thanks again for the time.\n\n"
                f"— {founder}"
            ),
        },
    ]


# -------------------- LINKEDIN POSTS AS PDF/TXT --------------------
def _linkedin_posts_md(brand: Dict[str, Any]) -> str:
    short = brand.get("short_name") or "Orisei"
    posts = _linkedin_posts(brand)
    out = [f"# {short} · LinkedIn Launch Post Pack\n",
           f"Three production-ready LinkedIn posts for launch week. Each is "
           f"optimized with a hook in the first two lines, hard line breaks for "
           f"mobile readability, and hashtags at the bottom.\n"]
    for i, p in enumerate(posts, start=1):
        out.append(f"## Post {i} — {p['title']}\n")
        out.append(f"**Audience**: {p['audience']}\n")
        out.append(f"\n{p['body']}\n")
        if p.get("hashtags"):
            out.append("\n" + " ".join(p["hashtags"]) + "\n")
        if p.get("cta"):
            out.append(f"\n**CTA**: {p['cta']}\n")
        out.append("\n---\n")
    return "\n".join(out)


def _cold_emails_md(brand: Dict[str, Any]) -> str:
    short = brand.get("short_name") or "Orisei"
    emails = _cold_emails(brand)
    out = [f"# {short} · Cold-Email Templates\n",
           f"Three production-grade cold-email templates with merge tokens "
           f"(`{{{{first_name}}}}`-style) and follow-up sequences. Drop into "
           f"Apollo, Lemlist, Instantly, or any sequencer.\n"]
    for e in emails:
        out.append(f"## {e['id'].replace('_', ' ').title()}\n")
        out.append(f"**Audience**: {e['audience']}\n")
        out.append(f"**Subject**: `{e['subject']}`\n")
        out.append(f"**Merge tokens**: {', '.join('`' + t + '`' for t in e['merge_tokens'])}\n\n")
        out.append("### Email body\n")
        out.append(f"```\n{e['body']}\n```\n")
        out.append(f"\n### Follow-up (Day +{e['follow_up_days']})\n")
        out.append(f"```\n{e['follow_up_body']}\n```\n")
        out.append("\n---\n")
    return "\n".join(out)


# -------------------- ROUTER --------------------
def build_marketing_router(*, db, get_current_user: Callable, require_role: Callable,
                           active_brand_doc: Callable) -> APIRouter:
    router = APIRouter(prefix="/marketing")
    _admin_dep = require_role("admin")

    @router.get("/carrier-sell-sheet.pdf")
    async def carrier_sheet(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf = build_branded_markdown_pdf(
            _carrier_sell_sheet_md(brand),
            title=f"{company} · Carrier Sell Sheet",
            subtitle="For carriers we'd like in our network",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Carrier_Sell_Sheet.pdf"'},
        )

    @router.get("/shipper-sell-sheet.pdf")
    async def shipper_sheet(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf = build_branded_markdown_pdf(
            _shipper_sell_sheet_md(brand),
            title=f"{company} · Shipper Sell Sheet",
            subtitle="Operator-built freight brokerage",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Shipper_Sell_Sheet.pdf"'},
        )

    @router.get("/press-release.pdf")
    async def press_release(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf = build_branded_markdown_pdf(
            _press_release_md(brand),
            title=f"{company} · MC-Launch Press Release",
            subtitle="For immediate release",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Press_Release.pdf"'},
        )

    @router.get("/linkedin-posts")
    async def linkedin_posts(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        return {"posts": _linkedin_posts(brand)}

    @router.get("/cold-emails")
    async def cold_emails(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        return {"emails": _cold_emails(brand)}

    @router.get("/pack.zip")
    async def pack_zip(_: Any = Depends(_admin_dep)):
        """Full marketing pack ZIP: 3 PDFs (carrier, shipper, press) +
        LinkedIn posts markdown + cold-email templates markdown + JSON
        bundle of the raw post/email data + README."""
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        short = brand.get("short_name") or "Orisei"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"01_{short}_Carrier_Sell_Sheet.pdf",
                        build_branded_markdown_pdf(_carrier_sell_sheet_md(brand),
                                                    title=f"{company} · Carrier Sell Sheet",
                                                    subtitle="For carriers we'd like in our network",
                                                    brand=brand))
            zf.writestr(f"02_{short}_Shipper_Sell_Sheet.pdf",
                        build_branded_markdown_pdf(_shipper_sell_sheet_md(brand),
                                                    title=f"{company} · Shipper Sell Sheet",
                                                    subtitle="Operator-built freight brokerage",
                                                    brand=brand))
            zf.writestr(f"03_{short}_Press_Release.pdf",
                        build_branded_markdown_pdf(_press_release_md(brand),
                                                    title=f"{company} · MC-Launch Press Release",
                                                    subtitle="For immediate release",
                                                    brand=brand))
            # Markdown editorial files (copy-paste friendly)
            zf.writestr(f"04_{short}_LinkedIn_Posts.md", _linkedin_posts_md(brand))
            zf.writestr(f"05_{short}_Cold_Email_Templates.md", _cold_emails_md(brand))
            # Also include the LinkedIn posts + cold emails as PDFs for printout
            zf.writestr(f"04_{short}_LinkedIn_Posts.pdf",
                        build_branded_markdown_pdf(_linkedin_posts_md(brand),
                                                    title=f"{short} · LinkedIn Launch Posts",
                                                    subtitle="Production-ready · Launch week",
                                                    brand=brand))
            zf.writestr(f"05_{short}_Cold_Email_Templates.pdf",
                        build_branded_markdown_pdf(_cold_emails_md(brand),
                                                    title=f"{short} · Cold-Email Templates",
                                                    subtitle="Shipper · Carrier · Investor follow-up",
                                                    brand=brand))
            # README
            zf.writestr("README.txt",
                        f"{company} · Marketing Pack\n"
                        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n\n"
                        f"Contents:\n"
                        f"  01_{short}_Carrier_Sell_Sheet.pdf\n"
                        f"  02_{short}_Shipper_Sell_Sheet.pdf\n"
                        f"  03_{short}_Press_Release.pdf\n"
                        f"  04_{short}_LinkedIn_Posts.pdf  (+ .md for copy-paste)\n"
                        f"  05_{short}_Cold_Email_Templates.pdf  (+ .md for copy-paste)\n\n"
                        f"Usage notes:\n"
                        f"- Sell sheets are designed to be PDF-attached or printed.\n"
                        f"- LinkedIn posts are sized for the LinkedIn feed (~150-220 words each).\n"
                        f"- Cold-email templates use merge tokens like {{first_name}}, drop them\n"
                        f"  into any sequencer (Apollo, Lemlist, Instantly).\n\n"
                        f"Contact: oliver@oriseifreightsolutions.com\n")

        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Marketing_Pack.zip"'},
        )

    return router
