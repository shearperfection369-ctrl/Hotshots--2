"""
Shipper Outreach Studio — generates branded, optionally-AI-personalized
materials for soliciting and onboarding shippers.

Channels
--------
* `email`           — cold introduction email (HTML + plain text + subject)
* `call_script`    — structured cold-call talking points + objection handling
* `linkedin_dm`    — short DM template
* `capability_pdf` — 1-page branded capability statement PDF
* `agreement_pdf`  — broker-shipper service agreement (Net 7 / 10 / 14)
* `welcome_pdf`    — welcome letter for newly-onboarded shippers
* `onboarding_packet` — single PDF: capability + agreement + welcome +
                        credit reference form + COI/W-9 request

All copy is brand-aware: pulls the active brand's company name, primary color,
contact email and signs as "Oliver Cummins · Founder" (configurable via the
active brand doc). Personalization fields: shipper_name, contact_name,
lane_focus, mode_mix.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .orisei_docs import build_branded_markdown_pdf

log = logging.getLogger("orisei.shipper_outreach")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _today() -> str:
    return datetime.now(timezone.utc).strftime("%B %-d, %Y")


def _brand_meta(brand: Optional[Dict[str, Any]]) -> Dict[str, str]:
    b = brand or {}
    return {
        "company":  b.get("company_name") or "Orisei Freight Solutions LLC",
        "short":    b.get("short_name")   or "ORISEI",
        "contact":  b.get("contact_email")
                    or "oliver@oriseifreight.com",
        "phone":    b.get("phone")        or "(612) 555-0114",
        "founder":  b.get("founder_name") or "Oliver Cummins",
        "city":     b.get("hq_city")      or "Minneapolis, MN",
        "site":     b.get("website")      or "oriseifreight.com",
        "primary":  b.get("primary_color") or "#0E3A6B",
    }


async def _maybe_personalize_intro(
    shipper_name: str,
    contact_name: str,
    lane_focus: str,
    mode_mix: str,
    channel: str,
) -> Optional[str]:
    """Use Claude (via Emergent LLM key) to write a 1–2 sentence intro that
    references the shipper by name. Returns None if no API key is configured,
    in which case the caller falls back to the static template intro."""
    key = (os.environ.get("EMERGENT_LLM_KEY")
           or os.environ.get("EMERGENT_UNIVERSAL_KEY"))
    if not key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        prompt = (
            f"Write a single sentence (max 30 words) opening a {channel} from "
            f"a new freight brokerage to {shipper_name}. Address the contact "
            f"as {contact_name or 'the team'}. Reference {lane_focus or 'their lanes'} and "
            f"{mode_mix or 'their freight mix'}. Confident, founder-led, no hype, "
            "no exclamation marks, no clichés like 'I hope this finds you well'. "
            "Output only the sentence, no quote marks."
        )
        chat = (LlmChat(api_key=key,
                         session_id=f"outreach-{shipper_name[:24]}",
                         system_message="You write tight, founder-direct "
                                        "cold outreach for B2B freight.")
                .with_model("anthropic", "claude-sonnet-4-5"))
        resp = await chat.send_message(UserMessage(text=prompt))
        return (str(resp) or "").strip().strip("\"'") or None
    except Exception as e:                                       # noqa: BLE001
        log.warning("intro personalization failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Static template bodies
# ---------------------------------------------------------------------------
def _email_body(shipper: str, contact: str, lane: str, mode: str,
                 intro: Optional[str], meta: Dict[str, str]) -> Dict[str, str]:
    hello = f"Hi {contact or 'team'},"
    opening = intro or (
        f"I'm {meta['founder']}, founder of {meta['company']}. We're a new "
        f"asset-light freight brokerage built in {meta['city']}, and we'd "
        f"like to bid on {shipper}'s "
        f"{lane or 'inbound and outbound'} freight."
    )
    body_md = f"""{hello}

{opening}

A few reasons it's worth a 15-minute call:

