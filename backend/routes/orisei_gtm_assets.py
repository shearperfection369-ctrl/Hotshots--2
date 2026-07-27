"""routes.orisei_gtm_assets — Marketing assets for Orisei Freight ag/grain GTM.

Generates the brochure PDF + serves the email/LinkedIn/video-script copy
so Oliver can copy-paste into LinkedIn, Outlook, Resend, etc.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from .orisei_docs import build_branded_markdown_pdf

# ============================ COPY ============================
BROCHURE_MARKDOWN = """# Orisei Freight Solutions
### Minnesota's specialty-grain & ag freight desk

---

## Who we are

Orisei Freight Solutions is a Plymouth-MN-based brokerage purpose-built for
**western and southern Minnesota's grain, feed, and specialty-ag shippers**.
We dispatch dry-van, hopper, flatbed, and reefer capacity from harvest belts
to the Twin Cities, MSP rail ramps, and Gulf export terminals.

---

## What you get

- **30-minute spot quote response** during harvest windows (6 AM – 8 PM CT).
- **Live shipper portal** — your active loads, routing guide, invoices, and
  POD photos in one token-protected URL. No login. No PDF chase.
- **Margin Shield carrier vetting** — every carrier auto-checked against FMCSA
  SAFER (operating authority, safety rating, insurance on file). Red flags
  blocked before tender.
- **Branded rate confirmations + BOLs** generated from our TMS, emailed direct
  to your dispatcher inbox.
- **Net 30** with optional **QuickPay 2% / Net 7** for QuickBooks-linked
  customers.

## Insurance & authority

| | |
|---|---|
| FMCSA MC# | **(submit current MC#)** |
| BMC-84 surety bond | **$75,000** |
| Auto liability | **$1,000,000** |
| Contingent cargo | **$100,000** |
| General liability + E&O | **$1,000,000** |

## Coverage lanes (Q3 2026 active)

- MN harvest belt (Willmar / Marshall / Worthington / Albert Lea) → Cargill /
  CHS / ADM crush plants + MSP rail
- Minneapolis-St. Paul → Gulf export ramps (Houston, Galveston, New Orleans)
- Twin Cities → Pacific Northwest export (Tacoma, Seattle, Vancouver WA)
- Regional spot (MN / IA / SD / ND / WI / IL) for harvest-overflow capacity

## Equipment we cover