- **One owner, one call.** You speak directly with me — no junior dispatcher rotation. Margin Shield tooling and real-time tracking are baked in from day one.
- **Asset-light, multi-mode.** {mode or "TL, LTL, parcel, and ocean/air when required"} — we source the right carrier, you stop juggling vendors.
- **Documented service.** Every load gets a rate confirmation, BOL, POD, and invoice — auto-archived to an immutable 7-year vault you can audit any time.
- **Founder-grade accountability.** I personally cover every load. If a wheel falls off, you'll hear it from me before you hear it from the receiver.

Open to a 15-minute intro this week? I can come with a lane benchmark for two of your top {lane.split(',')[0] if lane else 'corridors'}.

Either way — thanks for the read.

{meta['founder']}
Founder · {meta['company']}
{meta['contact']} · {meta['phone']}
{meta['site']}
"""
    return {
        "subject": f"15 minutes · {shipper} freight · {meta['short']} intro",
        "plain":   body_md,
        "html":    _md_to_basic_html(body_md, meta),
    }


def _call_script_md(shipper: str, contact: str, lane: str,
                     meta: Dict[str, str]) -> str:
    return f"""# COLD CALL SCRIPT · {shipper.upper()}

**Target contact:** {contact or "Logistics / Transportation Manager"}
**Lanes to anchor:** {lane or "Their top inbound & outbound corridors"}
**Prepared:** {_today()}

---

## Opening (15 seconds — earn the next 60)

> "Hi {contact or '<contact>'}, this is {meta['founder']} at {meta['company']} — I'm a freight brokerage based out of {meta['city']}.
> I'm calling because we'd like to bid on a couple of {shipper}'s lanes. Do you have ninety seconds, or should I grab fifteen minutes on your calendar this week?"

If they say **busy**: "Totally — fifteen minutes Thursday at 10 a.m. CST?" → book it.

If they say **go ahead**: pivot into the value pitch ↓

---

## Value pitch (60 seconds)

1. **Single owner, full accountability.** "You'll deal directly with me, not a rotating bench of dispatchers. Every load is mine."
2. **Margin Shield + immutable archive.** "Every BOL, rate confirmation, and invoice we issue is auto-archived for seven years. You can audit anything at any time."
3. **Asset-light, multi-mode.** "TL, LTL, parcel, ocean and air — I source the right carrier, you stop juggling vendors."
4. **Net 7 / 10 / 14 friendly.** "We factor on the back end so terms are flexible for you."

---

## Discovery (the only 4 questions that matter)

- Who's your **incumbent broker** today, and what's the one thing you wish they did better?
- What's your **average load volume** per week, and the modes that hurt the most?
- Where are your **top two pain lanes** — origin / destination pairs?
- What does your **invoicing & POD workflow** look like — do you need EDI or is portal/email fine?

---

## Likely objections + responses

| Objection | Response |
| --- | --- |
| "We already have a broker." | "Totally fair — most of our customers had one too. I'd love five minutes to bid one lane against them and show you what tight looks like." |
| "You're new — what's your bond?" | "$75k BMC-84 in place, certificate available on the spot. I'd rather earn the load than the comfort." |
| "Send me your info." | "Happy to — sending the capability statement to {contact or '<email>'} right after this call. Quick question while I have you: which lane would you most like priced?" |
| "Email me your rates." | "I price by lane — give me your top two and a benchmark RFQ comes back in 24 hours." |

---

## Close

> "I'll send a capability statement and a credit-reference packet over right now. Pencil me in for {contact or '<contact>'} — same time next Tuesday for a fifteen-minute review?"

Log the call. Mark next-touch in the CRM. Move on.

---

*{meta['company']} · {meta['founder']} · {meta['contact']} · {meta['phone']}*
"""


def _linkedin_dm(shipper: str, contact: str, lane: str,
                  intro: Optional[str], meta: Dict[str, str]) -> str:
    opening = intro or (
        f"Hi {contact or 'there'} — I'm building a new asset-light freight "
        f"brokerage out of {meta['city']} ({meta['company']}) and we'd love "
        f"to bid on {shipper}'s {lane or 'top'} lanes."
    )
    return (
        f"{opening}\n\n"
        f"One owner, full accountability, every doc auto-archived for seven "
        f"years. Open to a 15-minute intro this week? I'll come with a lane "
        f"benchmark for two of your corridors so the call is concrete.\n\n"
        f"— {meta['founder']} · {meta['contact']}"
    )


def _md_to_basic_html(md: str, meta: Dict[str, str]) -> str:
    """Tiny markdown → HTML so the email preview looks right in the UI."""
    html_lines = []
    for line in md.splitlines():
        s = line.rstrip()
        if not s:
            html_lines.append("<p></p>")
            continue
        if s.startswith("- "):
            html_lines.append(f"<li>{_inline_html(s[2:])}</li>")
        elif s.startswith("## "):
            html_lines.append(f"<h3 style='color:{meta['primary']}'>{s[3:]}</h3>")
        elif s.startswith("# "):
            html_lines.append(f"<h2 style='color:{meta['primary']}'>{s[2:]}</h2>")
        else:
            html_lines.append(f"<p>{_inline_html(s)}</p>")
    return ("<div style=\"font-family:Georgia,serif;color:#0B1320;"
            f"max-width:640px\">{''.join(html_lines)}</div>")


def _inline_html(t: str) -> str:
    import re
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*([^*]+?)\*", r"<i>\1</i>", t)
    return t


# ---------------------------------------------------------------------------
# Capability statement (PDF body)
# ---------------------------------------------------------------------------
def _capability_markdown(shipper: str, lane: str, mode: str,
                          meta: Dict[str, str]) -> str:
    target = shipper or "Prospective Shipping Partner"
    return f"""# CAPABILITY STATEMENT

**Prepared for:** {target}
**Date:** {_today()}
**From:** {meta['founder']}, Founder · {meta['company']}

## Who we are

{meta['company']} is a founder-led, asset-light freight brokerage based in {meta['city']}.
We move full truckload, less-than-truckload, parcel, and ocean / air freight
nationwide — but we do it differently:

- **One owner. One call.** You deal directly with the founder. No rotating bench.
- **Margin Shield pricing.** Every quote backed by a transparent margin model;
  no surprise fuel re-bills or accessorial gotchas at month-end.
- **Immutable 7-year document vault.** Every BOL, rate confirmation, POD, and
  invoice we issue is automatically captured into a SHA-256 fingerprinted
  archive — auditable at any time. Exceeds 49 CFR §379 (broker records, 3 yrs)
  by a comfortable margin.
- **Net 7 / 10 / 14 friendly.** Flexible terms because we factor on the back end.

## What we move

| Mode | Capability |
|---|---|
| Truckload | Dry van, reefer, flatbed, conestoga, step-deck — 48-state |
| LTL | Pre-priced NMFC class lanes via top-tier national LTL carriers |
| Parcel | UPS, FedEx, DHL — small parcel rating built into the TMS |
| Ocean / Air | NVOCC partner network for international FCL / LCL / air consolidations |
| Specialty | Hot shot, white-glove, hazmat (with proper authority) |

## Tech stack you inherit

- **Real-time tracking** via project44 / FourKites partner integrations
- **EDI** 204 / 210 / 214 / 990 / 856 ready (via SPS Commerce)
- **API** access to load status, invoices, PODs
- **Customer portal** with one-click document retrieval, signed POD download,
  and live in-transit map

## Authority & coverage

- MC # *(application in flight — current docs on request)*
- $75,000 BMC-84 surety bond
- $100k cargo / $1M auto / $1M general liability
- Workers' comp + cyber liability

## A focused first step

We'd like to bid on **two of {target}'s {lane or 'top corridors'}**
in {mode or 'your highest-volume mode'} — benchmark cost, transit, and a
side-by-side service plan delivered within 48 hours of receiving the RFQ.

> *Why now?* Because the cheapest freight is the freight that doesn't break.
> The second-cheapest is the freight that's tightly documented when it does.

---

**{meta['founder']}** · Founder
{meta['company']}
{meta['contact']} · {meta['phone']} · {meta['site']}
"""


def _agreement_markdown(shipper: str, contact: str, net_terms: int,
                         meta: Dict[str, str]) -> str:
    return f"""# BROKER · SHIPPER SERVICE AGREEMENT

**This agreement is made on {_today()} between:**