- Dry van (53')
- Hopper bottom + grain trailer
- Flatbed + step-deck (for ag equipment, fertilizer totes, bagged seed)
- Reefer (specialty seed, frozen ingredient)
- Hot-shot / pup combos for high-priority parts and small lots

---

## How a load works

1. **You email or portal-request a spot quote** (lane, equipment, pickup window).
2. **We respond within 30 min** with a firm rate good for 24 hr.
3. **You accept** — we dispatch a vetted carrier, generate a rate confirmation
   PDF, and the rate-con is in your inbox before the truck rolls.
4. **Driver updates status** via our PWA — pickup, in-transit, delivery — with
   GPS-stamped photos at each milestone.
5. **POD lands in your portal** the moment the driver signs off.
6. **Invoice mails the next business day**. Net 30 or QuickPay.

---

## Why ag/grain shippers pick us

- We dispatched from a **TMS we built ourselves** — faster than McLeod, more
  transparent than C.H. Robinson. You see what we see.
- We're **local**. Same time zone, same weather, same elevators. You're not
  pitching from a Bangalore call center.
- We're **small enough to remember your name**, big enough to cover 20 trucks
  in a day during harvest peak.

---

## Talk to us

**Oliver Cummins** · Founder & Head of Dispatch
Plymouth, MN
oliver@oriseifreightsolutions.com
"""


EMAIL_TEMPLATES = {
    "v1_lane_specific": {
        "subject": "Quick lane question — {shipper_city} → MSP",
        "body": """Hi {first_name},

Saw {company} runs grain from {shipper_city} to the Cargill / CHS / ADM crush
plants in the Twin Cities. Last week our average $/mi on that lane was
**$2.85** with a 96% on-time pickup score.

Worth a 10-minute call to compare your current dispatch vs. ours? I'd send
you a live portal link with your three top lanes so you can see actual rates
in real time — no login required.

— Oliver

Oliver Cummins · Orisei Freight Solutions · Plymouth, MN
oliver@oriseifreightsolutions.com · {phone}""",
    },
    "v2_harvest_overflow": {
        "subject": "Harvest overflow capacity — {company}",
        "body": """Hi {first_name},

Heard from a couple of {company}'s neighbors that this harvest is running
hot and your contracted carriers are turning down spot loads.

We're sitting on **{capacity_count} hopper-bottom + dry-van combos** out of
Plymouth right now and can roll a truck to {shipper_city} inside of 12 hours.

If you want to put me in your dispatch rotation as overflow capacity, I'll
send over our COI + W-9 + carrier packet today. No commitment, just be there
when your A-list carriers are.

— Oliver
Orisei Freight Solutions · Plymouth, MN""",
    },
    "v3_break_up": {
        "subject": "Closing your file, {first_name}",
        "body": """Hi {first_name},

Last email from me — closing your file unless I hear back. If freight isn't
the right topic, who at {company} handles your dispatch overflow during
harvest peak?

If I'm not the right fit, no hard feelings. If we should talk, here's our
live portal link — pick any lane and you'll see a real-time rate band
pulled from our actual booking history:

  https://livecleans.com/customer-portal?token={portal_token}

— Oliver""",
    },
}


LINKEDIN_PROFILE = """# Oliver Cummins · LinkedIn Profile Rewrite

## Headline (220 chars max)
**Founder · Orisei Freight Solutions | MN ag-grain freight desk · Plymouth, MN | Building the TMS the way brokers actually dispatch**

## About section (2,000 chars)

I run Orisei Freight Solutions — a Plymouth-MN brokerage built specifically
for the western and southern Minnesota grain belt.

After watching ag shippers fight stale rate sheets, missing PODs, and
dispatch-rotation politics for years, I built our own TMS from the ground up.
Same screen our dispatchers work in is the screen you, the shipper, log into
when you want to see your loads. No back-and-forth. No "give me 24 hours and
I'll get back to you."

What I focus on:

→ **30-minute spot quotes** during harvest windows. If your A-list carriers
   turn down a load at 6 AM, I'm the call before the sun comes up at 7.

→ **Carrier vetting that's actually fast.** Every carrier is auto-checked
   against FMCSA SAFER before tender. No expired authority, no
   conditional-rated trucks on your freight.

→ **Live portal access.** Every customer gets a unique URL with their lanes,
   their rates, their POD photos. No login. No "I'll forward you the BOL on
   Monday."

→ **Net 30 with QuickPay 2% / Net 7** for QuickBooks-linked customers.

Most of our work is grain belt → MSP rail / Gulf export / PNW. If your
freight runs that map, send me a note.

oliver@oriseifreightsolutions.com

## Featured section (3 items)
1. **Orisei Customer Portal demo** — link to https://livecleans.com/customer-portal-demo
2. **2026 Q3 lane rate sheet** — PDF download
3. **First 3 loads at carrier cost + $50** offer — landing page

## Experience entry (the one for Orisei)
**Founder & Head of Dispatch · Orisei Freight Solutions LLC**
Plymouth, Minnesota · 2026 — Present

Built a Minnesota-specialized freight brokerage from zero. Built our own
TMS so shippers can self-serve quotes, track loads, and pull invoices
without a phone call.

Focus: ag, grain, feed, and specialty fertilizer freight from the
MN/Dakotas harvest belt to Twin Cities crush plants, Gulf export ramps,
and Pacific Northwest export terminals.

## Connection invite template (300 char limit)
> Hi {first_name} — I run a small ag-freight brokerage out of Plymouth and
> noticed {company} is in the {city} corridor we run hard. Mind if I add
> you so I can share rate-band info when it's relevant? — Oliver

## Posting cadence (3x/week, M/W/F)
- **Mondays:** Lane-specific rate insight ("MSP → Houston Gulf ran $X.XX
  last week, here's why")
- **Wednesdays:** Operational story (a load you saved, a hot-shot you ran)
- **Fridays:** Capacity ping ("looking for 3 hoppers MN/IA next week — DM
  if you can place them")
"""


VIDEO_SCRIPT = """# 30-Second Customer Portal Demo Video Script

Use the existing `/scripts/build_hotshot_tms_promo.py` infrastructure
to record this. Replace Hot Shot TMS branding with Orisei Freight.

## Voice-over (OpenAI TTS · "echo" voice · warm-professional)

```
You run grain to the Twin Cities crush plants every week.
Every week, your broker emails you a PDF rate sheet that's already stale.
Every week, you chase POD photos by text.

Orisei Freight is different.

(00:08)

When you ship with us, you get a private portal — your portal — with your
lanes, live rates, real carrier scores. No login. No 24-hour wait.

(00:16)

Need a spot quote? Click. Request. Reply in 30 minutes — not tomorrow.

Need a POD? It's already in your portal the moment the truck unloads.

(00:24)

Orisei Freight Solutions. Built in Minnesota. For Minnesota grain.
Email Oliver — oliver@oriseifreightsolutions.com.
```

## Visual storyboard

| Time | Scene | On-screen |
|---|---|---|
| 00:00 - 00:03 | Aerial drone shot of MN grain elevator at sunrise | "ORISEI FREIGHT" logo wipe |
| 00:04 - 00:08 | Hands typing a stale Excel rate sheet | Pain-point title text |
| 00:09 - 00:16 | Screen recording: customer portal opening; routing-guide tab; lane card with live RPM band | Live UI walkthrough |
| 00:17 - 00:22 | Spot-quote-request dialog open + submit + success state | Lower-third: "Reply in 30 min" |
| 00:23 - 00:27 | POD photo gallery on portal | Lower-third: "POD in real-time" |
| 00:28 - 00:30 | Closing card | "Orisei Freight Solutions · Plymouth, MN · oliver@oriseifreightsolutions.com" |

## Distribution

1. Post to LinkedIn (Oliver's profile + Orisei company page)
2. Embed in customer portal hero (we'll wire `/customer-portal` to autoplay
   the first time a token is hit)
3. Email signature attachment (short autoplay gif version)
4. Reply-link in every cold email's PS:
   "PS — 30-sec look at the portal we'll give you: [link]"

## Music
Royalty-free option: "Tomorrow Will Be Better" by Reaktor Productions
(via Artlist or Epidemic Sound — ~$15/license).
"""


# ============================ ROUTER ============================
def build_gtm_assets_router(api_router: APIRouter, *, db,
                              require_role: Callable) -> None:
    router = APIRouter(prefix="/marketing/orisei", tags=["marketing", "gtm"])
    admin_dep = Depends(require_role("admin"))

    @router.get("/brochure-pdf")
    async def brochure_pdf(_=admin_dep):
        brand = await db.company_brand.find_one(
            {"is_active": True}, {"_id": 0}) or {}
        pdf = build_branded_markdown_pdf(
            BROCHURE_MARKDOWN,
            title="Orisei Freight Solutions",
            subtitle="MN specialty-grain & ag freight desk · 2026",
            brand=brand,
        )
        return Response(content=pdf, media_type="application/pdf",
                          headers={"Content-Disposition":
                                    "attachment; filename=Orisei_Brochure_2026.pdf"})

    @router.get("/email-templates")
    async def email_templates(_=admin_dep) -> Dict[str, Any]:
        return {"templates": EMAIL_TEMPLATES}

    @router.get("/linkedin-profile")
    async def linkedin_profile(_=admin_dep) -> Dict[str, str]:
        return {"markdown": LINKEDIN_PROFILE}

    @router.get("/video-script")
    async def video_script(_=admin_dep) -> Dict[str, str]:
        return {"markdown": VIDEO_SCRIPT}

    api_router.include_router(router)