| Party | Detail |
|---|---|
| **BROKER** | {meta['company']} (a Minnesota LLC) — {meta['city']} |
| **SHIPPER** | {shipper or '[SHIPPER COMPANY]'} — c/o {contact or '[primary contact]'} |

## 1. Engagement

Shipper engages Broker as a non-exclusive transportation broker to arrange
the movement of Shipper's freight, by motor carrier or other regulated mode,
in interstate and intrastate commerce within the United States and (where
applicable) Canada and Mexico.

## 2. Scope of services

Broker shall: (a) source qualified motor carriers; (b) negotiate rates;
(c) issue rate confirmations; (d) coordinate pickup, transit, and delivery;
(e) deliver original or electronic Bills of Lading and Proofs of Delivery;
(f) invoice Shipper per the rate schedule below.

## 3. Independent contractors

Broker is acting solely as a property broker (FMCSA license # pending /
on file). The actual transportation is performed by independent motor
carriers under their own operating authority and insurance. Broker does
not own or lease the equipment.

## 4. Rates and payment terms

- **Rates:** As confirmed per-load in writing on each rate confirmation.
- **Payment terms:** **NET {net_terms}** days from invoice date.
- **Detention / accessorial:** Pre-approved in writing by Shipper before
  charges accrue. No retroactive accessorials.
- **Fuel surcharge:** Pass-through unless otherwise agreed in writing.

## 5. Cargo claims

Cargo loss & damage claims shall be filed under 49 CFR Part 370 against
the contracted carrier-of-record. Broker shall assist Shipper in claim
adjudication but is not the carrier and is not liable for cargo loss
except in cases of Broker negligence.

## 6. Insurance

Broker maintains:

- **General liability:** $1,000,000
- **Cargo (contingent):** $100,000
- **Auto liability:** $1,000,000 (carrier)
- **Workers' compensation:** statutory
- **Cyber liability:** $1,000,000

Certificates available on request and updated automatically when policies renew.

## 7. Confidentiality

Rates, lane data, customer lists, and any non-public business information
exchanged are confidential and shall not be disclosed to third parties
except as required to perform services.

## 8. Term & termination

This agreement remains in effect until terminated by either party with
**thirty (30) days' written notice**. Existing in-transit loads and
unpaid invoices survive termination.

## 9. Governing law

Minnesota law. Venue: Hennepin County, MN.

---

**Accepted on behalf of {meta['company']}:**

Signature: ______________________________  Date: ____________
Name: {meta['founder']}
Title: Founder

**Accepted on behalf of {shipper or '[SHIPPER]'}:**

Signature: ______________________________  Date: ____________
Name: ____________________________________
Title: ____________________________________

*{meta['company']} · {meta['contact']} · {meta['phone']} · {meta['site']}*
"""


def _welcome_markdown(shipper: str, contact: str,
                       meta: Dict[str, str]) -> str:
    return f"""# WELCOME TO {meta['short'].upper()}

**Date:** {_today()}
**To:** {contact or 'the team'} at {shipper or '[SHIPPER]'}

Welcome aboard. This packet walks you through the first 14 days so the
relationship starts the way good freight should — predictable, documented,
and quietly under control.

## Day 1 · Account setup

- We open your account in our TMS — you get a customer portal login
  with one-click access to live loads, BOLs, PODs, and invoices.
- You'll receive a welcome email from `{meta['contact']}` with portal
  credentials and a single point-of-contact card.

## Day 2 · First lane benchmark

- We benchmark your top two corridors against current spot + contract markets
  and send you a one-page **Margin Shield** report so you can see exactly
  where pricing sits.

## Day 3–7 · First loads

- We tender the first load via your preferred channel (email, EDI 204, or
  TMS portal).
- Rate confirmation issued same day. BOL drafted and sent to the shipper
  origin contact 24h before pickup.
- POD returned within 4 hours of delivery — auto-uploaded to your portal
  and our immutable 7-year archive.

## Day 8–14 · Cadence

- Weekly KPI digest emailed each Monday: lanes run, OTD %, claim ratio,
  average margin, and any flagged exceptions.
- Monthly business review on the calendar — we come with a lane-cost
  trend deck so we can plan the next month before it arrives.

## What you can ask of us at any time

- **Audit.** Pull any BOL, POD, rate-con, or invoice. Hashed, versioned,
  immutable.
- **Re-rate.** Spot-check a lane against the latest market in 24 hours.
- **Escalation.** {meta['founder']}'s direct line: {meta['phone']}.

---

**Thank you** for trusting us with the freight.
The spirit of Califia, the power of modern freight — that's the brand,
and we mean it every load.

**{meta['founder']}**
Founder · {meta['company']}
{meta['contact']} · {meta['phone']}
"""


def _credit_ref_markdown(shipper: str, meta: Dict[str, str]) -> str:
    return f"""# NEW CUSTOMER SETUP & CREDIT REFERENCE FORM

*Please complete and return to {meta['contact']}*

**Customer Name:** {shipper or '_______________________________'}

## Billing & contact

- Billing contact name: ______________________________
- Billing email: ______________________________
- Billing phone: ______________________________
- Accounts-payable portal (if any): ______________________________
- Preferred invoice format: ☐ Email PDF · ☐ EDI 210 · ☐ Customer portal

## Bank reference

- Bank name: ______________________________
- Account officer + phone: ______________________________

## Trade references (provide three)

| # | Company | Contact name | Phone | Email |
|---|---|---|---|---|
| 1 |   |   |   |   |
| 2 |   |   |   |   |
| 3 |   |   |   |   |

## Insurance / operating

- Operating authority MC #: ______________________________
- Federal Tax ID (W-9 attached): ______________________________
- COI required from carrier: $ ______________________________

## Authorized signer

Signature: ______________________________
Print name: ______________________________
Title: ______________________________
Date: ______________________________

---

*Return to {meta['contact']} or upload via the customer portal once you receive credentials.*
"""


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
class GenerateIn(BaseModel):
    shipper_name: str
    contact_name: Optional[str] = ""
    lane_focus: Optional[str] = ""
    mode_mix: Optional[str] = ""
    net_terms: Optional[int] = 14
    personalize_with_ai: Optional[bool] = True


def build_shipper_outreach_router(*, db, get_current_user, require_role,
                                    active_brand_doc):
    router = APIRouter(prefix="/shipper-outreach", tags=["shipper-outreach"])

    @router.get("/templates")
    async def list_templates(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "channels": [
                {"id": "email",       "label": "Cold Email",         "kind": "text"},
                {"id": "call_script", "label": "Cold Call Script",   "kind": "text"},
                {"id": "linkedin_dm", "label": "LinkedIn DM",        "kind": "text"},
                {"id": "capability_pdf", "label": "Capability Statement", "kind": "pdf"},
                {"id": "agreement_pdf",  "label": "Service Agreement",    "kind": "pdf"},
                {"id": "welcome_pdf",    "label": "Welcome Letter",       "kind": "pdf"},
                {"id": "credit_ref_pdf", "label": "Credit Reference Form","kind": "pdf"},
                {"id": "onboarding_packet", "label": "Full Onboarding Packet", "kind": "pdf"},
            ]
        }

    async def _make_text(channel: str, payload: GenerateIn,
                          brand: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        meta = _brand_meta(brand)
        intro = None
        if payload.personalize_with_ai:
            intro = await _maybe_personalize_intro(
                payload.shipper_name, payload.contact_name or "",
                payload.lane_focus or "", payload.mode_mix or "", channel)
        if channel == "email":
            content = _email_body(payload.shipper_name, payload.contact_name or "",
                                    payload.lane_focus or "", payload.mode_mix or "",
                                    intro, meta)
            return {"channel": "email", **content}
        if channel == "call_script":
            md = _call_script_md(payload.shipper_name,
                                  payload.contact_name or "",
                                  payload.lane_focus or "", meta)
            return {"channel": "call_script", "markdown": md}
        if channel == "linkedin_dm":
            return {"channel": "linkedin_dm",
                    "text": _linkedin_dm(payload.shipper_name,
                                          payload.contact_name or "",
                                          payload.lane_focus or "",
                                          intro, meta)}
        raise HTTPException(400, f"Unsupported text channel {channel}")

    @router.post("/generate")
    async def generate_text(payload: GenerateIn, channel: str = "email",
                              user=Depends(get_current_user)) -> Dict[str, Any]:
        brand = await active_brand_doc()
        out = await _make_text(channel, payload, brand)
        # log to audit so cold-call counts roll up into the Launch Runway
        try:
            await db.audit_log.insert_one({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "action": "cold_outreach_generated",
                "channel": channel,
                "shipper_name": payload.shipper_name,
                "by": getattr(user, "name", "system"),
            })
            if channel == "call_script":
                await db.audit_log.insert_one({
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "action": "cold_call",
                    "shipper_name": payload.shipper_name,
                    "by": getattr(user, "name", "system"),
                })
        except Exception:                                       # noqa: BLE001
            pass
        return out

    @router.post("/pdf")
    async def generate_pdf(payload: GenerateIn, channel: str,
                            user=Depends(get_current_user)) -> StreamingResponse:
        brand = await active_brand_doc()
        meta = _brand_meta(brand)
        if channel == "capability_pdf":
            md = _capability_markdown(payload.shipper_name, payload.lane_focus or "",
                                        payload.mode_mix or "", meta)
            title = "Capability Statement"
            subtitle = f"Prepared for {payload.shipper_name}"
            fname = f"Orisei_Capability_{_slug(payload.shipper_name)}.pdf"
        elif channel == "agreement_pdf":
            md = _agreement_markdown(payload.shipper_name,
                                       payload.contact_name or "",
                                       int(payload.net_terms or 14), meta)
            title = f"Service Agreement · Net {payload.net_terms or 14}"
            subtitle = payload.shipper_name
            fname = f"Orisei_Agreement_{_slug(payload.shipper_name)}.pdf"
        elif channel == "welcome_pdf":
            md = _welcome_markdown(payload.shipper_name,
                                     payload.contact_name or "", meta)
            title = "Welcome to Orisei"
            subtitle = payload.shipper_name
            fname = f"Orisei_Welcome_{_slug(payload.shipper_name)}.pdf"
        elif channel == "credit_ref_pdf":
            md = _credit_ref_markdown(payload.shipper_name, meta)
            title = "New Customer Setup"
            subtitle = "Credit & Trade References"
            fname = f"Orisei_NewCustomer_{_slug(payload.shipper_name)}.pdf"
        elif channel == "onboarding_packet":
            # Concatenate all four into one PDF via the markdown engine
            parts = [
                _welcome_markdown(payload.shipper_name, payload.contact_name or "", meta),
                _capability_markdown(payload.shipper_name, payload.lane_focus or "",
                                       payload.mode_mix or "", meta),
                _agreement_markdown(payload.shipper_name, payload.contact_name or "",
                                      int(payload.net_terms or 14), meta),
                _credit_ref_markdown(payload.shipper_name, meta),
            ]
            md = "\n\n---\n\n".join(parts)
            title = "Shipper Onboarding Packet"
            subtitle = f"For {payload.shipper_name}"
            fname = f"Orisei_OnboardingPacket_{_slug(payload.shipper_name)}.pdf"
        else:
            raise HTTPException(400, f"Unsupported pdf channel {channel}")

        pdf = build_branded_markdown_pdf(
            md, title=title, subtitle=subtitle, brand=brand,
            personalization={"firm_name": payload.shipper_name,
                              "contact_name": payload.contact_name or "",
                              "prepared_date": _today()},
        )
        # Auto-archive into the immutable Document Vault
        try:
            from .doc_vault import archive_pdf
            await archive_pdf(
                db, pdf,
                doc_type=("ONBOARDING_PACKET" if channel == "onboarding_packet"
                          else channel.upper().replace("_PDF", "")),
                doc_id=_slug(payload.shipper_name).upper()[:24] or "UNKNOWN",
                ref_id=None,
                source_endpoint=f"/api/shipper-outreach/pdf?channel={channel}",
                payload_snapshot=payload.model_dump(),
                user=user,
                filename=fname,
            )
        except Exception:                                       # noqa: BLE001
            log.exception("Vault archive failed for %s", channel)
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return router


def _slug(s: str) -> str:
    import re
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"
